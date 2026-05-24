"""
driver_factory.py — Reusable Selenium Chrome driver factory.

Works on both local Windows and Render/Linux without hardcoding paths.

Strategy:
  - webdriver-manager is used in BOTH environments to locate/download
    ChromeDriver automatically.  This avoids any assumption about where
    ChromeDriver is installed on the host.
  - On Render/Linux, headless + sandbox-free Chrome options are added so
    the browser can run without a display.
  - On Windows, no extra options are applied — behaviour is identical to
    the original code.
  - If a CHROME_BIN environment variable is set, that path is used as the
    Chrome binary location (useful when Chrome is not on PATH).
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
    """Return True when running on Render or any Linux host."""
    # Render injects the RENDER env var automatically for every service
    if os.environ.get("RENDER"):
        return True
    # Fallback: detect Linux (covers Docker, CI, other cloud hosts)
    if platform.system().lower() == "linux":
        return True
    return False


def create_driver() -> webdriver.Chrome:
    """
    Create and return a configured Chrome WebDriver.

    Both environments use webdriver-manager to locate ChromeDriver so there
    is no dependency on a specific filesystem path.  The only difference
    between environments is the set of Chrome options applied.

    Returns
    -------
    webdriver.Chrome
        A ready-to-use Chrome driver instance.  The caller is responsible
        for calling driver.quit() when finished.
    """
    chrome_options = Options()

    if _is_render_or_linux():
        # ------------------------------------------------------------------ #
        # Render / Linux — headless, sandbox-free options                    #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: Linux/Render environment detected")

        # Run without a display — required on headless servers
        chrome_options.add_argument("--headless=new")

        # Required in containers — no kernel namespace support
        chrome_options.add_argument("--no-sandbox")

        # /dev/shm is often too small in containers; fall back to /tmp
        chrome_options.add_argument("--disable-dev-shm-usage")

        # No GPU on headless servers
        chrome_options.add_argument("--disable-gpu")

        # Consistent viewport for predictable page layout
        chrome_options.add_argument("--window-size=1920,1080")

        # Reduce resource usage in a shared container environment
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-networking")

        # If CHROME_BIN is set, point Selenium at that binary explicitly.
        # This handles cases where Chrome is installed to a non-standard path
        # (e.g. /usr/bin/google-chrome-stable, /usr/bin/chromium-browser).
        # If not set, Selenium will search PATH — which works when Chrome is
        # installed by render-build.sh and is on PATH.
        chrome_bin = os.environ.get("CHROME_BIN", "")
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
            logger.info(f"driver_factory: Chrome binary overridden to {chrome_bin}")
        else:
            logger.info("driver_factory: using Chrome from PATH")

        # webdriver-manager downloads the matching ChromeDriver automatically.
        # This is the same mechanism used on Windows and avoids any hardcoded
        # path assumption — the root cause of the previous /usr/bin/chromedriver
        # not found error.
        service = Service(ChromeDriverManager().install())
        logger.info("driver_factory: ChromeDriver resolved via webdriver-manager")

    else:
        # ------------------------------------------------------------------ #
        # Local Windows — original behaviour, completely unchanged            #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: Windows environment detected")
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver
