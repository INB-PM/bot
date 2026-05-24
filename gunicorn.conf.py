# gunicorn.conf.py
#
# Deployment-specific change: Gunicorn configuration for Render.
#
# The scraper visits multiple URLs with Selenium (each with a time.sleep(2)
# delay), so a single /run request can take 30–120 seconds depending on how
# many links were collected.  The default Gunicorn worker timeout is 30 s,
# which causes workers to be killed mid-scrape and returns a 502 to the user.
#
# This file is picked up automatically when Gunicorn is started with:
#   gunicorn -c gunicorn.conf.py app:app
#
# Local Windows developers run `python app.py` directly and are unaffected
# by this file.

import os

# ---------------------------------------------------------------------------
# Worker configuration
# ---------------------------------------------------------------------------

# Use a single sync worker.  The background scheduler thread is already
# handling periodic scraping; the Flask worker only needs to serve HTTP
# requests and the occasional manual /run trigger.
workers = 1

# Sync worker class — compatible with the background daemon thread started
# by scheduler.py.  Async workers (gevent, eventlet) can interfere with
# threading.Thread-based schedulers.
worker_class = "sync"

# ---------------------------------------------------------------------------
# Timeout configuration
# ---------------------------------------------------------------------------

# Deployment-specific: raise the worker timeout to 300 seconds (5 minutes)
# to accommodate slow Selenium scrape runs on Render's free tier.
# The GUNICORN_TIMEOUT environment variable lets operators override this
# without changing the file (e.g. set it to 120 for faster machines).
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "300"))

# Keep-alive timeout for persistent connections
keepalive = 5

# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------

# Render injects the PORT environment variable; fall back to 10000 locally
# if this config file is ever used outside Render.
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Send access and error logs to stdout so Render's log viewer captures them
accesslog = "-"
errorlog = "-"
loglevel = "info"
