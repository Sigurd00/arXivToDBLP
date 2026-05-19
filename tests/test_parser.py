import tempfile
import unittest
from pathlib import Path

from parser import parse_bib_content, parse_bib_file, write_bib_file


class ParserTests(unittest.TestCase):
    def test_multiline_title_and_nested_braces(self):
        content = """@article{key1,
  title = {A multiline
    title with {Nested {Braces}} inside},
  author = {Alice}
}
"""
        entries = parse_bib_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["fields"]["title"],
            "A multiline\n    title with {Nested {Braces}} inside",
        )
        self.assertEqual(entries[0]["fields"]["author"], "Alice")

    def test_escaped_quotes_and_mixed_quoting_styles(self):
        content = r'''@misc{key2,
  title = "Quoted \"Title\" With Escapes",
  note = {brace value},
  publisher = "ACM"
}
'''
        entries = parse_bib_content(content)
        fields = entries[0]["fields"]
        self.assertEqual(fields["title"], r'Quoted \"Title\" With Escapes')
        self.assertEqual(fields["note"], "brace value")
        self.assertEqual(fields["publisher"], "ACM")

    def test_parenthesized_entry_and_trailing_comma(self):
        content = """@article(key4,
  title = {Paren style},
  year = 2024,
)
"""
        entries = parse_bib_content(content)
        self.assertEqual(entries[0]["citation_key"], "key4")
        self.assertEqual(entries[0]["fields"]["year"], "2024")

    def test_escaped_braces_do_not_break_balancing(self):
        content = r'''@inproceedings{key3,
  title = {Symbols like \{ and \} and nested {parts}},
  abstract = "Line 1\nLine 2 with \"quotes\"",
  year = 2026,
}
'''
        records = parse_bib_content(content)
        self.assertEqual(
            records[0]["fields"]["title"],
            r"Symbols like \{ and \} and nested {parts}",
        )

    def test_round_trip_keeps_semantically_important_characters(self):
        content = r'''@inproceedings{key5,
  title = {Symbols like \{ and \} and nested {parts}},
  abstract = "Line 1\nLine 2 with \"quotes\"",
  year = 2026,
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "in.bib"
            output_path = Path(tmp) / "out.bib"
            input_path.write_text(content, encoding="utf-8")

            records = parse_bib_file(input_path)
            write_bib_file(output_path, records)
            reparsed = parse_bib_file(output_path)

        self.assertEqual(records[0]["fields"], reparsed[0]["fields"])


if __name__ == "__main__":
    unittest.main()
