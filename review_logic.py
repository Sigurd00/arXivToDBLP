from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from dblp_api import DblpLookupService
from diff import compute_diff
from parser import extract_arxiv_id


def generate_review_proposals(
    records: List[Dict[str, Any]],
    lookup_service: Optional[DblpLookupService] = None,
) -> Tuple[List[Optional[Dict[str, Any]]], List[Optional[Dict[str, Any]]]]:
    """Generate DBLP replacement proposals and diffs for review UI.

    Returns two arrays aligned to input record ordering:
      - proposals[idx] is a DBLP record or None
      - changes[idx] is a diff dict or None
    """
    service = lookup_service or DblpLookupService()

    # Extract arXiv IDs once and preserve positional order for deterministic output.
    arxiv_ids: List[Optional[str]] = []
    original_keys: List[Optional[str]] = []
    for rec in records:
        fields = rec.get("fields") or {}
        arxiv_ids.append(
            extract_arxiv_id(
                fields.get("url"),
                fields.get("doi"),
                fields.get("eprint"),
                fields.get("note"),
            )
        )
        original_keys.append(rec.get("citation_key"))

    looked_up = service.lookup_many(arxiv_ids, original_keys)

    proposals: List[Optional[Dict[str, Any]]] = []
    changes: List[Optional[Dict[str, Any]]] = []

    for rec, dblp_rec in zip(records, looked_up):
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
