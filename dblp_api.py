import requests
import time
from formatter import format_authors
from parser import VALID_BIBTEX_TYPES
from logger import logger
from errors import LookupFailure


def try_fetch_from_dblp(arxiv_id, max_retries=5):
    url = f'https://dblp.org/search/publ/api?q={arxiv_id}&format=json'
    last_error = None
    for attempt in range(max_retries):
        try:
            logger.info(
                "querying_dblp",
                extra={"arxiv_id": arxiv_id, "stage": "lookup", "attempt": attempt + 1},
            )
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            logger.warning(
                "dblp_non_200",
                extra={
                    "arxiv_id": arxiv_id,
                    "stage": "lookup",
                    "status_code": response.status_code,
                },
            )
        except requests.RequestException as e:
            last_error = e
            logger.error(
                "dblp_network_error",
                extra={"arxiv_id": arxiv_id, "stage": "lookup", "exception_type": type(e).__name__},
            )
        time.sleep(2 ** attempt)

    logger.error(
        "dblp_lookup_failed",
        extra={"arxiv_id": arxiv_id, "stage": "lookup", "exception_type": type(last_error).__name__ if last_error else "None"},
    )
    raise LookupFailure(f"DBLP lookup failed for arXiv ID {arxiv_id}")


def find_dblp_citation(arxiv_id, original_key):
    data = try_fetch_from_dblp(arxiv_id)

    hits = data.get('result', {}).get('hits', {})
    if int(hits.get('@total', 0)) == 0:
        logger.warning(
            "dblp_no_match",
            extra={"citation_key": original_key, "arxiv_id": arxiv_id, "stage": "lookup"},
        )
        return None

    hit = hits.get('hit', [])[0].get('info', {})
    record_type = hit.get('type', 'misc')
    if record_type not in VALID_BIBTEX_TYPES:
        record_type = 'misc'

    authors = format_authors(hit.get('authors'))
    if not authors:
        logger.warning(
            "dblp_missing_author",
            extra={"citation_key": original_key, "arxiv_id": arxiv_id, "stage": "transform"},
        )

    citation = {
        'type': record_type,
        'citation_key': original_key,
        'fields': {k: v for k, v in hit.items() if k not in ['type', 'key', 'authors']}
    }
    citation['fields']['author'] = authors
    return citation
