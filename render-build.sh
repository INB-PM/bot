#!/usr/bin/env bash
# render-build.sh
#
# Deployment-specific build script for Render.com.
# This script runs during the Render build phase (set as the "Build Command"
# in the Render dashboard or render.yaml).
#
# What it does:
#   1. Installs Python dependencies from requirements.txt
#   2. Installs Google Chrome Stable and its dependencies on Linux
#   3. Installs ChromeDriver that matches the installed Chrome version
#
# Local Windows developers do NOT run this script — webdriver-manager handles
# ChromeDriver automatically on Windows via driver_factory.py.

set -e  # Exit immediately on any error

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Installing system dependencies for Chrome"
apt-get update -y
apt-get install -y \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
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
    xdg-utils \
    --no-install-recommends

echo "==> Adding Google Chrome apt repository"
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list

echo "==> Installing Google Chrome Stable"
apt-get update -y
apt-get install -y google-chrome-stable --no-install-recommends

echo "==> Verifying Chrome installation"
google-chrome-stable --version

echo "==> Installing ChromeDriver"
# Derive the ChromeDriver version from the installed Chrome version.
CHROME_VERSION=$(google-chrome-stable --version | grep -oP '\d+\.\d+\.\d+\.\d+')
CHROME_MAJOR=$(echo "$CHROME_VERSION" | cut -d. -f1)

echo "    Chrome version: $CHROME_VERSION (major: $CHROME_MAJOR)"

# Chrome 115+ uses the Chrome for Testing endpoint
if [ "$CHROME_MAJOR" -ge 115 ]; then
    echo "==> Using Chrome for Testing endpoint (Chrome >= 115)"
    CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"
    wget -q "$CHROMEDRIVER_URL" -O /tmp/chromedriver.zip
    unzip -q /tmp/chromedriver.zip -d /tmp/
    mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver
else
    echo "==> Using legacy ChromeDriver endpoint (Chrome < 115)"
    CHROMEDRIVER_VERSION=$(curl -sS "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}")
    wget -q "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" \
        -O /tmp/chromedriver.zip
    unzip -q /tmp/chromedriver.zip -d /tmp/
    mv /tmp/chromedriver /usr/bin/chromedriver
fi

chmod +x /usr/bin/chromedriver
echo "==> ChromeDriver installed:"
chromedriver --version

echo "==> Ensuring output directory exists"
mkdir -p output

echo "==> Build complete"
