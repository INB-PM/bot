"""
driver_factory.py — Reusable Selenium Chrome driver factory.

Works on both local Windows and Render/Linux with zero system dependencies.

Strategy:
  - On BOTH environments, we pass no Service() and no binary_location.
    Selenium 4.6+ ships with "Selenium Manager" — a self-contained binary
    that automatically downloads the correct Chrome + ChromeDriver for the
    current platform and caches them locally.  No apt-get, no webdriver-manager,
    no hardcoded paths required.
  - On Render/Linux, headless + sandbox-free Chrome options are added so
    the browser can run without a display.
  - On Windows, no extra options are applied — behaviour is identical to
    the original code.

Why this works on Render:
  Selenium Manager is bundled inside the selenium Python package itself
  (at selenium/webdriver/common/linux/selenium-manager).  It runs as a
  subprocess, downloads Chrome for Testing + ChromeDriver into a cache
  directory inside the project, and returns the paths to the Python driver.
  No root access, no apt-get, no pre-installed Chrome required.
"""

import os
import platform
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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

    Selenium Manager (bundled with selenium >= 4.6) handles Chrome and
    ChromeDriver download/location automatically on all platforms.
    No Service() object is passed — Selenium resolves the driver path itself.

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
        logger.info("driver_factory: Linux/Render environment — applying headless options")

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

        logger.info(
            "driver_factory: no Service() passed — Selenium Manager will "
            "auto-download Chrome + ChromeDriver for this platform"
        )

    else:
        # ------------------------------------------------------------------ #
        # Local Windows — no extra options, Selenium Manager handles driver  #
        # ------------------------------------------------------------------ #
        logger.info(
            "driver_factory: Windows environment — Selenium Manager will "
            "locate or download ChromeDriver automatically"
        )

    # Do NOT pass a Service() argument.
    # Selenium Manager (bundled in the selenium package) resolves Chrome and
    # ChromeDriver automatically.  This works on Windows, Linux, and Render
    # without any system-level Chrome installation or webdriver-manager calls.
    driver = webdriver.Chrome(options=chrome_options)
    return driver
