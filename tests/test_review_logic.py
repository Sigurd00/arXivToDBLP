import unittest
from unittest.mock import patch

from review_logic import build_proposals, apply_accepted_proposals


class ReviewLogicTests(unittest.TestCase):
    def test_build_proposals_generates_diff_for_arxiv_match(self):
        records = [
            {
                "type": "article",
                "citation_key": "k1",
                "fields": {
                    "title": "Test",
                    "url": "https://arxiv.org/abs/1234.5678",
                },
            }
        ]

        dblp_rec = {
            "type": "inproceedings",
            "citation_key": "k1",
            "fields": {"title": "Test Updated", "author": "A. Author"},
        }

        with patch("review_logic.find_dblp_citation", return_value=dblp_rec):
            proposals, changes = build_proposals(records)

        self.assertEqual(proposals, [dblp_rec])
        self.assertIsNotNone(changes[0])
        self.assertIn("modified", changes[0])

    def test_build_proposals_ignores_records_without_arxiv_id(self):
        records = [
            {
                "type": "article",
                "citation_key": "k2",
                "fields": {"title": "No arxiv", "url": "https://example.com"},
            }
        ]

        with patch("review_logic.find_dblp_citation") as mocked:
            proposals, changes = build_proposals(records)

        mocked.assert_not_called()
        self.assertEqual(proposals, [None])
        self.assertEqual(changes, [None])

    def test_apply_accepted_proposals_replaces_only_selected_valid_indices(self):
        records = [
            {"citation_key": "a", "fields": {"title": "old-a"}},
            {"citation_key": "b", "fields": {"title": "old-b"}},
        ]
        proposals = [
            {"citation_key": "a", "fields": {"title": "new-a"}},
            None,
        ]

        final_records, replaced = apply_accepted_proposals(records, proposals, {0, 1, 999})

        self.assertEqual(replaced, 1)
        self.assertEqual(final_records[0]["fields"]["title"], "new-a")
        self.assertEqual(final_records[1]["fields"]["title"], "old-b")


if __name__ == "__main__":
    unittest.main()
