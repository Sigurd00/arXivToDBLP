# pipeline.py
from typing import Optional, Dict, Any, List
from parser import parse_bib_file, write_bib_file
from dblp_api import find_dblp_citation
from logger import logger
from diff import format_changes_for_log, format_changes_markdown
from transform_service import generate_proposals, apply_replacements

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
        return {"ok": False, "error": "parse_failed", "failures": 1}

    report_sections: List[str] = []

    # 2) Process records via shared transformation service
    proposal_result = generate_proposals(original_records, find_dblp_citation)
    proposals = proposal_result["proposals"]
    diffs = proposal_result["diffs"]
    shared_stats = proposal_result["stats"]

    for idx, changes in enumerate(diffs):
        if not changes:
            continue
        record = original_records[idx]
        proposal = proposals[idx]
        logger.info("\n" + format_changes_for_log(record["citation_key"], changes))
        if diff_report and proposal:
            report_sections.append(
                format_changes_markdown(record["citation_key"], record, proposal, changes)
            )

    applied = apply_replacements(original_records, proposals)
    new_records = applied["records"]

    stats = {
        "ok": True,
        "input_file": input_file,
        "output_file": output_file,
        **shared_stats,
        "applied_replacements": applied["applied_replacements"],
    }

    # 3) Write output
    try:
        write_bib_file(output_file, new_records)
    except Exception as e:
        logger.critical(f"Writing output failed for {output_file}: {e}")
        return {**stats, "ok": False, "error": "write_failed", "failures": stats.get("failures", 0) + 1}

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
