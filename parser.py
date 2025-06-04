import re
from logger import logger

VALID_BIBTEX_TYPES = {
    "article", "book", "booklet", "conference", "inbook", "incollection",
    "inproceedings", "manual", "mastersthesis", "misc", "phdthesis",
    "proceedings", "techreport", "unpublished"
}

def extract_arxiv_id(*fields):
    for field in fields:
        if not field:
            continue
        match = (
            re.search(r'arxiv\.org/(abs|pdf)/([^\s/]+)', field) or
            re.search(r'arxiv:(\d+\.\d+)', field) or
            re.search(r'abs/(\d+\.\d+)', field)
        )
        if match:
            return match.group(2) if len(match.groups()) > 1 else match.group(1)
    return None

def parse_bib_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error reading BibTeX file: {e}")
        raise

    entries = re.findall(r'@(\w+)\s*{\s*([^,]+),([\s\S]*?)}\s*(?=@|$)', content)
    parsed = []

    for entry_type, citation_key, body in entries:
        entry_type = entry_type.lower()
        fields = dict(re.findall(r'(\w+)\s*=\s*[{"]([^"}]+)[}"]', body))

        url = fields.get('url', '').lower()
        journal = fields.get('journal', '').lower()
        volume = fields.get('volume', '').lower()
        from_arxiv = any('arxiv' in val for val in [url, journal, volume])
        arxiv_id = extract_arxiv_id(url, journal, volume) if from_arxiv else ""

        if entry_type not in VALID_BIBTEX_TYPES:
            entry_type = 'misc'

        parsed.append({
            'type': entry_type,
            'citation_key': citation_key,
            'fields': fields,
            'from_arxiv': from_arxiv,
            'arxiv_id': arxiv_id,
            'raw': f'@{entry_type}{{{citation_key},\n{body}}}'
        })
    
    logger.info(f"Parsed {len(parsed)} entries from {path}")
    return parsed

def write_bib_file(path, records):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            for rec in records:
                fields = rec['fields']
                lines = [f"@{rec['type']}{{{rec['citation_key']},"]
                for key, value in fields.items():
                    lines.append(f"  {key} = {{{value}}},")
                if lines[-1].endswith(','):
                    lines[-1] = lines[-1][:-1]
                lines.append("}\n")
                f.write("\n".join(lines) + "\n")
        logger.info(f"Wrote {len(records)} entries to {path}")
    except Exception as e:
        logger.error(f"Failed to write BibTeX file: {e}")
        raise
