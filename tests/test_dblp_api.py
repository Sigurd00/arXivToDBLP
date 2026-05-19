import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unittest.mock import patch

from dblp_api import find_dblp_citation


def _make_hit(title, year, ee=None, venue="TestConf", authors=None, record_type="article"):
    if authors is None:
        authors = [{"text": "Alice"}, {"text": "Bob"}]
    payload = {
        "title": title,
        "year": year,
        "venue": venue,
        "type": record_type,
        "authors": {"author": authors},
    }
    if ee is not None:
        payload["ee"] = ee
    return {"info": payload}


def test_find_dblp_citation_selects_candidate_with_matching_arxiv_id():
    mocked_response = {
        "result": {
            "hits": {
                "@total": "3",
                "hit": [
                    _make_hit("A Different Paper", "2020", ee="https://arxiv.org/abs/1111.1111"),
                    _make_hit("Target Paper", "2021", ee="https://arxiv.org/abs/1234.5678v2"),
                    _make_hit("Totally Unrelated", "2021"),
                ],
            }
        }
    }

    with patch("dblp_api.try_fetch_from_dblp", return_value=mocked_response):
        citation = find_dblp_citation("1234.5678", "origKey")

    assert citation is not None
    assert citation["citation_key"] == "origKey"
    assert citation["fields"]["title"] == "Target Paper"


def test_find_dblp_citation_returns_none_when_no_candidate_matches_and_threshold_high():
    mocked_response = {
        "result": {
            "hits": {
                "@total": "2",
                "hit": [
                    _make_hit("Completely Different One", "2021", ee="https://arxiv.org/abs/9999.0001"),
                    _make_hit("Another Unrelated Work", "2022"),
                ],
            }
        }
    }

    with patch("dblp_api.try_fetch_from_dblp", return_value=mocked_response):
        citation = find_dblp_citation("1234.5678", "origKey", min_confidence=0.7)

    assert citation is None
