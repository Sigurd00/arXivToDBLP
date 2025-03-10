I made this script because my supervisor told me that I should use DBLP to cite my sources instead of arXiv. 
But at that point I was already 50 citations deep and I could either spend hours making a script to automate this or I could spend hours going back and forth between my citations and DBLP, so here we are.

Currently working on authors field. Some citations have "author" others have "authors" This should be consolidated.

If you find errors in the translation from arxiv to dblp citation, please let me know.

# Usage
```bash
pip install -r requirements.txt
python main.py <bibtexfile.bib>
```