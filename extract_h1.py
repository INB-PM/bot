from selenium.webdriver.common.by import By
import json
import time

# Deployment-specific change: driver creation is now handled by driver_factory
# so that Chrome options are configured correctly for both local Windows and
# Render/Linux without duplicating setup code here.
from driver_factory import create_driver


def run():

    with open(
        "output/links.json",
        "r"
    ) as f:

        links_data = json.load(f)

    # create_driver() returns a Chrome instance configured for the current
    # environment (headless + no-sandbox on Render, normal on Windows).
    driver = create_driver()

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

    with open(
        "output/h1_tags.json",
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
