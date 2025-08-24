# pipeline.py
from typing import Optional, Dict, Any, List
from parser import parse_bib_file, write_bib_file
from dblp_api import find_dblp_citation
from logger import logger
from diff import compute_diff, format_changes_for_log, format_changes_markdown

def run_flow(
    input_file: str,
    output_file: str,
    diff_report: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the full conversion pipeline:
      1) Parse input .bib
      2) For arXiv records, attempt DBLP replacement
      3) Log and optionally write per-record diffs
      4) Write output .bib

    Returns a stats dict suitable for logging/telemetry or testing.
    """
    # 1) Parse
    try:
        original_records = parse_bib_file(input_file)
    except Exception as e:
        logger.critical(f"Parsing failed for {input_file}: {e}")
        return {"ok": False, "error": "parse_failed"}

    new_records: List[dict] = []
    report_sections: List[str] = []

    stats = {
        "ok": True,
        "input_file": input_file,
        "output_file": output_file,
        "total_records": len(original_records),
        "arxiv_candidates": 0,
        "replaced": 0,
        "unchanged": 0,
        "no_match": 0,
        "diff_count": 0,
    }

    # 2) Process records
    for record in original_records:
        from_arxiv = record.get("from_arxiv")
        arxiv_id = record.get("arxiv_id")
        fields = record.get("fields", {})
        title = fields.get("title", "No title")

        if from_arxiv and arxiv_id:
            stats["arxiv_candidates"] += 1
            logger.info(f"Looking up: {title}")

            dblp = find_dblp_citation(arxiv_id, record["citation_key"])
            if dblp:
                changes = compute_diff(record, dblp)
                if changes:
                    stats["diff_count"] += 1
                    logger.info("\n" + format_changes_for_log(record["citation_key"], changes))
                    if diff_report:
                        report_sections.append(
                            format_changes_markdown(record["citation_key"], record, dblp, changes)
                        )
                else:
                    stats["unchanged"] += 1
                    logger.info(f"No changes for {record['citation_key']}")
                new_records.append(dblp)
                stats["replaced"] += 1
            else:
                new_records.append(record)
                stats["no_match"] += 1
        else:
            new_records.append(record)

    # 3) Write output
    try:
        write_bib_file(output_file, new_records)
    except Exception as e:
        logger.critical(f"Writing output failed for {output_file}: {e}")
        return {"ok": False, "error": "write_failed", **stats}

    # 4) Optional Markdown report
    if diff_report:
        try:
            with open(diff_report, "w", encoding="utf-8") as f:
                if report_sections:
                    f.write("# BibTeX Changes Report\n\n")
                    f.write("\n".join(report_sections))
                else:
                    f.write("# BibTeX Changes Report\n\nNo changes found.\n")
            logger.info(f"Wrote diff report to {diff_report}")
        except Exception as e:
            logger.error(f"Failed to write diff report: {e}")
            # Not fatal for the main flow

    return stats
