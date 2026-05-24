#!/usr/bin/env bash
# render-build.sh
#
# Build script for Render.com.
# Set this as the "Build Command" in the Render dashboard or render.yaml.
#
# What it does:
#   1. Installs Python dependencies (including webdriver-manager, which will
#      download ChromeDriver automatically at runtime — no manual install needed)
#   2. Installs Google Chrome Stable on Linux
#
# ChromeDriver is NOT installed here. webdriver-manager (called by
# driver_factory.py at runtime) downloads the correct ChromeDriver version
# automatically, matching whatever Chrome version is installed. This avoids
# version mismatch errors and path assumption failures.

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
    unzip \
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

echo "==> Ensuring output directory exists"
mkdir -p output

echo "==> Build complete"
echo "    ChromeDriver will be downloaded automatically by webdriver-manager at runtime."
