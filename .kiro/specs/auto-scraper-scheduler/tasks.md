# Implementation Plan: Auto Scraper Scheduler

## Overview

Introduce `scheduler.py` as a new module that runs `extract_links.run()` followed by `extract_h1.run()` on a 30-second background loop, then wire it into `app.py` with a single import and a single `start_scheduler()` call. All existing scraping modules and the `/run` route remain untouched.

## Tasks

- [x] 1. Create `scheduler.py` with module-level state and logging setup
  - Create `scheduler.py` in the project root
  - Import `threading`, `time`, `logging`, `datetime`, `timedelta`, `extract_links`, and `extract_h1`
  - Declare module-level variables: `_scrape_lock`, `_stop_event`, `_scheduler_thread`, `_is_running`
  - Configure a module-level logger named `"scheduler"` using `logging.getLogger`
  - _Requirements: 1.2, 1.3, 4.5, 4.6, 8.1_

- [x] 2. Implement `_run_scrape_job()` with lock, sequencing, and error handling
  - [x] 2.1 Implement `_run_scrape_job()`
    - Use `_scrape_lock.acquire(blocking=False)` to attempt lock acquisition
    - If lock is not acquired, log a WARNING containing "previous job still in progress" and return immediately
    - Inside a `try` block: log INFO with "started" and current timestamp, call `extract_links.run()`, call `extract_h1.run()`, log INFO with "completed" and elapsed duration
    - Inside an `except Exception` block: log ERROR with "error" and exception details using `exc_info=True`
    - Inside a `finally` block: call `_scrape_lock.release()`
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 5.1, 5.2, 7.1_

  - [x] 2.2 Write property test for lock always released (Property 1)
    - **Property 1: Lock is always released after a scrape job**
    - Generate random exception types raised at three injection points: before `extract_links.run()`, between the two calls, and after `extract_h1.run()`
    - For each combination, assert `_scrape_lock.locked()` is `False` after `_run_scrape_job()` returns
    - **Validates: Requirements 3.3, 5.2**

  - [x] 2.3 Write property test for overlap prevention (Property 2)
    - **Property 2: Overlap prevention**
    - Pre-acquire `_scrape_lock` to simulate a running job, then call `_run_scrape_job()`
    - Assert that neither `extract_links.run` nor `extract_h1.run` was called
    - **Validates: Requirements 3.1, 3.2**

  - [x] 2.4 Write property test for scrape job sequence (Property 5)
    - **Property 5: Scrape job sequence is preserved**
    - Generate any number of successful and failing scrape job executions using mocked `extract_links.run` and `extract_h1.run`
    - For every execution where both calls are made, assert the call order recorded by the mock shows `extract_links.run` before `extract_h1.run`
    - **Validates: Requirements 7.1**

  - [x] 2.5 Write unit tests for `_run_scrape_job()`
    - Test that `extract_links.run()` is called before `extract_h1.run()` in a successful run
    - Test that the lock is released when `extract_links.run()` raises an exception
    - Test that the lock is released when `extract_h1.run()` raises an exception
    - Test that execution is skipped and a warning is logged when the lock is already held
    - _Requirements: 3.1, 3.2, 3.3, 5.1, 5.2, 7.1_

- [x] 3. Checkpoint — Ensure all `_run_scrape_job` tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement `_scheduler_loop()` with stop-event-based sleep
  - [x] 4.1 Implement `_scheduler_loop()`
    - Log INFO "Scheduler activated." at loop entry
    - Loop `while not _stop_event.is_set()`
    - Inside the loop: call `_run_scrape_job()`, compute `next_run = datetime.now() + timedelta(seconds=30)`, log INFO with next run timestamp, call `_stop_event.wait(timeout=30)`
    - After the loop exits, log INFO "Scheduler deactivated."
    - Wrap the entire loop body in a broad `try/except` to prevent silent thread death
    - _Requirements: 2.1, 2.2, 4.4, 4.5, 4.6, 5.3, 8.3_

  - [x] 4.2 Write unit tests for `_scheduler_loop()`
    - Test that the loop calls `_run_scrape_job()` and then waits 30 seconds before the next call
    - Test that setting `_stop_event` causes the loop to exit without executing another job
    - Test that `stop_scheduler()` interrupts the sleep immediately rather than waiting the full 30 seconds
    - _Requirements: 2.1, 5.3, 6.3_

- [x] 5. Implement `start_scheduler()` and `stop_scheduler()`
  - [x] 5.1 Implement `start_scheduler()`
    - Check `_is_running`; if `True`, log WARNING "scheduler already running" and return
    - Reset `_stop_event` by calling `_stop_event.clear()`
    - Create a new `threading.Thread` targeting `_scheduler_loop`, set `daemon=True`, assign to `_scheduler_thread`
    - Set `_is_running = True` and call `_scheduler_thread.start()`
    - _Requirements: 1.1, 1.2, 1.3, 6.1, 6.4, 8.1_

  - [x] 5.2 Implement `stop_scheduler()`
    - Check `_is_running`; if `False`, log WARNING "scheduler not running" and return
    - Call `_stop_event.set()` to signal the loop to exit
    - Set `_is_running = False`
    - _Requirements: 6.2, 6.3, 6.5_

  - [x] 5.3 Write property test for duplicate start is a no-op (Property 4)
    - **Property 4: Duplicate start is a no-op**
    - Start the scheduler, then call `start_scheduler()` N times (N drawn from 1–20 by Hypothesis)
    - Assert that the number of active `Scheduler_Thread` instances remains exactly one throughout
    - **Validates: Requirements 6.4**

  - [x] 5.4 Write property test for stop-then-start thread count (Property 3)
    - **Property 3: Stop-then-start produces exactly one active thread**
    - Generate arbitrary sequences of `stop_scheduler()` followed by `start_scheduler()` calls
    - After each valid stop→start transition, assert exactly one `Scheduler_Thread` is alive and `_is_running` is `True`
    - **Validates: Requirements 8.1, 8.2**

  - [x] 5.5 Write unit tests for `start_scheduler()` and `stop_scheduler()`
    - Test that `start_scheduler()` creates a daemon thread and sets `_is_running = True`
    - Test that calling `start_scheduler()` twice logs a warning and does not create a second thread
    - Test that `stop_scheduler()` sets the stop event
    - Test that calling `stop_scheduler()` when not running logs a warning
    - Test that a stop-then-start cycle produces exactly one active thread with no orphans
    - _Requirements: 1.2, 1.3, 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2_

- [x] 6. Checkpoint — Ensure all scheduler control tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Wire `scheduler.py` into `app.py`
  - Add `from scheduler import start_scheduler` to the imports in `app.py`
  - Add `start_scheduler()` call in the module body of `app.py`, after `app = Flask(__name__)`
  - Verify the `/run` route, all existing imports, and templates are completely unchanged
  - _Requirements: 1.1, 7.2, 7.3_

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Property-based tests use [Hypothesis](https://hypothesis.readthedocs.io/); install with `pip install hypothesis`
- Each property test maps directly to a correctness property in the design document
- Unit tests use `unittest.mock` to patch `extract_links.run` and `extract_h1.run`, keeping tests free of Selenium/browser dependencies
- `_stop_event.wait(timeout=30)` is used instead of `time.sleep(30)` so `stop_scheduler()` can interrupt the sleep immediately
- The scheduler thread is a daemon thread — it will not prevent the Python process from exiting when Flask shuts down
