# app.py
from __future__ import annotations
import os
import json
import tempfile
import uuid
import threading
import time
from typing import Any, Dict, List, Optional

from flask import (
    Flask, request, render_template, send_file, redirect, url_for, flash, jsonify
)
from parser import parse_bib_file, write_bib_file
from review_logic import build_review_state, finalize_records
from dblp_api import find_dblp_citation, ensure_local_dblp_dataset_fresh
from logger import logger

app = Flask(__name__)
# Simple secret key for flashing messages; change for production
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
# Where we stash per-upload state between steps
STATE_DIR = os.path.join(tempfile.gettempdir(), "bibdiff_state")
os.makedirs(STATE_DIR, exist_ok=True)
_STATE_IO_LOCK = threading.Lock()


def _state_path(token: str) -> str:
    return os.path.join(STATE_DIR, f"{token}.json")




def _write_state(token: str, state: Dict[str, Any]) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    path = _state_path(token)
    tmp_path = f"{path}.tmp"
    with _STATE_IO_LOCK:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f)

        # On Windows, replacing a file can fail transiently if another
        # reader has the destination file open. Retry briefly.
        last_err: Optional[Exception] = None
        for _ in range(6):
            try:
                os.replace(tmp_path, path)
                return
            except PermissionError as e:
                last_err = e
                time.sleep(0.05)

        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        if last_err:
            raise last_err


def _read_state(token: str) -> Optional[Dict[str, Any]]:
    state_path = _state_path(token)
    if not os.path.exists(state_path):
        return None
    with _STATE_IO_LOCK:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)


def _process_review_job(token: str) -> None:
    try:
        state = _read_state(token)
        if not state:
            return

        records: List[Dict[str, Any]] = state.get("records") or []
        proposals: List[Optional[Dict[str, Any]]] = [None] * len(records)
        changes: List[Optional[Dict[str, Any]]] = [None] * len(records)

        total_candidates = 0
        completed_candidates = 0
        for rec in records:
            if rec.get("from_arxiv") and rec.get("arxiv_id"):
                total_candidates += 1

        state["status"] = "running"
        state["progress"] = {"total_candidates": total_candidates, "completed_candidates": 0}
        _write_state(token, state)
        try:
            ensure_local_dblp_dataset_fresh()
        except Exception as e:
            logger.warning(f"Could not refresh local DBLP dataset, falling back to API: {e}")

        from diff import compute_diff

        for idx, rec in enumerate(records):
            if not (rec.get("from_arxiv") and rec.get("arxiv_id")):
                continue

            arxiv_id = rec.get("arxiv_id")
            citation_key = rec.get("citation_key")
            rec["lookup_status"] = "running"
            _write_state(token, state)
            try:
                proposal = find_dblp_citation(arxiv_id, citation_key)
            except Exception:
                proposal = None
                rec["lookup_status"] = "failed"
            else:
                rec["lookup_status"] = "found" if proposal else "no_match"

            proposals[idx] = proposal
            changes[idx] = compute_diff(rec, proposal) if proposal else None

            completed_candidates += 1
            state["progress"] = {"total_candidates": total_candidates, "completed_candidates": completed_candidates}
            state["proposals"] = proposals
            state["changes"] = changes
            _write_state(token, state)

        review_state = build_review_state(records, lookup_fn=lambda a, b: None)
        totals = dict(review_state["totals"])
        totals["with_proposals"] = sum(1 for p in proposals if p)
        totals["unchanged_or_nomatch"] = totals["total"] - totals["with_proposals"]
        totals["no_match_records"] = sum(1 for r in records if r.get("lookup_status") in ("no_match", "failed"))

        state["status"] = "done"
        state["proposals"] = proposals
        state["changes"] = changes
        state["totals"] = totals
        _write_state(token, state)
    except Exception as e:
        logger.exception(f"Review job failed for token {token}: {e}")
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/review", methods=["POST"])
def review():
    """Accept uploaded .bib and start async DBLP lookup job."""
    uploaded_file = request.files.get("bibfile")
    if not uploaded_file or not uploaded_file.filename.endswith(".bib"):
        flash("Please upload a valid .bib file (.bib).", "error")
        return redirect(url_for("home"))

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bib") as tmp:
            uploaded_path = tmp.name
            uploaded_file.save(uploaded_path)

        records = parse_bib_file(uploaded_path) or []
        logger.info(f"Parsed {len(records)} records from upload")

        token = uuid.uuid4().hex
        state = {
            "status": "queued",
            "records": records,
            "proposals": [None] * len(records),
            "changes": [None] * len(records),
            "progress": {"total_candidates": 0, "completed_candidates": 0},
            "totals": {"total": len(records), "with_proposals": 0, "unchanged_or_nomatch": len(records)},
        }
        _write_state(token, state)

        thread = threading.Thread(target=_process_review_job, args=(token,), daemon=True)
        thread.start()

        return redirect(url_for("review_page", token=token))

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        flash(f"Error while processing file: {e}", "error")
        return redirect(url_for("home"))


@app.route("/review/<token>", methods=["GET"])
def review_page(token: str):
    state = _read_state(token)
    if not state:
        flash("Review session expired. Please re-upload.", "error")
        return redirect(url_for("home"))

    return render_template("review.html", token=token)


@app.route("/review_status/<token>", methods=["GET"])
def review_status(token: str):
    state = _read_state(token)
    if not state:
        return jsonify({"error": "expired"}), 404
    return jsonify(state)


@app.route("/finalize", methods=["POST"])
def finalize():
    """Build the final .bib based on which entries the user accepted."""
    token = request.form.get("token")
    if not token:
        flash("Missing review token.", "error")
        return redirect(url_for("home"))

    state_path = _state_path(token)
    if not os.path.exists(state_path):
        flash("Review session expired. Please re-upload.", "error")
        return redirect(url_for("home"))

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        records: List[Dict[str, Any]] = state.get("records") or []
        proposals: List[Optional[Dict[str, Any]]] = state.get("proposals") or []

        accepted_indices = set(int(i) for i in request.form.getlist("accept"))
        logger.info(f"User accepted {len(accepted_indices)} proposed replacements")

        finalize_result = finalize_records(records, proposals, accepted_indices)
        final_records = finalize_result["records"]

        # Stream output .bib
        out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".bib").name
        write_bib_file(out_path, final_records)
        logger.info(f"Wrote output with {finalize_result['applied_replacements']} replacements (of {len(records)} total)")
        # Best-effort cleanup
        try:
            os.remove(_state_path(token))
        except OSError:
            pass

        return send_file(out_path, as_attachment=True, download_name="converted.bib")

    except Exception as e:
        logger.error(f"Finalize failed: {e}")
        flash(f"Finalize failed: {e}", "error")
        return redirect(url_for("home"))


if __name__ == "__main__":
    logger.info("Running BibTeX DBLP web UI")
    app.run(debug=True)
