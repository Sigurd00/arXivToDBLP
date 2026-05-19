import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import io
from unittest.mock import patch, Mock
import requests

import app as webapp
from errors import LookupFailure
from pipeline import run_flow
from dblp_api import try_fetch_from_dblp


def test_pipeline_parse_failure():
    with patch("pipeline.parse_bib_file", side_effect=ValueError("bad bib")):
        stats = run_flow("in.bib", "out.bib")
    assert stats["ok"] is False
    assert stats["error"] == "parse_failed"
    assert stats["failures"] == 1


def test_pipeline_write_failure(tmp_path):
    records = [{"type": "article", "citation_key": "k1", "fields": {}, "from_arxiv": False, "arxiv_id": ""}]
    with patch("pipeline.parse_bib_file", return_value=records), patch("pipeline.write_bib_file", side_effect=OSError("disk full")):
        stats = run_flow("in.bib", str(tmp_path / "out.bib"))
    assert stats["ok"] is False
    assert stats["error"] == "write_failed"
    assert stats["failures"] == 1


def test_pipeline_lookup_failure(tmp_path):
    records = [{"type": "article", "citation_key": "k2", "fields": {}, "from_arxiv": True, "arxiv_id": "1234.5678"}]
    with patch("pipeline.parse_bib_file", return_value=records), patch("pipeline.find_dblp_citation", side_effect=LookupFailure("boom")), patch("pipeline.write_bib_file"):
        stats = run_flow("in.bib", str(tmp_path / "out.bib"))
    assert stats["ok"] is True
    assert stats["candidates"] == 1
    assert stats["failures"] == 1
    assert stats["replaced"] == 0


def test_web_review_lookup_failure_flash():
    webapp.app.config["TESTING"] = True
    client = webapp.app.test_client()

    bib = b"@article{k,\n  url={https://arxiv.org/abs/1234.5678}\n}\n"
    with patch("app.find_dblp_citation", side_effect=LookupFailure("downstream unavailable")):
        response = client.post("/review", data={"bibfile": (io.BytesIO(bib), "sample.bib")}, content_type="multipart/form-data", follow_redirects=True)

    assert response.status_code == 200
    assert b"Lookup failed for k; original entry kept." in response.data


import pytest

def test_dblp_api_failure_raises_lookup_failure():
    with patch("dblp_api.requests.get", side_effect=requests.RequestException("boom")), patch("dblp_api.time.sleep"):
        with pytest.raises(LookupFailure):
            try_fetch_from_dblp("1234.5678", max_retries=2)
