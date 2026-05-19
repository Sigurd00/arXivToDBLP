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


def _skip_ws(content, i):
    while i < len(content) and content[i].isspace():
        i += 1
    return i


def _read_balanced(content, i, open_char, close_char):
    depth = 1
    i += 1
    out = []
    escaped = False
    in_quotes = False

    while i < len(content):
        ch = content[i]

        if escaped:
            out.append(ch)
            escaped = False
            i += 1
            continue

        if ch == '\\':
            out.append(ch)
            escaped = True
            i += 1
            continue

        if ch == '"':
            in_quotes = not in_quotes
            out.append(ch)
            i += 1
            continue

        if not in_quotes and ch == open_char:
            depth += 1
            out.append(ch)
        elif not in_quotes and ch == close_char:
            depth -= 1
            if depth == 0:
                return ''.join(out), i + 1
            out.append(ch)
        else:
            out.append(ch)
        i += 1

    raise ValueError("Unterminated balanced value")


def _read_quoted(content, i):
    i += 1
    out = []
    escaped = False
    while i < len(content):
        ch = content[i]
        if escaped:
            out.append(ch)
            escaped = False
        elif ch == '\\':
            out.append(ch)
            escaped = True
        elif ch == '"':
            return ''.join(out), i + 1
        else:
            out.append(ch)
        i += 1
    raise ValueError("Unterminated quoted value")


def _read_entry_header(content, i):
    start = i
    i += 1
    type_start = i
    while i < len(content) and (content[i].isalnum() or content[i] in "_-"):
        i += 1
    entry_type = content[type_start:i]
    i = _skip_ws(content, i)
    if i >= len(content) or content[i] not in "{(":
        raise ValueError(f"Invalid entry header near index {start}")

    opener = content[i]
    i += 1
    i = _skip_ws(content, i)
    key_start = i
    while i < len(content) and content[i] != ',':
        i += 1
    if i >= len(content):
        raise ValueError("Missing citation key separator")
    citation_key = content[key_start:i].strip()
    return entry_type, citation_key, i + 1, opener


def _parse_fields(content, i, close_char):
    fields = {}
    while i < len(content):
        i = _skip_ws(content, i)
        if i >= len(content):
            break
        if content[i] == close_char:
            return fields, i + 1

        key_start = i
        while i < len(content) and (content[i].isalnum() or content[i] in "_-"):
            i += 1
        key = content[key_start:i]
        if not key:
            raise ValueError(f"Invalid field name at index {i}")

        i = _skip_ws(content, i)
        if i >= len(content) or content[i] != '=':
            raise ValueError(f"Expected '=' after field {key}")
        i += 1
        i = _skip_ws(content, i)

        if i >= len(content):
            raise ValueError(f"Missing value for field {key}")

        if content[i] == '{':
            value, i = _read_balanced(content, i, '{', '}')
        elif content[i] == '"':
            value, i = _read_quoted(content, i)
        else:
            raw_start = i
            while i < len(content) and content[i] not in (',', close_char):
                i += 1
            value = content[raw_start:i].strip()

        fields[key] = value

        i = _skip_ws(content, i)
        if i < len(content) and content[i] == ',':
            i += 1
    raise ValueError("Unterminated entry body")


def parse_bib_content(content: str) -> list[dict]:
    parsed = []
    i = 0
    while i < len(content):
        at = content.find('@', i)
        if at == -1:
            break

        entry_type, citation_key, body_start, opener = _read_entry_header(content, at)
        closer = '}' if opener == '{' else ')'
        fields, end_idx = _parse_fields(content, body_start, closer)
        raw_entry = content[at:end_idx]

        normalized_type = entry_type.lower()
        entry_type_out = normalized_type if normalized_type in VALID_BIBTEX_TYPES else 'misc'

        lowered = {k.lower(): v for k, v in fields.items()}
        url = lowered.get('url', '').lower()
        journal = lowered.get('journal', '').lower()
        volume = lowered.get('volume', '').lower()
        from_arxiv = any('arxiv' in val for val in [url, journal, volume])
        arxiv_id = extract_arxiv_id(url, journal, volume) if from_arxiv else ""

        parsed.append({
            'type': entry_type_out,
            'citation_key': citation_key,
            'fields': fields,
            'from_arxiv': from_arxiv,
            'arxiv_id': arxiv_id,
            'raw': raw_entry,
        })
        i = end_idx
    return parsed


def parse_bib_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error reading BibTeX file: {e}")
        raise

    parsed = parse_bib_content(content)
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
