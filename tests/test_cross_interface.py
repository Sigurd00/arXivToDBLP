import unittest
from unittest.mock import patch

from transform_service import generate_proposals, apply_replacements
from review_logic import build_review_state, finalize_records


def _fixture_records():
    return [
        {
            "type": "article",
            "citation_key": "k1",
            "fields": {"title": "Paper A", "url": "https://arxiv.org/abs/1234.5678"},
            "from_arxiv": True,
            "arxiv_id": "1234.5678",
        },
        {
            "type": "article",
            "citation_key": "k2",
            "fields": {"title": "Paper B"},
            "from_arxiv": False,
            "arxiv_id": "",
        },
    ]


def _lookup(arxiv_id, citation_key):
    if arxiv_id == "1234.5678":
        return {
            "type": "inproceedings",
            "citation_key": citation_key,
            "fields": {"title": "Paper A Updated", "year": "2024"},
        }
    return None


class CrossInterfaceTests(unittest.TestCase):
    def test_cli_and_web_share_proposal_outputs(self):
        records = _fixture_records()

        cli_result = generate_proposals(records, _lookup)

        with patch("review_logic.find_dblp_citation", side_effect=_lookup):
            web_state = build_review_state(records)

        self.assertEqual(cli_result["proposals"], web_state["proposals"])
        self.assertEqual(cli_result["diffs"], web_state["changes"])
        self.assertEqual(cli_result["stats"], {k: web_state["totals"][k] for k in cli_result["stats"]})
        self.assertEqual(web_state["totals"]["total"], cli_result["stats"]["total_records"])
        self.assertEqual(web_state["totals"]["with_proposals"], cli_result["stats"]["proposed_replacements"])

    def test_cli_and_web_share_replacement_application(self):
        records = _fixture_records()
        proposals = generate_proposals(records, _lookup)["proposals"]
        accepted = {0}

        cli_final = apply_replacements(records, proposals, accepted)
        web_final = finalize_records(records, proposals, accepted)

        self.assertEqual(cli_final, web_final)


if __name__ == "__main__":
    unittest.main()
