#!/usr/bin/env bash
# render-build.sh
#
# Build Command for Render.com — set this in the Render dashboard:
#   Build Command: bash render-build.sh
#
# Installs Google Chrome directly from the official .deb package using wget.
# This bypasses the apt-key / apt-repo approach which fails silently on
# modern Debian containers (apt-key is deprecated; the signed-by method
# requires extra setup that varies by distro version).
#
# Downloading the .deb directly is the most reliable method on Render.

set -e  # Exit immediately on any error — build fails loudly, not silently

# ---------------------------------------------------------------------------
# 1. Python dependencies
# ---------------------------------------------------------------------------
echo "==> [1/4] Installing Python dependencies"
pip install -r requirements.txt

# ---------------------------------------------------------------------------
# 2. System libraries Chrome depends on
# ---------------------------------------------------------------------------
echo "==> [2/4] Installing Chrome system dependencies"
apt-get update -y
apt-get install -y \
    wget \
    curl \
    unzip \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    --no-install-recommends

# ---------------------------------------------------------------------------
# 3. Download and install Google Chrome Stable .deb directly from Google
#    This avoids the apt-key / signed-by repo setup entirely.
# ---------------------------------------------------------------------------
echo "==> [3/4] Downloading Google Chrome Stable .deb"
wget -q \
    "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" \
    -O /tmp/google-chrome-stable.deb

echo "==> [3/4] Installing Google Chrome Stable"
# dpkg -i will fail on missing deps; apt-get -f install fixes them
dpkg -i /tmp/google-chrome-stable.deb || apt-get install -f -y

# ---------------------------------------------------------------------------
# 4. Verify Chrome is installed and print version — fails build if missing
# ---------------------------------------------------------------------------
echo "==> [4/4] Verifying Chrome installation"

CHROME_BIN=""
for candidate in \
    /usr/bin/google-chrome-stable \
    /usr/bin/google-chrome \
    /usr/bin/chromium-browser \
    /usr/bin/chromium; do
    if [ -x "$candidate" ]; then
        CHROME_BIN="$candidate"
        break
    fi
done

if [ -z "$CHROME_BIN" ]; then
    echo "ERROR: Chrome binary not found after installation. Build cannot continue."
    echo "Searched: /usr/bin/google-chrome-stable, /usr/bin/google-chrome, /usr/bin/chromium-browser, /usr/bin/chromium"
    exit 1
fi

echo "Chrome binary found at: $CHROME_BIN"
"$CHROME_BIN" --version

# ---------------------------------------------------------------------------
# 5. Ensure output directory exists for JSON files
# ---------------------------------------------------------------------------
mkdir -p output

echo ""
echo "==> Build complete."
echo "    Chrome: $CHROME_BIN"
echo "    ChromeDriver will be resolved by webdriver-manager at runtime."
