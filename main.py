import re
import requests
import bibtexparser
import argparse
import time

valid_bibtex_types = {
    "article", "book", "booklet", "conference", "inbook", "incollection", "inproceedings", "manual",
    "mastersthesis", "misc", "phdthesis", "proceedings", "techreport", "unpublished"
}

def extract_arxiv_id(url, journal, volume):
    """Extract the arXiv ID from URL, journal, or volume fields."""
    for field in [url, journal, volume]:
        if not field:
            continue
        match = re.search(r'arxiv\.org/(abs|pdf)/([^\s/]+)', field) or \
                re.search(r'arxiv:(\d+\.\d+)', field) or \
                re.search(r'abs/(\d+\.\d+)', field)
        if match:
            return match.group(2) if len(match.groups()) > 1 else match.group(1)
    return None

def format_authors(author_dict):
    authors = [entry['text'] for entry in author_dict.get('author', [])]
    
    if not authors:
        return ""
    elif len(authors) == 1:
        return authors[0]
    
    author_list = []
    
    for i, author in enumerate(authors, start=1):
        author_list.append(f"author{i}: {author}")
    
    return " and ".join(author_list) if len(authors) > 1 else author_list[0]

def parse_bib_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        bib_database = bibtexparser.load(file)
    
    records = []
    for entry in bib_database.entries:
        fields = {key: value for key, value in entry.items() if key not in ['ENTRYTYPE', 'ID']}
        
        url_lower = fields.get('url', '').lower()
        journal_lower = fields.get('journal', '').lower()
        volume_lower = fields.get('volume', '').lower()
        from_arxiv = any('arxiv' in field for field in [url_lower, journal_lower, volume_lower])
        
        arxiv_id = extract_arxiv_id(url_lower, journal_lower, volume_lower)
        
        record_type = entry.get('ENTRYTYPE', 'unknown')
        if record_type not in valid_bibtex_types:
            record_type = 'misc'

        record = {
            'type': record_type,
            'citation_key': entry.get('ID', 'unknown_key'),
            'fields': fields,
            'from_arxiv': from_arxiv,
            'arxiv_id': arxiv_id
        }
        records.append(record)
    
    return records

def try_fetch_from_dblp(arxiv_id, max_retries=5):
    url = f'https://dblp.org/search/publ/api?q={arxiv_id}&format=json'
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response
            print(f"Error fetching data: {response.status_code}, retrying...")
        except requests.RequestException as e:
            print(f"Request error: {e}, retrying...")
        time.sleep(2 ** retries)
        retries += 1
    else:
        print("Failed to fetch data from DBLP after multiple attempts.")
        return None

def find_dblp_citation(arxiv_id, original_citation_key):
    response = try_fetch_from_dblp(arxiv_id)
    if response == None:
        raise(f"Didnt get DBLP response for {original_citation_key}")
    
    data = response.json()
    hits = data.get('result', {}).get('hits', {})
    if int(hits.get('@total', 0)) == 0:
        print("No matches found on DBLP.")
        return None

    hit = hits.get('hit', [])[0].get('info', {})
    record_type = hit.get('type', 'misc')
    if record_type not in valid_bibtex_types:
        record_type = 'misc'

    authors = hit.get('authors')
    if not authors:
        print(f'Did not find authors for {hit}')

    citation = {
        'type': record_type,
        'citation_key': original_citation_key,
        'authors': format_authors(authors),
        'fields': {key: value for key, value in hit.items() if key not in ['type', 'key', 'authors']}
    }

    return citation

def write_bib_file(file_path, records):
    bib_database = bibtexparser.bibdatabase.BibDatabase()
    bib_database.entries = [
        {**{'ENTRYTYPE': record['type'], 'ID': record['citation_key']}, 'authors': record.get('authors', record.get('author', 'NO FUCKING AUTHOR??')), **record['fields']}
        for record in records if record
    ]
    
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(bibtexparser.dumps(bib_database))

def main():
    parser = argparse.ArgumentParser(description="Replace arXiv citations with DBLP while keeping original citation keys. Should be completely compatible with your original bibtex file.")
    parser.add_argument("input_file", help="Path to the input .bib file")
    parser.add_argument("output_file", help="Path to the output .bib file", nargs='?', default="output.bib")
    args = parser.parse_args()

    new_records = []
    records = parse_bib_file(args.input_file)
    for record in records:
        if record['from_arxiv'] and record['arxiv_id']:
            record_title = record['fields'].get('title', 'Unknown Title')
            print(f'Searching for DBLP citation for {record_title}')
            dblp_citation = find_dblp_citation(record['arxiv_id'], record['citation_key'])
            new_records.append(dblp_citation if dblp_citation else record)
        elif record['from_arxiv']:
            print(f'This record is from arXiv but we did not find the arxiv ID: {record}')
            new_records.append(record)
        else:
            new_records.append(record)
    
    write_bib_file(args.output_file, new_records)

if __name__ == "__main__":
    main()
