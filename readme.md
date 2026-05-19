I made this script because my supervisor told me that I should use DBLP to cite my sources instead of arXiv. 
But at that point I was already 50 citations deep and I could either spend hours making a script to automate this or I could spend hours going back and forth between my citations and DBLP, so here we are.
Please let me know if you have any issues with using this script.

# Usage
```bash
pip install -r requirements.txt
python main.py <bibtexfile.bib>
```

# Module boundaries
- `transform_service.py`: shared transformation core used by both interfaces. It owns:
  - proposal generation (`generate_proposals`)
  - replacement application (`apply_replacements`)
  - diff generation (`generate_diff`)
- `pipeline.py`: CLI orchestration only (parse/write files, logging, optional markdown report). Business transformation logic is delegated to `transform_service.py`.
- `review_logic.py`: web orchestration helpers for Flask routes (`build_review_state`, `finalize_records`) that also delegate transformation behavior to `transform_service.py`.
- `app.py`: Flask transport/controller layer only (request handling, session persistence, rendering, download response).
