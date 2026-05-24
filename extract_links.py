from selenium.webdriver.common.by import By
import json

# Deployment-specific change: driver creation is now handled by driver_factory
# so that Chrome options are configured correctly for both local Windows and
# Render/Linux without duplicating setup code here.
from driver_factory import create_driver


def run():

    # create_driver() returns a Chrome instance configured for the current
    # environment (headless + no-sandbox on Render, normal on Windows).
    driver = create_driver()

    websites = [
        "https://bon-news-alpha.vercel.app/",
        "https://new-web-exp.vercel.app/",
        "https://textutils-3i6y.onrender.com/",
    ]

    blocked_domains = [
        "https://bon-news-alpha.vercel.app",
        "https://new-web-exp.vercel.app/",
        "https://textutils-3i6y.onrender.com",
    ]

    data = []

    for website in websites:

        driver.get(website)

        links = driver.find_elements(
            By.TAG_NAME,
            "a"
        )

        for link in links:

            href = link.get_attribute("href")

            # Skip empty links
            if not href:
                continue

            # Skip invalid links
            if href == "//":
                continue

            blocked = False

            # Remove only internal website links
            for domain in blocked_domains:

                if href.startswith(domain):

                    blocked = True
                    break

            if not blocked:

                data.append({
                    "link": href
                })

    with open(
        "output/links.json",
        "w"
    ) as f:

        json.dump(
            data,
            f,
            indent=4
        )

    print("Links saved successfully")

    driver.quit()
