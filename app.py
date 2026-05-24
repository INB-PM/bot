from pathlib import Path

from flask import Flask, render_template
import json

import extract_links
import extract_h1
from scheduler import start_scheduler

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


def _load_json(path: Path):

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def home():

    return render_template(
        "index.html",
        data=_load_json(OUTPUT_DIR / "h1_tags.json"),
        error=None
    )

@app.route("/run")
def run_scraper():

    try:

        extract_links.run()
        extract_h1.run()
        data = _load_json(OUTPUT_DIR / "h1_tags.json")

    except Exception as exc:

        return render_template(
            "index.html",
            data=_load_json(OUTPUT_DIR / "h1_tags.json"),
            error=str(exc)
        ), 503

    return render_template(
        "index.html",
        data=data,
        error=None
    )

if __name__ == "__main__":

    start_scheduler()
    app.run(debug=True)
