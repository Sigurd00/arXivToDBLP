import argparse
from parser import parse_bib_file, write_bib_file
from dblp_api import find_dblp_citation
from logger import logger

def main():
    parser = argparse.ArgumentParser(description="Replace arXiv BibTeX entries with DBLP data")
    parser.add_argument("input_file")
    parser.add_argument("output_file", nargs="?", default="output.bib")
    args = parser.parse_args()

    try:
        original_records = parse_bib_file(args.input_file)
    except Exception:
        logger.critical("Parsing failed. Aborting.")
        return

    new_records = []
    for record in original_records:
        if record['from_arxiv'] and record['arxiv_id']:
            logger.info(f"Looking up: {record['fields'].get('title', 'No title')}")
            dblp = find_dblp_citation(record['arxiv_id'], record['citation_key'])
            new_records.append(dblp if dblp else record)
        else:
            new_records.append(record)

    try:
        write_bib_file(args.output_file, new_records)
    except Exception:
        logger.critical("Writing output failed.")

if __name__ == "__main__":
    logger.info("Running arXivToDblp as a CLI tool")
    main()
