import random
import threading
import time
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from formatter import format_authors
from logger import logger
from parser import VALID_BIBTEX_TYPES
from errors import LookupFailure

_CACHE_MISS = object()
_REQUEST_GATE_LOCK = threading.Lock()
_NEXT_REQUEST_NOT_BEFORE = 0.0


def _retry_wait_seconds(response: Optional[requests.Response], attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.5, float(retry_after))
            except ValueError:
                pass
    base_wait = min(16.0, 2 ** attempt)
    return base_wait + random.uniform(0.0, 0.5)


def _reserve_request_slot(min_gap_seconds: float = 1.25) -> None:
    """Serialize outbound DBLP calls and enforce a small inter-request gap."""
    global _NEXT_REQUEST_NOT_BEFORE
    with _REQUEST_GATE_LOCK:
        now = time.monotonic()
        wait = max(0.0, _NEXT_REQUEST_NOT_BEFORE - now)
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        _NEXT_REQUEST_NOT_BEFORE = now + min_gap_seconds


def _apply_global_cooldown(seconds: float) -> None:
    global _NEXT_REQUEST_NOT_BEFORE
    with _REQUEST_GATE_LOCK:
        _NEXT_REQUEST_NOT_BEFORE = max(_NEXT_REQUEST_NOT_BEFORE, time.monotonic() + seconds)


def _build_dblp_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=0,
        connect=0,
        read=0,
        status=0,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def try_fetch_from_dblp(arxiv_id, max_retries=5, request_timeout=10):
    base_urls = [
        "https://dblp.org/search/publ/api",
        "https://dblp.uni-trier.de/search/publ/api",
    ]
    headers = {
        "User-Agent": "arXivToDBLP/1.0 (+https://dblp.org)",
        "Accept": "application/json",
        "Connection": "close",
    }

    for attempt in range(max_retries):
        response: Optional[requests.Response] = None
        session = _build_dblp_session()
        base_url = base_urls[attempt % len(base_urls)]
        try:
            _reserve_request_slot()
            logger.info(f"Querying DBLP for arXiv ID: {arxiv_id} via {base_url}")
            response = session.get(
                base_url,
                params={"q": arxiv_id, "format": "json"},
                timeout=request_timeout,
                headers=headers,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Received {response.status_code} from DBLP for ID {arxiv_id} via {base_url}")
            if response.status_code == 429:
                cooldown = _retry_wait_seconds(response, attempt)
                _apply_global_cooldown(max(cooldown, 10.0))
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"Transient network error while querying DBLP (attempt {attempt + 1}/{max_retries}) for {arxiv_id}: {e}")
            else:
                logger.error(f"Network error while querying DBLP for {arxiv_id}: {e}")
        finally:
            session.close()

        if attempt < max_retries - 1:
            time.sleep(_retry_wait_seconds(response, attempt))

    logger.error(f"Failed to fetch from DBLP for {arxiv_id} after {max_retries} retries.")
    raise LookupFailure(f"DBLP lookup failed for arXiv ID {arxiv_id}")


def find_dblp_citation(arxiv_id, original_key, request_timeout=10, min_confidence=0.0):
    data = try_fetch_from_dblp(arxiv_id, request_timeout=request_timeout)
    if not data:
        return None

    hits = data.get('result', {}).get('hits', {})
    if int(hits.get('@total', 0)) == 0:
        logger.warning(f"No DBLP match found for citation key: {original_key}")
        return None

    raw_hit = hits.get('hit', [])
    if isinstance(raw_hit, dict):
        candidate_hits = [(raw_hit.get("info") or {})]
    elif isinstance(raw_hit, list) and raw_hit:
        candidate_hits = [(h.get("info") or {}) for h in raw_hit if isinstance(h, dict)]
    else:
        logger.warning(f"Malformed DBLP response for citation key: {original_key}")
        return None
    hit = candidate_hits[0]
    for cand in candidate_hits:
        blob = " ".join(str(cand.get(k, "")) for k in ("ee", "url", "note", "key", "title"))
        if arxiv_id in blob:
            hit = cand
            break
    record_type = hit.get('type', 'misc')
    if record_type not in VALID_BIBTEX_TYPES:
        record_type = 'misc'

    authors = format_authors(hit.get('authors'))
    if not authors:
        logger.warning(f"Missing author data for DBLP record: {hit}")

    citation = {
        'type': record_type,
        'citation_key': original_key,
        'fields': {k: v for k, v in hit.items() if k not in ['type', 'key', 'authors']}
    }
    citation['fields']['author'] = authors
    if min_confidence >= 0.7:
        source_blob = " ".join(str(hit.get(k, "")) for k in ("ee", "url", "note", "key", "title"))
        if arxiv_id not in source_blob:
            return None
    return citation


class DblpLookupService:
    """Resolve arXiv IDs to DBLP records with dedupe and short cache."""

    def __init__(
        self,
        max_concurrency: int = 1,
        per_request_timeout: float = 8.0,
        total_timeout_budget: float = 20.0,
        cache_ttl_seconds: float = 120.0,
    ):
        # Intentionally pinned to sequential DBLP requests to avoid burst traffic.
        self.max_concurrency = 1
        self.per_request_timeout = per_request_timeout
        self.total_timeout_budget = total_timeout_budget
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Tuple[float, Optional[dict]]] = {}
        self._cache_lock = threading.Lock()

    def _cache_get(self, arxiv_id: str):
        now = time.time()
        with self._cache_lock:
            cached = self._cache.get(arxiv_id)
            if cached is None:
                return _CACHE_MISS
            ts, value = cached
            if now - ts > self.cache_ttl_seconds:
                self._cache.pop(arxiv_id, None)
                return _CACHE_MISS
            return value

    def _cache_set(self, arxiv_id: str, value: Optional[dict]) -> None:
        with self._cache_lock:
            self._cache[arxiv_id] = (time.time(), value)

    def _fetch_one(self, arxiv_id: str, original_key: str) -> Optional[dict]:
        return find_dblp_citation(
            arxiv_id,
            original_key,
            request_timeout=self.per_request_timeout,
        )

    def lookup_many(
        self,
        arxiv_ids: List[Optional[str]],
        original_keys: List[Optional[str]],
    ) -> List[Optional[dict]]:
        """Return results aligned to input ordering with deduped remote calls."""
        results_by_id: Dict[str, Optional[dict]] = {}

        unique_ids: List[str] = []
        first_keys: Dict[str, str] = {}
        for arxiv_id, original_key in zip(arxiv_ids, original_keys):
            if not arxiv_id:
                continue
            if arxiv_id not in first_keys:
                unique_ids.append(arxiv_id)
                first_keys[arxiv_id] = original_key or arxiv_id

        pending_ids: List[str] = []
        for arxiv_id in unique_ids:
            cached = self._cache_get(arxiv_id)
            if cached is not _CACHE_MISS:
                results_by_id[arxiv_id] = cached
            else:
                pending_ids.append(arxiv_id)

        deadline = time.monotonic() + self.total_timeout_budget
        for arxiv_id in pending_ids:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(f"DBLP lookup budget exhausted; skipping unresolved ID {arxiv_id}")
                results_by_id[arxiv_id] = None
                self._cache_set(arxiv_id, None)
                continue

            started = time.monotonic()
            try:
                result = self._fetch_one(arxiv_id, first_keys[arxiv_id])
            except Exception as e:
                logger.warning(f"DBLP lookup failed for {arxiv_id}: {e}")
                result = None

            elapsed = time.monotonic() - started
            if elapsed > remaining:
                logger.warning(f"DBLP lookup budget exceeded while resolving {arxiv_id}")
                result = None

            results_by_id[arxiv_id] = result
            self._cache_set(arxiv_id, result)

        ordered_results: List[Optional[dict]] = []
        for arxiv_id, original_key in zip(arxiv_ids, original_keys):
            if not arxiv_id:
                ordered_results.append(None)
                continue

            resolved = results_by_id.get(arxiv_id)
            if resolved:
                adjusted = {
                    **resolved,
                    "citation_key": original_key or resolved.get("citation_key")
                }
                ordered_results.append(adjusted)
            else:
                ordered_results.append(None)

        return ordered_results
