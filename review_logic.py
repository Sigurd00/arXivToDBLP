from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from parser import extract_arxiv_id
from dblp_api import find_dblp_citation
from diff import compute_diff


def build_proposals(records: Sequence[Dict[str, Any]]) -> Tuple[List[Optional[Dict[str, Any]]], List[Optional[Dict[str, Any]]]]:
    """Build DBLP replacement proposals and field-level diffs for parsed BibTeX records."""
    proposals: List[Optional[Dict[str, Any]]] = []
    changes: List[Optional[Dict[str, Any]]] = []

    for rec in records:
        fields = rec.get("fields") or {}
        arxiv_id = extract_arxiv_id(
            fields.get("url"),
            fields.get("doi"),
            fields.get("eprint"),
            fields.get("note"),
        )
        if not arxiv_id:
            proposals.append(None)
            changes.append(None)
            continue

        dblp_rec = find_dblp_citation(arxiv_id, rec.get("citation_key"))
        if not dblp_rec:
            proposals.append(None)
            changes.append(None)
            continue

        diff = compute_diff(rec, dblp_rec)
        if not diff:
            proposals.append(None)
            changes.append(None)
            continue

        proposals.append(dblp_rec)
        changes.append(diff)

    return proposals, changes


def apply_accepted_proposals(
    records: Sequence[Dict[str, Any]],
    proposals: Sequence[Optional[Dict[str, Any]]],
    accepted_indices: Set[int],
) -> Tuple[List[Dict[str, Any]], int]:
    """Return finalized records with selected proposals applied, plus replacement count."""
    final_records: List[Dict[str, Any]] = []
    replaced = 0

    for idx, rec in enumerate(records):
        if idx in accepted_indices and idx < len(proposals) and proposals[idx]:
            final_records.append(proposals[idx])
            replaced += 1
        else:
            final_records.append(rec)

    return final_records, replaced
