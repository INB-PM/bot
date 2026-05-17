# Design Document: Auto Scraper Scheduler

## Overview

This feature adds a background scheduling layer to the existing Flask web scraping application. Currently, scraping is triggered manually via the `/run` route. The scheduler will run `extract_links.run()` followed by `extract_h1.run()` automatically on a fixed 30-second interval, starting as soon as the Flask application boots.

The design introduces a single new module — `scheduler.py` — that encapsulates all scheduling logic. It integrates into `app.py` with minimal changes: one import and one `start_scheduler()` call. All existing scraping modules and the `/run` route remain completely untouched.

### Key Design Decisions

- **Single loop thread over recursive timers**: A `while` loop inside a daemon thread is used instead of `threading.Timer` chaining. This avoids timer accumulation and makes the stop signal straightforward — a single `threading.Event` flag.
- **Lock-based overlap prevention**: A `threading.Lock` is acquired before each scrape job and released in a `finally` block, guaranteeing release on both success and failure.
- **Non-blocking stop**: `stop_scheduler()` sets a stop event; the running job (if any) completes naturally before the loop exits.
- **Daemon thread**: The scheduler thread is marked as a daemon so it does not prevent the Python process from exiting when Flask shuts down.

---

## Architecture

```mermaid
graph TD
    A[app.py - Flask startup] -->|calls start_scheduler()| B[scheduler.py]
    B --> C[Scheduler_Thread - daemon]
    C --> D{Scrape_Lock available?}
    D -->|No| E[Log warning: job still running, skip]
    D -->|Yes| F[Acquire Scrape_Lock]
    F --> G[extract_links.run()]
    G --> H[extract_h1.run()]
    H --> I[Release Scrape_Lock]
    I --> J[Log completion + next run time]
    J --> K[time.sleep 30s]
    K --> D
    E --> K
    L[/run route] -->|manual trigger| G

    M[stop_scheduler()] -->|sets stop_event| C
```

The scheduler runs entirely on its own thread. Flask's request-handling threads and the scheduler thread share no mutable state except the output JSON files (which are protected by the scrape lock).

---

## Components and Interfaces

### `scheduler.py` (new module)

This is the only new file. It exposes two public functions and manages all internal state as module-level variables.

```python
def start_scheduler() -> None:
    """
    Start the background scheduling loop on a daemon thread.
    No-op (with warning log) if already running.
    """

def stop_scheduler() -> None:
    """
    Signal the scheduling loop to stop after the current job completes.
    No-op (with warning log) if not currently running.
    """
```

**Internal state (module-level)**:

| Variable | Type | Purpose |
|---|---|---|
| `_scrape_lock` | `threading.Lock` | Prevents concurrent scrape jobs |
| `_stop_event` | `threading.Event` | Signals the loop to exit |
| `_scheduler_thread` | `threading.Thread \| None` | Reference to the active daemon thread |
| `_is_running` | `bool` | Guard flag for duplicate start/stop calls |
| `logger` | `logging.Logger` | Module-level logger (`scheduler`) |

**Internal functions**:

```python
def _run_scrape_job() -> None:
    """
    Execute one full scrape cycle: extract_links.run() then extract_h1.run().
    Acquires and releases _scrape_lock. Logs start, completion, and errors.
    """

def _scheduler_loop() -> None:
    """
    Main loop executed on the Scheduler_Thread.
    Calls _run_scrape_job(), sleeps 30 seconds, repeats until _stop_event is set.
    """
```

### `app.py` (modified — minimal)

Two lines are added:

```python
from scheduler import start_scheduler

# inside the module body, after app = Flask(__name__)
start_scheduler()
```

No other changes. The `/run` route, imports of `extract_links` and `extract_h1`, and all templates remain identical.

### `extract_links.py` and `extract_h1.py` (unchanged)

These modules are called by `_run_scrape_job()` exactly as they are called by the `/run` route today. No modifications are made.

---

## Data Models

The scheduler introduces no new persistent data structures. All data flow remains through the existing JSON files:

```
output/links.json      ← written by extract_links.run()
output/h1_tags.json    ← written by extract_h1.run(), read by /run route
```

### Scheduler Internal State

The scheduler's runtime state is held entirely in module-level variables (no classes, no databases):

```python
_scrape_lock: threading.Lock = threading.Lock()
_stop_event: threading.Event = threading.Event()
_scheduler_thread: threading.Thread | None = None
_is_running: bool = False
```

### Log Message Schema

All log messages are emitted via Python's `logging` module at the following levels:

| Event | Level | Required content |
|---|---|---|
| Scheduler started | INFO | "activated" |
| Scheduler stopped | INFO | "deactivated" |
| Scrape job started | INFO | "started", current timestamp |
| Scrape job completed | INFO | "completed", elapsed duration (seconds) |
| Scrape job failed | ERROR | "error", exception details |
| Next run scheduled | INFO | next run timestamp |
| Job skipped (overlap) | WARNING | previous job still in progress |
| Duplicate start call | WARNING | scheduler already running |
| Redundant stop call | WARNING | scheduler not running |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Lock is always released after a scrape job

*For any* scrape job execution — whether it succeeds or raises an exception — the `_scrape_lock` SHALL be released upon job completion, leaving the lock in an unacquired state.

**Validates: Requirements 3.3, 5.2**

---

### Property 2: Overlap prevention

*For any* scheduler state where a scrape job is currently holding the lock, attempting to start another scrape job SHALL fail to acquire the lock and SHALL not execute `extract_links.run()` or `extract_h1.run()`.

**Validates: Requirements 3.1, 3.2**

---

### Property 3: Stop-then-start produces exactly one active thread

*For any* sequence of `stop_scheduler()` followed by `start_scheduler()`, the scheduler SHALL have exactly one active `Scheduler_Thread` and no orphaned threads from the previous run.

**Validates: Requirements 8.1, 8.2**

---

### Property 4: Duplicate start is a no-op

*For any* scheduler state where the scheduler is already running, calling `start_scheduler()` again SHALL not create an additional thread and SHALL leave the number of active scheduler threads unchanged at one.

**Validates: Requirements 6.4**

---

### Property 5: Scrape job sequence is preserved

*For any* scrape job execution triggered by the scheduler, `extract_links.run()` SHALL always be called before `extract_h1.run()`, matching the sequence in the `/run` route.

**Validates: Requirements 7.1**

---

## Error Handling

### Scrape job exceptions

All exceptions raised inside `_run_scrape_job()` are caught by a `try/except/finally` block:

```python
def _run_scrape_job():
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
```

The `finally` block guarantees lock release regardless of outcome. The scheduler loop continues after the job returns, so a failed job does not halt future scheduling.

### Scheduler thread exceptions

The `_scheduler_loop()` function wraps the entire loop body in a broad `try/except` to prevent the thread from dying silently on unexpected errors outside the scrape job itself.

### Stop signal during sleep

`_stop_event.wait(timeout=30)` is used instead of `time.sleep(30)`. This allows `stop_scheduler()` to interrupt the sleep immediately when the stop event is set, rather than waiting up to 30 seconds for the sleep to expire.

```python
def _scheduler_loop():
    logger.info("Scheduler activated.")
    while not _stop_event.is_set():
        _run_scrape_job()
        next_run = datetime.now() + timedelta(seconds=30)
        logger.info(f"Next scrape scheduled at {next_run}")
        _stop_event.wait(timeout=30)
    logger.info("Scheduler deactivated.")
```

---

## Testing Strategy

### Unit Tests

Unit tests use `unittest.mock` to patch `extract_links.run` and `extract_h1.run`, keeping tests fast and free of Selenium/browser dependencies.

**Specific scenarios to cover:**

- `start_scheduler()` starts a daemon thread and sets `_is_running = True`
- `start_scheduler()` called twice logs a warning and does not create a second thread
- `stop_scheduler()` sets the stop event and the loop exits
- `stop_scheduler()` called when not running logs a warning
- `_run_scrape_job()` calls `extract_links.run()` then `extract_h1.run()` in order
- `_run_scrape_job()` releases the lock when `extract_links.run()` raises an exception
- `_run_scrape_job()` releases the lock when `extract_h1.run()` raises an exception
- `_run_scrape_job()` skips execution and logs a warning when the lock is already held
- Stop-then-start cycle produces exactly one active thread

### Property-Based Tests

Property-based tests use [Hypothesis](https://hypothesis.readthedocs.io/) (Python PBT library). Each test runs a minimum of 100 iterations.

**Property 1 — Lock always released:**
Generate random exception types and injection points (before `extract_links.run()`, between the two calls, after `extract_h1.run()`). For each combination, verify the lock is not held after `_run_scrape_job()` returns.
*Tag: Feature: auto-scraper-scheduler, Property 1: Lock is always released after a scrape job*

**Property 2 — Overlap prevention:**
Generate concurrent call scenarios where the lock is pre-held. Verify that `extract_links.run()` and `extract_h1.run()` are never called while the lock is already acquired.
*Tag: Feature: auto-scraper-scheduler, Property 2: Overlap prevention*

**Property 3 — Stop-then-start thread count:**
Generate arbitrary sequences of stop/start calls. After each valid stop→start transition, verify thread count is exactly one.
*Tag: Feature: auto-scraper-scheduler, Property 3: Stop-then-start produces exactly one active thread*

**Property 4 — Duplicate start is a no-op:**
Generate an already-running scheduler state. Call `start_scheduler()` N times (N drawn from 1–20). Verify thread count remains one throughout.
*Tag: Feature: auto-scraper-scheduler, Property 4: Duplicate start is a no-op*

**Property 5 — Scrape job sequence:**
Generate any number of successful and failing scrape job executions. Verify that in every execution where both calls are made, `extract_links.run()` is always called before `extract_h1.run()`.
*Tag: Feature: auto-scraper-scheduler, Property 5: Scrape job sequence is preserved*

### Integration Tests

- Start the scheduler, wait for at least one full cycle, verify `output/h1_tags.json` is written and contains valid JSON.
- Verify the `/run` route still works independently of the scheduler.
