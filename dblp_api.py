import re
import requests
import time
from difflib import SequenceMatcher
from formatter import format_authors
from parser import VALID_BIBTEX_TYPES
from logger import logger


ARXIV_ID_PATTERN = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)?(?P<id>\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)


def try_fetch_from_dblp(arxiv_id, max_retries=5):
    url = f'https://dblp.org/search/publ/api?q={arxiv_id}&format=json'
    for attempt in range(max_retries):
        try:
            logger.info(f"Querying DBLP for arXiv ID: {arxiv_id}")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Received {response.status_code} from DBLP for ID {arxiv_id}")
        except requests.RequestException as e:
            logger.error(f"Network error while querying DBLP: {e}")
        time.sleep(2 ** attempt)
    logger.error(f"Failed to fetch from DBLP for {arxiv_id} after {max_retries} retries.")
    return None


def _normalize_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).lower())).strip()


def _normalize_arxiv_id(value):
    match = ARXIV_ID_PATTERN.search(str(value or ""))
    if not match:
        return ""
    return match.group("id").lower()


def _extract_candidate(hit_info):
    authors_blob = hit_info.get("authors")
    authors_list = []
    if isinstance(authors_blob, dict):
        author_value = authors_blob.get("author", [])
        if isinstance(author_value, list):
            authors_list = [a.get("text") if isinstance(a, dict) else str(a) for a in author_value]
        elif author_value:
            authors_list = [author_value.get("text") if isinstance(author_value, dict) else str(author_value)]

    candidate_sources = [
        str(hit_info.get("title", "")),
        str(hit_info.get("url", "")),
        str(hit_info.get("ee", "")),
        str(hit_info.get("key", "")),
        str(hit_info.get("note", "")),
    ]

    return {
        "raw": hit_info,
        "title": hit_info.get("title", ""),
        "year": str(hit_info.get("year", "")).strip(),
        "venue": hit_info.get("venue", ""),
        "authors": [a for a in authors_list if a],
        "sources": [s for s in candidate_sources if s],
    }


def _score_candidate(arxiv_id, candidate):
    normalized_query = _normalize_arxiv_id(arxiv_id)
    normalized_title = _normalize_text(candidate["title"])
    title_similarity = SequenceMatcher(None, _normalize_text(normalized_query), normalized_title).ratio() if normalized_query else 0.0

    matched_sources = []
    for source in candidate["sources"]:
        source_norm = _normalize_arxiv_id(source)
        if source_norm and source_norm.startswith(normalized_query):
            matched_sources.append(source)

    arxiv_id_match = bool(matched_sources)

    score = 0.0
    if arxiv_id_match:
        score += 0.8
    score += min(title_similarity, 1.0) * 0.2

    return {
        "score": min(score, 1.0),
        "title_similarity": title_similarity,
        "arxiv_id_match": arxiv_id_match,
        "matched_sources": matched_sources,
    }


def _build_citation_from_hit(hit, original_key):
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
    return citation


def find_dblp_citation(arxiv_id, original_key, min_confidence=0.70):
    data = try_fetch_from_dblp(arxiv_id)
    if not data:
        return None

    hits = data.get('result', {}).get('hits', {})
    if int(hits.get('@total', 0)) == 0:
        logger.warning(f"No DBLP match found for citation key: {original_key}")
        return None

    raw_hits = hits.get('hit', [])
    if isinstance(raw_hits, dict):
        raw_hits = [raw_hits]

    scored = []
    for idx, raw_hit in enumerate(raw_hits):
        hit_info = raw_hit.get("info", {})
        candidate = _extract_candidate(hit_info)
        rank = _score_candidate(arxiv_id, candidate)
        scored.append((idx, hit_info, candidate, rank))

    if not scored:
        logger.warning(f"DBLP returned no parseable hits for citation key: {original_key}")
        return None

    scored.sort(key=lambda item: (-item[3]["score"], -int(item[3]["arxiv_id_match"]), -item[3]["title_similarity"], item[0]))

    best_idx, best_hit, best_candidate, best_rank = scored[0]
    if best_rank["score"] < min_confidence:
        logger.info(
            "Rejected DBLP candidates below confidence threshold",
            extra={
                "event": "dblp_match_rejected",
                "citation_key": original_key,
                "arxiv_id": arxiv_id,
                "threshold": min_confidence,
                "top_candidate": {
                    "index": best_idx,
                    "title": best_candidate["title"],
                    "year": best_candidate["year"],
                    "venue": best_candidate["venue"],
                    "authors": best_candidate["authors"],
                    "metrics": best_rank,
                },
                "candidate_count": len(scored),
            },
        )
        return None

    logger.info(
        "Selected DBLP candidate",
        extra={
            "event": "dblp_match_selected",
            "citation_key": original_key,
            "arxiv_id": arxiv_id,
            "selected_index": best_idx,
            "selected_candidate": {
                "title": best_candidate["title"],
                "year": best_candidate["year"],
                "venue": best_candidate["venue"],
                "authors": best_candidate["authors"],
                "metrics": best_rank,
            },
            "evaluated_candidates": [
                {
                    "index": idx,
                    "title": candidate["title"],
                    "year": candidate["year"],
                    "venue": candidate["venue"],
                    "authors": candidate["authors"],
                    "metrics": rank,
                }
                for idx, _, candidate, rank in scored
            ],
        },
    )

    return _build_citation_from_hit(best_hit, original_key)
