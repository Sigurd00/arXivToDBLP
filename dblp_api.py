import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import requests

from formatter import format_authors
from logger import logger
from parser import VALID_BIBTEX_TYPES
from errors import LookupFailure

_CACHE_MISS = object()


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


def try_fetch_from_dblp(arxiv_id, max_retries=5, request_timeout=10):
    url = f'https://dblp.org/search/publ/api?q={arxiv_id}&format=json'
    headers = {
        "User-Agent": "arXivToDBLP/1.0 (+https://dblp.org)",
        "Accept": "application/json",
        "Connection": "close",
    }
    session = requests.Session()

    for attempt in range(max_retries):
        response: Optional[requests.Response] = None
        try:
            logger.info(f"Querying DBLP for arXiv ID: {arxiv_id}")
            response = session.get(url, timeout=request_timeout, headers=headers)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Received {response.status_code} from DBLP for ID {arxiv_id}")
        except requests.RequestException as e:
            logger.error(f"Network error while querying DBLP: {e}")

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
    """Resolve arXiv IDs to DBLP records with dedupe, bounded concurrency and short cache."""

    def __init__(
        self,
        max_concurrency: int = 8,
        per_request_timeout: float = 8.0,
        total_timeout_budget: float = 20.0,
        cache_ttl_seconds: float = 120.0,
    ):
        self.max_concurrency = max_concurrency
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
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = {
                arxiv_id: executor.submit(self._fetch_one, arxiv_id, first_keys[arxiv_id])
                for arxiv_id in pending_ids
            }

            for arxiv_id in pending_ids:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(f"DBLP lookup budget exhausted; skipping unresolved ID {arxiv_id}")
                    results_by_id[arxiv_id] = None
                    self._cache_set(arxiv_id, None)
                    futures[arxiv_id].cancel()
                    continue

                try:
                    result = futures[arxiv_id].result(timeout=remaining)
                except Exception as e:
                    logger.warning(f"DBLP lookup failed/timed out for {arxiv_id}: {e}")
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
