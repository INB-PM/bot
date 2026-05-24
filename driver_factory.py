"""
driver_factory.py — Reusable Selenium Chrome driver factory.

Works on both local Windows and Render/Linux.

HOW IT WORKS ON RENDER:
  render-build.sh uses the selenium-manager binary (bundled inside the
  selenium package) to download Chrome for Testing + ChromeDriver into
  /opt/render/project/src/.selenium-cache during the build phase.
  That directory is inside the project repo and persists to the runtime
  container.

  At runtime, this module sets SE_CACHE_PATH to that same directory before
  calling webdriver.Chrome(). Selenium Manager finds the cached binaries
  and uses them — no re-download, no apt-get, no system Chrome needed.

HOW IT WORKS LOCALLY (WINDOWS):
  webdriver-manager resolves ChromeDriver from the local Chrome installation.
  No options are changed. Behaviour is identical to the original code.
"""

import os
import platform
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

# Path where render-build.sh caches Chrome for Testing + ChromeDriver.
# Must match the --cache-path argument in render-build.sh.
_RENDER_SE_CACHE = "/opt/render/project/src/.selenium-cache"


def _is_render_or_linux() -> bool:
    """Return True when running on Render or any Linux host."""
    if os.environ.get("RENDER"):
        return True
    if platform.system().lower() == "linux":
        return True
    return False


def create_driver() -> webdriver.Chrome:
    """
    Create and return a configured Chrome WebDriver.

    On Render/Linux: points Selenium Manager at the pre-downloaded cache
    directory and applies headless + sandbox-free Chrome options.

    On Windows: uses webdriver-manager to resolve ChromeDriver from the
    local Chrome installation. No options changed — identical to original.

    Returns
    -------
    webdriver.Chrome
        A ready-to-use Chrome driver instance. Caller must call driver.quit().
    """
    # ------------------------------------------------------------------ #
    # Startup diagnostics — always logged, visible in Render log viewer  #
    # ------------------------------------------------------------------ #
    logger.info("driver_factory: ---- startup diagnostics ----")
    logger.info(f"driver_factory: platform         = {platform.system()} {platform.release()}")
    logger.info(f"driver_factory: python           = {platform.python_version()}")
    logger.info(f"driver_factory: RENDER env var   = {os.environ.get('RENDER', '(not set)')}")
    logger.info(f"driver_factory: SE_CACHE_PATH    = {os.environ.get('SE_CACHE_PATH', '(not set)')}")

    chrome_options = Options()

    if _is_render_or_linux():
        # ------------------------------------------------------------------ #
        # Render / Linux                                                      #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: mode = Render/Linux")

        # Point Selenium Manager at the cache directory populated during build.
        # This must be set BEFORE webdriver.Chrome() is called so that
        # Selenium Manager reads it when resolving browser/driver paths.
        os.environ["SE_CACHE_PATH"] = _RENDER_SE_CACHE
        logger.info(f"driver_factory: SE_CACHE_PATH set to {_RENDER_SE_CACHE}")

        # Verify the cache directory exists — if not, build script didn't run
        if not os.path.isdir(_RENDER_SE_CACHE):
            raise RuntimeError(
                f"Selenium cache directory not found: {_RENDER_SE_CACHE}\n"
                "This means render-build.sh did not run or failed.\n"
                "Check the Render build logs for '[3/4] Downloading Chrome'.\n"
                "Ensure Build Command is set to: bash render-build.sh"
            )

        # Log what's in the cache so we can see it in Render logs
        try:
            for root, dirs, files in os.walk(_RENDER_SE_CACHE):
                for f in files:
                    full = os.path.join(root, f)
                    logger.info(f"driver_factory: cache entry: {full}")
        except Exception:
            pass

        # Headless + sandbox-free options required on a server without display
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-networking")

        # Do NOT pass Service() — Selenium Manager resolves Chrome + ChromeDriver
        # from SE_CACHE_PATH automatically when no service is provided.
        logger.info("driver_factory: launching Chrome via Selenium Manager cache")
        driver = webdriver.Chrome(options=chrome_options)

    else:
        # ------------------------------------------------------------------ #
        # Local Windows — original behaviour, completely unchanged           #
        # ------------------------------------------------------------------ #
        logger.info("driver_factory: mode = local Windows")

        chromedriver_path = ChromeDriverManager().install()
        logger.info(f"driver_factory: ChromeDriver = {chromedriver_path}")

        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

    logger.info("driver_factory: Chrome launched successfully")
    return driver
