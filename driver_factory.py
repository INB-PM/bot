"""
driver_factory.py — Reusable Selenium Chrome driver factory.

Works on both local Windows and Render/Linux.

Strategy:
  - On Windows: webdriver-manager locates/downloads ChromeDriver automatically.
    No Chrome options are changed — identical to the original local behaviour.
  - On Render/Linux: Chrome is installed by render-build.sh during the build
    phase.  This module probes the known Linux binary locations, sets
    binary_location explicitly so Selenium never has to guess, and applies
    headless + sandbox-free options required for a server environment.
    webdriver-manager is still used to resolve ChromeDriver on Linux too,
    so there is no hardcoded ChromeDriver path.

Debug logging:
  Every create_driver() call logs the platform, PATH, detected Chrome path,
  and ChromeDriver path so deployment failures are easy to diagnose from
  Render's log viewer.
"""

import os
import platform
import logging
import shutil

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

# Ordered list of Chrome binary locations to probe on Linux.
# The first one that exists and is executable wins.
_LINUX_CHROME_CANDIDATES = [
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/snap/bin/chromium",
]


def _is_render_or_linux() -> bool:
    """Return True when running on Render or any Linux host."""
    if os.environ.get("RENDER"):
        return True
    if platform.system().lower() == "linux":
        return True
    return False


def _find_linux_chrome() -> str:
    """
    Probe known Linux Chrome binary locations and return the first one found.
    Raises RuntimeError with a diagnostic message if none are found.
    """
    for candidate in _LINUX_CHROME_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # Also try whatever 'google-chrome' resolves to on PATH
    on_path = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium-browser") or shutil.which("chromium")
    if on_path:
        return on_path

    raise RuntimeError(
        "Chrome binary not found on this Linux host.\n"
        f"Searched: {_LINUX_CHROME_CANDIDATES}\n"
        "Also checked PATH via shutil.which — nothing found.\n"
        "Ensure render-build.sh ran successfully during the Render build phase.\n"
        "Check the Render build logs for '[3/4] Installing Google Chrome Stable'."
    )


def create_driver() -> webdriver.Chrome:
    """
    Create and return a configured Chrome WebDriver.

    Logs platform, PATH, Chrome binary path, and ChromeDriver path before
    launching so deployment failures are visible in Render's log viewer.

    Returns
    -------
    webdriver.Chrome
        A ready-to-use Chrome driver instance.  The caller is responsible
        for calling driver.quit() when finished.
    """
    # ------------------------------------------------------------------ #
    # Startup diagnostics — always logged, visible in Render log viewer  #
    # ------------------------------------------------------------------ #
    logger.info("driver_factory: ---- Chrome driver startup diagnostics ----")
    logger.info(f"driver_factory: OS platform      = {platform.system()} {platform.release()}")
    logger.info(f"driver_factory: Python version   = {platform.python_version()}")
    logger.info(f"driver_factory: RENDER env var   = {os.environ.get('RENDER', '(not set)')}")
    logger.info(f"driver_factory: PATH             = {os.environ.get('PATH', '(not set)')}")

    chrome_options = Options()

    if _is_render_or_linux():
        # ------------------------------------------------------------------ #
        # Render / Linux path                                                #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: environment = Render/Linux")

        # Locate Chrome binary — probe all known paths
        chrome_bin = _find_linux_chrome()
        logger.info(f"driver_factory: Chrome binary    = {chrome_bin}")

        # Tell Selenium exactly where Chrome is — no guessing
        chrome_options.binary_location = chrome_bin

        # Headless + sandbox-free options required on a server
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-networking")

        # webdriver-manager downloads the matching ChromeDriver automatically
        chromedriver_path = ChromeDriverManager().install()
        logger.info(f"driver_factory: ChromeDriver path = {chromedriver_path}")

        service = Service(chromedriver_path)

    else:
        # ------------------------------------------------------------------ #
        # Local Windows — original behaviour, completely unchanged           #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: environment = local Windows")

        # Log what Chrome webdriver-manager finds locally
        chromedriver_path = ChromeDriverManager().install()
        logger.info(f"driver_factory: ChromeDriver path = {chromedriver_path}")

        service = Service(chromedriver_path)
        # No chrome_options changes — GUI Chrome, no headless

    logger.info("driver_factory: ---- launching Chrome ----")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    logger.info("driver_factory: Chrome launched successfully")
    return driver
