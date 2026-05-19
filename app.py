# app.py
from __future__ import annotations
import os
import json
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from flask import (
    Flask, request, render_template, send_file, redirect, url_for, flash
)
from parser import parse_bib_file, write_bib_file
from review_logic import build_review_state, finalize_records
from dblp_api import find_dblp_citation
from logger import logger

app = Flask(__name__)
# Simple secret key for flashing messages; change for production
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
# Where we stash per-upload state between steps
STATE_DIR = os.path.join(tempfile.gettempdir(), "bibdiff_state")
os.makedirs(STATE_DIR, exist_ok=True)


def _state_path(token: str) -> str:
    return os.path.join(STATE_DIR, f"{token}.json")


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/review", methods=["POST"])
def review():
    """Accept uploaded .bib, compute DBLP proposals + diffs, render review page."""
    uploaded_file = request.files.get("bibfile")
    if not uploaded_file or not uploaded_file.filename.endswith(".bib"):
        flash("Please upload a valid .bib file (.bib).", "error")
        return redirect(url_for("home"))

    try:
        # Persist upload to a temp file so the parser can read it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bib") as tmp:
            uploaded_path = tmp.name
            uploaded_file.save(uploaded_path)

        # Parse
        records = parse_bib_file(uploaded_path) or []
        logger.info(f"Parsed {len(records)} records from upload")

        review_state = build_review_state(records, lookup_fn=find_dblp_citation)
        for key in review_state["totals"].get("failure_keys", []):
            flash(f"Lookup failed for {key}; original entry kept.", "warning")

        token = uuid.uuid4().hex
        state = review_state
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(_state_path(token), "w", encoding="utf-8") as f:
            json.dump(state, f)

        return render_template(
            "review.html",
            token=token,
            records=review_state["records"],
            proposals=review_state["proposals"],
            changes=review_state["changes"],
            totals=review_state["totals"],
        )

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        flash(f"Error while processing file: {e}", "error")
        return redirect(url_for("home"))


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
            os.remove(state_path)
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
