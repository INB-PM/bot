from flask import Flask, render_template
import json

import extract_links
import extract_h1
from scheduler import start_scheduler

app = Flask(__name__)
start_scheduler()

@app.route("/")
def home():

    return render_template(
        "index.html",
        data=None
    )

@app.route("/run")
def run_scraper():

    extract_links.run()

    extract_h1.run()

    with open(
        "output/h1_tags.json",
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    return render_template(
        "index.html",
        data=data
    )

if __name__ == "__main__":

    app.run(debug=True)