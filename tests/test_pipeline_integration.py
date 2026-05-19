import unittest
from unittest.mock import patch

from parser import extract_arxiv_id
from dblp_api import find_dblp_citation


class TestArxivExtraction(unittest.TestCase):
    def test_extracts_modern_id_with_version(self):
        value = "https://arxiv.org/abs/2101.00001v2"
        self.assertEqual(extract_arxiv_id(value), "2101.00001")

    def test_extracts_legacy_id(self):
        value = "arXiv:cs/9901001"
        self.assertEqual(extract_arxiv_id(value), "cs/9901001")


class TestDblpHitParsing(unittest.TestCase):
    @patch("dblp_api.try_fetch_from_dblp")
    def test_handles_single_hit_dict(self, mock_fetch):
        mock_fetch.return_value = {
            "result": {
                "hits": {
                    "@total": "1",
                    "hit": {
                        "info": {
                            "type": "article",
                            "title": "Demo",
                            "year": "2024",
                            "authors": {"author": [{"text": "Jane Doe"}]},
                        }
                    },
                }
            }
        }

        citation = find_dblp_citation("2101.00001", "mykey")
        self.assertIsNotNone(citation)
        self.assertEqual(citation["citation_key"], "mykey")
        self.assertEqual(citation["type"], "article")
        self.assertEqual(citation["fields"]["title"], "Demo")
        self.assertEqual(citation["fields"]["author"], "Jane Doe")


if __name__ == "__main__":
    unittest.main()
