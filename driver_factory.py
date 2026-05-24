"""
driver_factory.py — Reusable Selenium Chrome driver factory.

Deployment-specific change: This module centralises all Chrome/Selenium
setup so that extract_links.py and extract_h1.py do not duplicate driver
configuration.  It detects whether the app is running on Render (or any
Linux host) and applies the headless, sandbox-free options required there,
while leaving Windows local behaviour completely unchanged.

Environment detection logic:
  - If the RENDER environment variable is set (Render injects it automatically)
    OR the platform is Linux, treat the environment as a deployment host.
  - Otherwise, assume a local Windows developer machine and use the default
    Chrome installation via webdriver-manager, exactly as before.
"""

import os
import platform
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


def _is_render_or_linux() -> bool:
    """
    Return True when running on Render or any Linux host.

    Render sets the RENDER environment variable automatically.
    The platform check catches other Linux CI/CD environments.
    """
    # RENDER env var is injected by Render for every service
    if os.environ.get("RENDER"):
        return True
    # Fallback: detect Linux platform (covers Docker, CI, etc.)
    if platform.system().lower() == "linux":
        return True
    return False


def create_driver() -> webdriver.Chrome:
    """
    Create and return a configured Chrome WebDriver.

    Local Windows:
        Uses webdriver-manager to locate/download the matching ChromeDriver.
        No special Chrome options — behaves exactly as the original code did.

    Render / Linux:
        Uses the system Chrome binary installed by render-build.sh.
        Applies headless and sandbox-free options required for a server
        environment without a display.

    Returns
    -------
    webdriver.Chrome
        A ready-to-use Chrome driver instance.  The caller is responsible
        for calling driver.quit() when finished.
    """
    chrome_options = Options()

    if _is_render_or_linux():
        # ------------------------------------------------------------------ #
        # Deployment-specific Chrome options (Render / Linux only)           #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: configuring Chrome for Render/Linux environment")

        # Run without a display — required on headless servers
        chrome_options.add_argument("--headless=new")

        # Required in Docker / Render containers (no kernel namespace support)
        chrome_options.add_argument("--no-sandbox")

        # /dev/shm is often too small in containers; use /tmp instead
        chrome_options.add_argument("--disable-dev-shm-usage")

        # GPU acceleration is unavailable on headless servers
        chrome_options.add_argument("--disable-gpu")

        # Set a consistent viewport so page layout is predictable
        chrome_options.add_argument("--window-size=1920,1080")

        # Disable extensions and background networking to reduce resource use
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-networking")

        # Point to the system Chrome installed by render-build.sh
        # The CHROME_BIN env var lets operators override the path if needed.
        chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome-stable")
        chrome_options.binary_location = chrome_bin
        logger.info(f"driver_factory: using Chrome binary at {chrome_bin}")

        # Use the system ChromeDriver installed alongside Chrome.
        # CHROMEDRIVER_PATH can be overridden via environment variable.
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
        service = Service(chromedriver_path)

    else:
        # ------------------------------------------------------------------ #
        # Local Windows — original behaviour, completely unchanged            #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: configuring Chrome for local Windows environment")

        # webdriver-manager downloads the correct ChromeDriver automatically,
        # matching the locally installed Chrome version — same as before.
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver
