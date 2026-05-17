import threading
import time
import logging
from datetime import datetime, timedelta

import extract_links
import extract_h1

# Module-level logger
logger = logging.getLogger("scheduler")

# Module-level state
_scrape_lock: threading.Lock = threading.Lock()
_stop_event: threading.Event = threading.Event()
_scheduler_thread: threading.Thread | None = None
_is_running: bool = False


def _run_scrape_job() -> None:
    """
    Execute one full scrape cycle: extract_links.run() then extract_h1.run().
    Acquires and releases _scrape_lock. Logs start, completion, and errors.
    """
    if not _scrape_lock.acquire(blocking=False):
        logger.warning("Previous scrape job still in progress — skipping.")
        return
    try:
        start = time.time()
        logger.info(f"Scrape job started at {datetime.now()}")
        extract_links.run()
        extract_h1.run()
        elapsed = time.time() - start
        logger.info(f"Scrape job completed in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"Scrape job error: {e}", exc_info=True)
    finally:
        _scrape_lock.release()


def _scheduler_loop() -> None:
    """
    Main loop executed on the Scheduler_Thread.
    Calls _run_scrape_job(), waits 30 seconds (interruptible), repeats until
    _stop_event is set. Wraps the loop body in a broad try/except to prevent
    silent thread death on unexpected errors outside the scrape job itself.
    """
    logger.info("Scheduler activated.")
    while not _stop_event.is_set():
        try:
            _run_scrape_job()
            next_run = datetime.now() + timedelta(seconds=30)
            logger.info(f"Next scrape scheduled at {next_run}")
            _stop_event.wait(timeout=30)
        except Exception as e:
            logger.error(f"Unexpected scheduler error: {e}", exc_info=True)
    logger.info("Scheduler deactivated.")


def start_scheduler() -> None:
    """
    Start the background scheduling loop on a daemon thread.
    No-op (with warning log) if already running.
    """
    global _is_running, _scheduler_thread

    if _is_running:
        logger.warning("scheduler already running")
        return

    _stop_event.clear()

    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _is_running = True
    _scheduler_thread.start()


def stop_scheduler() -> None:
    """
    Signal the scheduling loop to stop after the current job completes.
    No-op (with warning log) if not currently running.
    """
    global _is_running

    if not _is_running:
        logger.warning("scheduler not running")
        return

    _stop_event.set()
    _is_running = False
