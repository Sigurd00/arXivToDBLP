import tempfile
import unittest
from unittest.mock import patch

from pipeline import run_flow


class PipelineRegressionTests(unittest.TestCase):
    @patch('pipeline.find_dblp_citation')
    @patch('pipeline.parse_bib_file')
    @patch('pipeline.write_bib_file')
    def test_no_diff_still_replaces_when_valid_dblp_match_exists(self, mock_write, mock_parse, mock_find):
        rec = {
            'type': 'article',
            'citation_key': 'k1',
            'from_arxiv': True,
            'arxiv_id': '1234.5678',
            'fields': {'title': 'Same', 'author': 'A'}
        }
        mock_parse.return_value = [rec]
        mock_find.return_value = {
            'type': 'article',
            'citation_key': 'k1',
            'fields': {'title': 'Same', 'author': 'A'}
        }

        out = tempfile.NamedTemporaryFile(delete=False, suffix='.bib').name
        stats = run_flow('in.bib', out)

        self.assertTrue(stats['ok'])
        self.assertEqual(stats['diff_count'], 0)
        self.assertEqual(stats['unchanged'], 1)
        self.assertEqual(stats['replaced'], 1)
        mock_write.assert_called_once()


if __name__ == '__main__':
    unittest.main()
