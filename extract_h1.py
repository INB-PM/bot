from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import json
import time


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


def run():

    with (OUTPUT_DIR / "links.json").open(
        "r",
        encoding="utf-8"
    ) as f:

        links_data = json.load(f)

    driver = webdriver.Chrome(
        service=Service(
            ChromeDriverManager().install()
        )
    )

    result = []

    for item in links_data:

        url = item["link"]

        try:

            driver.get(url)

            time.sleep(2)

            h1_tags = driver.find_elements(
                By.TAG_NAME,
                "h1"
            )

            h1_texts = []

            for h1 in h1_tags:

                text = h1.text.strip()

                if text:

                    h1_texts.append(text)

            result.append({
                "url": url,
                "h1": h1_texts
            })

            print(f"Done: {url}")

        except Exception as e:

            result.append({
                "url": url,
                "error": str(e)
            })

            print(f"Error: {url}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with (OUTPUT_DIR / "h1_tags.json").open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=4,
            ensure_ascii=False
        )

    print("H1 tags saved successfully")

    driver.quit()
