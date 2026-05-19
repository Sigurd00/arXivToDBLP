I made this script because my supervisor told me that I should use DBLP to cite my sources instead of arXiv.
But at that point I was already 50 citations deep and I could either spend hours making a script to automate this or I could spend hours going back and forth between my citations and DBLP, so here we are.
Please let me know if you have any issues with using this script.

## Usage

```bash
pip install -r requirements.txt
python main.py <bibtexfile.bib>
```

You can optionally pass:

- an explicit output file path, and
- a Markdown diff report path.

```bash
python main.py <bibtexfile.bib> <output.bib> --diff-report <report.md>
```

## Quick integration check

Use these commands to verify the full pipeline wiring before opening a PR:

```bash
python -m compileall .
python main.py --help
python diff.py --help
```

## Notes on DBLP/network access

This tool performs live lookups against `https://dblp.org`.
If your environment blocks outbound network or HTTPS proxy tunneling, replacements can fail after retries, but the pipeline still exits successfully and writes the original entries back out.
