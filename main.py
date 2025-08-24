# main.py
import argparse
from logger import logger
from pipeline import run_flow

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replace arXiv BibTeX entries with DBLP data and show per-record diffs."
    )
    parser.add_argument("input_file", help="Path to input .bib file")
    parser.add_argument("output_file", nargs="?", default="output.bib", help="Path to write the output .bib")
    parser.add_argument("--diff-report", help="Optional Markdown file to write a per-record change report")
    return parser

def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    logger.info("Running ArxivToDblp pipeline")
    stats = run_flow(args.input_file, args.output_file, args.diff_report)

    if not stats.get("ok", False):
        logger.error(f"Completed with errors: {stats.get('error')}")
        return 1

    logger.info(
        "Done. "
        f"Total={stats.get('total_records')} | "
        f"arXiv candidates={stats.get('arxiv_candidates')} | "
        f"replaced={stats.get('replaced')} | "
        f"unchanged={stats.get('unchanged')} | "
        f"no match={stats.get('no_match')} | "
        f"diffs={stats.get('diff_count')}"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
