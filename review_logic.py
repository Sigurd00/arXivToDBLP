from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from dblp_api import find_dblp_citation
from transform_service import apply_replacements, generate_proposals


def build_review_state(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = generate_proposals(records, find_dblp_citation)
    proposals = result["proposals"]
    diffs = result["diffs"]
    totals = dict(result["stats"])

    # Backward-compatible aliases for any older templates/UI wiring.
    totals["total"] = totals["total_records"]
    totals["with_proposals"] = totals["proposed_replacements"]
    totals["unchanged_or_nomatch"] = totals["total_records"] - totals["proposed_replacements"]

    return {"records": records, "proposals": proposals, "changes": diffs, "totals": totals}


def finalize_records(
    records: List[Dict[str, Any]],
    proposals: List[Optional[Dict[str, Any]]],
    accepted_indices: Set[int],
) -> Dict[str, Any]:
    return apply_replacements(records, proposals, accepted_indices)
