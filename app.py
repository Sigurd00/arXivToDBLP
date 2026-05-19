from __future__ import annotations
import os
import json
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from flask import (
    Flask, request, render_template, send_file, redirect, url_for, flash
)
from parser import parse_bib_file, write_bib_file, extract_arxiv_id
from dblp_api import find_dblp_citation
from diff import compute_diff
from logger import logger
from errors import LookupFailure

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
STATE_DIR = os.path.join(tempfile.gettempdir(), "bibdiff_state")
os.makedirs(STATE_DIR, exist_ok=True)


def _state_path(token: str) -> str:
    return os.path.join(STATE_DIR, f"{token}.json")


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/review", methods=["POST"])
def review():
    uploaded_file = request.files.get("bibfile")
    if not uploaded_file or not uploaded_file.filename.endswith(".bib"):
        flash("Please upload a valid .bib file (.bib).", "error")
        return redirect(url_for("home"))

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bib") as tmp:
            uploaded_path = tmp.name
            uploaded_file.save(uploaded_path)

        records = parse_bib_file(uploaded_path) or []

        proposals: List[Optional[Dict[str, Any]]] = []
        changes: List[Optional[Dict[str, Any]]] = []
        failures = 0
        no_match = 0

        for rec in records:
            fields = rec.get("fields") or {}
            arxiv_id = extract_arxiv_id(fields.get("url"), fields.get("doi"), fields.get("eprint"), fields.get("note"))
            if not arxiv_id:
                proposals.append(None)
                changes.append(None)
                no_match += 1
                continue

            try:
                dblp_rec = find_dblp_citation(arxiv_id, rec.get("citation_key"))
            except LookupFailure as e:
                failures += 1
                logger.error("lookup_failed", extra={"citation_key": rec.get("citation_key"), "arxiv_id": arxiv_id, "stage": "lookup", "exception_type": type(e).__name__})
                flash(f"Lookup failed for {rec.get('citation_key')}; original entry kept.", "warning")
                proposals.append(None)
                changes.append(None)
                continue

            if not dblp_rec:
                proposals.append(None)
                changes.append(None)
                no_match += 1
                continue

            diff = compute_diff(rec, dblp_rec)
            if not diff:
                proposals.append(None)
                changes.append(None)
                no_match += 1
                continue

            proposals.append(dblp_rec)
            changes.append(diff)

        token = uuid.uuid4().hex
        state = {"records": records, "proposals": proposals, "changes": changes}
        with open(_state_path(token), "w", encoding="utf-8") as f:
            json.dump(state, f)

        totals = {
            "total": len(records),
            "candidates": sum(1 for r in records if r.get("arxiv_id")),
            "replaced": sum(1 for p in proposals if p),
            "no_match": no_match,
            "failures": failures,
        }

        return render_template("review.html", token=token, records=records, proposals=proposals, changes=changes, totals=totals)

    except Exception as e:
        logger.error("review_failed", extra={"stage": "review", "exception_type": type(e).__name__})
        flash("Could not process the uploaded file. Please verify BibTeX syntax and retry.", "error")
        return redirect(url_for("home"))


@app.route("/finalize", methods=["POST"])
def finalize():
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
        final_records: List[Dict[str, Any]] = []
        replaced = 0
        for idx, rec in enumerate(records):
            if idx in accepted_indices and idx < len(proposals) and proposals[idx]:
                final_records.append(proposals[idx])
                replaced += 1
            else:
                final_records.append(rec)

        out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".bib").name
        write_bib_file(out_path, final_records)
        logger.info("finalize_complete", extra={"stage": "finalize", "replaced": replaced, "total": len(records)})
        try:
            os.remove(state_path)
        except OSError:
            pass

        return send_file(out_path, as_attachment=True, download_name="converted.bib")

    except Exception as e:
        logger.error("finalize_failed", extra={"stage": "finalize", "exception_type": type(e).__name__})
        flash("Could not generate output file. Please retry.", "error")
        return redirect(url_for("home"))


if __name__ == "__main__":
    logger.info("Running BibTeX DBLP web UI")
    app.run(debug=True)
