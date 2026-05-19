from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from diff import compute_diff

Record = Dict[str, Any]
Proposal = Optional[Record]
DiffResult = Optional[Dict[str, Any]]
LookupFn = Callable[[str, Optional[str]], Proposal]


def generate_proposals(records: Sequence[Record], lookup_fn: LookupFn) -> Dict[str, Any]:
    proposals: List[Proposal] = []
    diffs: List[DiffResult] = []
    stats = {
        "total_records": len(records),
        "candidate_records": 0,
        "proposed_replacements": 0,
        "unchanged_records": 0,
        "no_match_records": 0,
        "diff_records": 0,
    }

    for rec in records:
        from_arxiv = rec.get("from_arxiv")
        arxiv_id = rec.get("arxiv_id")
        if not (from_arxiv and arxiv_id):
            proposals.append(None)
            diffs.append(None)
            continue

        stats["candidate_records"] += 1
        dblp_rec = lookup_fn(arxiv_id, rec.get("citation_key"))
        if not dblp_rec:
            proposals.append(None)
            diffs.append(None)
            stats["no_match_records"] += 1
            continue

        diff = compute_diff(rec, dblp_rec)
        proposals.append(dblp_rec)
        diffs.append(diff)
        stats["proposed_replacements"] += 1
        if diff:
            stats["diff_records"] += 1
        else:
            stats["unchanged_records"] += 1

    stats["skipped_records"] = stats["total_records"] - stats["candidate_records"]

    return {"proposals": proposals, "diffs": diffs, "stats": stats}


def apply_replacements(
    records: Sequence[Record],
    proposals: Sequence[Proposal],
    accepted_indices: Optional[Set[int]] = None,
) -> Dict[str, Any]:
    final_records: List[Record] = []
    applied = 0

    for idx, rec in enumerate(records):
        proposal = proposals[idx] if idx < len(proposals) else None
        should_apply = proposal is not None and (accepted_indices is None or idx in accepted_indices)
        if should_apply:
            final_records.append(proposal)
            applied += 1
        else:
            final_records.append(rec)

    return {
        "records": final_records,
        "applied_replacements": applied,
        "total_records": len(records),
    }


def generate_diff(record: Record, proposal: Record) -> DiffResult:
    return compute_diff(record, proposal)
