from typing import Optional, Dict, Any, List
from parser import parse_bib_file, write_bib_file
from dblp_api import find_dblp_citation
from logger import logger
from diff import compute_diff, format_changes_for_log, format_changes_markdown
from errors import ParseFailure, WriteFailure, LookupFailure


def run_flow(input_file: str, output_file: str, diff_report: Optional[str] = None) -> Dict[str, Any]:
    try:
        original_records = parse_bib_file(input_file)
    except Exception as e:
        err = ParseFailure(str(e))
        logger.critical("parse_failed", extra={"stage": "parse", "exception_type": type(err).__name__})
        return {"ok": False, "error": "parse_failed", "total": 0, "candidates": 0, "replaced": 0, "no_match": 0, "failures": 1}

    new_records: List[dict] = []
    report_sections: List[str] = []
    stats = {"ok": True, "input_file": input_file, "output_file": output_file, "total": len(original_records), "candidates": 0, "replaced": 0, "no_match": 0, "failures": 0, "diff_count": 0}

    for record in original_records:
        if record.get("from_arxiv") and record.get("arxiv_id"):
            arxiv_id = record["arxiv_id"]
            citation_key = record.get("citation_key")
            stats["candidates"] += 1
            try:
                dblp = find_dblp_citation(arxiv_id, citation_key)
            except LookupFailure as e:
                logger.error("lookup_failed", extra={"citation_key": citation_key, "arxiv_id": arxiv_id, "stage": "lookup", "exception_type": type(e).__name__})
                stats["failures"] += 1
                new_records.append(record)
                continue

            if dblp:
                changes = compute_diff(record, dblp)
                if changes:
                    stats["diff_count"] += 1
                    logger.info(format_changes_for_log(citation_key, changes), extra={"citation_key": citation_key, "arxiv_id": arxiv_id, "stage": "diff"})
                    if diff_report:
                        report_sections.append(format_changes_markdown(citation_key, record, dblp, changes))
                new_records.append(dblp)
                stats["replaced"] += 1
            else:
                stats["no_match"] += 1
                new_records.append(record)
        else:
            new_records.append(record)

    try:
        write_bib_file(output_file, new_records)
    except Exception as e:
        err = WriteFailure(str(e))
        logger.critical("write_failed", extra={"stage": "write", "exception_type": type(err).__name__})
        return {**stats, "ok": False, "error": "write_failed", "failures": stats["failures"] + 1}

    if diff_report:
        try:
            with open(diff_report, "w", encoding="utf-8") as f:
                f.write("# BibTeX Changes Report\n\n")
                f.write("\n".join(report_sections) if report_sections else "No changes found.\n")
        except Exception as e:
            logger.error("diff_report_failed", extra={"stage": "write_report", "exception_type": type(e).__name__})
    return stats
