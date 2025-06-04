import requests
import time
from formatter import format_authors
from parser import VALID_BIBTEX_TYPES
from logger import logger

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

def find_dblp_citation(arxiv_id, original_key):
    data = try_fetch_from_dblp(arxiv_id)
    if not data:
        return None

    hits = data.get('result', {}).get('hits', {})
    if int(hits.get('@total', 0)) == 0:
        logger.warning(f"No DBLP match found for citation key: {original_key}")
        return None

    hit = hits.get('hit', [])[0].get('info', {})
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
