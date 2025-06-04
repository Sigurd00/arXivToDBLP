from flask import Flask, request, render_template, send_file
from parser import parse_bib_file, write_bib_file
from dblp_api import find_dblp_citation
from logger import logger
import os
import tempfile

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded_file = request.files.get("bibfile")
        if not uploaded_file or not uploaded_file.filename.endswith(".bib"):
            return "Please upload a valid .bib file", 400

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".bib") as temp_in:
                uploaded_file.save(temp_in.name)
                records = parse_bib_file(temp_in.name)

            new_records = []
            for record in records:
                if record['from_arxiv'] and record['arxiv_id']:
                    logger.info(f"Processing: {record['fields'].get('title', 'Unknown')}")
                    dblp = find_dblp_citation(record['arxiv_id'], record['citation_key'])
                    new_records.append(dblp if dblp else record)
                else:
                    new_records.append(record)

            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".bib").name
            write_bib_file(output_path, new_records)

            return send_file(output_path, as_attachment=True, download_name="converted.bib")

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return f"Error: {e}", 500

    return render_template("index.html")

if __name__ == "__main__":
    logger.info("Running arXivToDblp as a webapp")
    app.run(debug=True)
