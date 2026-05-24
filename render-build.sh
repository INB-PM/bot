#!/usr/bin/env bash
# render-build.sh
#
# Build script for Render.com.
# Set this as the "Build Command" in the Render dashboard or render.yaml.
#
# Chrome and ChromeDriver are NOT installed here.
# Selenium Manager (bundled inside the selenium Python package >= 4.6)
# downloads the correct Chrome for Testing + ChromeDriver automatically
# at runtime, into a local cache directory.  No apt-get, no root access,
# no pre-installed Chrome required.

set -e  # Exit immediately on any error

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Ensuring output directory exists"
mkdir -p output

echo "==> Build complete"
echo "    Chrome + ChromeDriver will be downloaded automatically by"
echo "    Selenium Manager (bundled in the selenium package) at runtime."
