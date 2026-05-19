from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from dblp_api import find_dblp_citation
from transform_service import apply_replacements, generate_proposals


def build_review_state(records: List[Dict[str, Any]], lookup_fn=None) -> Dict[str, Any]:
    if lookup_fn is None:
        lookup_fn = find_dblp_citation
    result = generate_proposals(records, lookup_fn)
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



def generate_review_proposals(records: List[Dict[str, Any]], lookup_service) -> tuple[List[Optional[Dict[str, Any]]], List[Optional[Dict[str, Any]]]]:
    """Backward-compatible adapter used by legacy tests/callers."""
    arxiv_ids = [r.get("arxiv_id") or (r.get("fields") or {}).get("eprint") for r in records]
    keys = [r.get("citation_key") for r in records]

    extracted_ids = []
    from parser import extract_arxiv_id
    for rec, aid in zip(records, arxiv_ids):
        fields = rec.get("fields") or {}
        extracted_ids.append(extract_arxiv_id(fields.get("url"), fields.get("doi"), fields.get("eprint"), fields.get("note")) if not rec.get("arxiv_id") else rec.get("arxiv_id"))

    proposals = lookup_service.lookup_many(extracted_ids, keys)
    changes = []
    from diff import compute_diff
    for rec, prop in zip(records, proposals):
        changes.append(compute_diff(rec, prop) if prop else None)
    return proposals, changes
