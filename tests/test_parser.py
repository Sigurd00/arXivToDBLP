import os
import tempfile
import unittest

from parser import parse_bib_file


class ParserFixtureTests(unittest.TestCase):
    def _write_tmp(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix='.bib', text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_malformed_bibtex_keeps_valid_entries_and_marks_arxiv_fields(self):
        path = self._write_tmp(
            """
@article{good,
  title={Good Entry},
  url={https://arxiv.org/abs/1234.5678}
}
@article{broken
  title={Missing comma and braces}

@misc{also_good,
  title={Second Entry},
  note={arXiv:2401.99999}
}
"""
        )
        parsed = parse_bib_file(path)

        self.assertGreaterEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['citation_key'], 'good')
        self.assertTrue(parsed[0]['from_arxiv'])
        self.assertEqual(parsed[0]['arxiv_id'], '1234.5678')

    def test_complex_bibtex_normalizes_type_and_extracts_arxiv(self):
        path = self._write_tmp(
            """
@InProceedings{complex_key,
  title={A Complex Entry},
  journal={ArXiv preprint arXiv:2101.00001},
  volume={arXiv:2101.00001},
  author={Doe, Jane and Roe, Richard}
}
@weirdtype{odd,
  title={Unknown Type},
  url={https://arxiv.org/pdf/2202.12345}
}
"""
        )
        parsed = parse_bib_file(path)
        self.assertEqual(len(parsed), 2)

        self.assertEqual(parsed[0]['type'], 'inproceedings')
        self.assertTrue(parsed[0]['from_arxiv'])
        self.assertEqual(parsed[0]['arxiv_id'], '2101.00001')

        self.assertEqual(parsed[1]['type'], 'misc')
        self.assertTrue(parsed[1]['from_arxiv'])
        self.assertEqual(parsed[1]['arxiv_id'], '2202.12345')


if __name__ == '__main__':
    unittest.main()
