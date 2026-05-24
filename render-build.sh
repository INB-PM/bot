#!/usr/bin/env bash
# render-build.sh
#
# Build Command for Render.com.
# Set in Render dashboard: Build Command = bash render-build.sh
#
# WHY THIS APPROACH:
#   On Render, the build container and runtime container share ONLY the
#   project directory (/opt/render/project/src/). System-level installs
#   via apt-get are wiped between build and runtime — that is why every
#   previous apt-get approach failed.
#
#   This script uses Selenium Manager (the binary bundled inside the
#   selenium Python package at selenium/webdriver/common/linux/selenium-manager)
#   to download Chrome for Testing + ChromeDriver into a subdirectory of
#   the project during build. That subdirectory persists to runtime.
#
#   At runtime, driver_factory.py sets SE_CACHE_PATH to the same directory
#   so Selenium Manager finds the cached binaries without re-downloading.

set -e  # Fail loudly on any error

# ---------------------------------------------------------------------------
# Project directory — the only path that persists from build to runtime
# ---------------------------------------------------------------------------
PROJECT_DIR="/opt/render/project/src"
SE_CACHE="${PROJECT_DIR}/.selenium-cache"

echo "==> [1/4] Installing Python dependencies"
pip install -r requirements.txt

echo "==> [2/4] Locating Selenium Manager binary"
# selenium-manager is bundled inside the installed selenium package
SM_BIN=$(python -c "
import os, selenium
pkg_dir = os.path.dirname(selenium.__file__)
candidates = [
    os.path.join(pkg_dir, 'webdriver', 'common', 'linux', 'selenium-manager'),
    os.path.join(pkg_dir, 'webdriver', 'common', 'macos', 'selenium-manager'),
]
for c in candidates:
    if os.path.isfile(c):
        print(c)
        break
")

if [ -z "$SM_BIN" ]; then
    echo "ERROR: selenium-manager binary not found inside the selenium package."
    echo "Ensure selenium>=4.6.0 is in requirements.txt"
    exit 1
fi

echo "    selenium-manager found at: $SM_BIN"
chmod +x "$SM_BIN"

# ---------------------------------------------------------------------------
# [3/4] Use Selenium Manager to download Chrome for Testing + ChromeDriver
#        into the project directory so they persist to runtime
# ---------------------------------------------------------------------------
echo "==> [3/4] Downloading Chrome for Testing + ChromeDriver via Selenium Manager"
mkdir -p "$SE_CACHE"

"$SM_BIN" \
    --browser chrome \
    --cache-path "$SE_CACHE" \
    --debug

echo ""
echo "==> Verifying downloaded binaries"
find "$SE_CACHE" -type f -name "chrome" -o -name "chromedriver" | while read -r f; do
    echo "    Found: $f"
    "$f" --version 2>/dev/null || true
done

# ---------------------------------------------------------------------------
# [4/4] Ensure output directory exists for JSON files
# ---------------------------------------------------------------------------
echo "==> [4/4] Ensuring output directory exists"
mkdir -p output

echo ""
echo "==> Build complete."
echo "    Selenium cache: $SE_CACHE"
echo "    Chrome + ChromeDriver are cached in the project directory."
echo "    driver_factory.py will set SE_CACHE_PATH=$SE_CACHE at runtime."
