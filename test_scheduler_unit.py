"""
Unit tests for scheduler._run_scrape_job().

Covers:
- extract_links.run() is called before extract_h1.run() in a successful run
- Lock is released when extract_links.run() raises an exception
- Lock is released when extract_h1.run() raises an exception
- Execution is skipped and a warning is logged when the lock is already held

Requirements: 3.1, 3.2, 3.3, 5.1, 5.2, 7.1
"""

import sys
import threading
import types
import unittest
from unittest.mock import MagicMock, call, patch

# Stub out selenium-dependent modules before importing scheduler so the test
# suite can run without a browser/Selenium installation.
for _mod_name in ("selenium", "selenium.webdriver", "extract_links", "extract_h1"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = types.ModuleType(_mod_name)

# Ensure extract_links and extract_h1 have a callable `run` attribute
sys.modules["extract_links"].run = MagicMock()
sys.modules["extract_h1"].run = MagicMock()

import scheduler  # noqa: E402 — must come after stubs


def reset_scheduler_state():
    """Reset all scheduler module-level state between test runs."""
    scheduler._scrape_lock = threading.Lock()
    scheduler._stop_event = threading.Event()
    scheduler._is_running = False
    scheduler._scheduler_thread = None


class TestRunScrapeJobSequence(unittest.TestCase):
    """
    Test that extract_links.run() is called before extract_h1.run()
    in a successful scrape job execution.

    Requirements: 7.1
    """

    def setUp(self):
        reset_scheduler_state()

    def test_extract_links_called_before_extract_h1(self):
        """extract_links.run() must be called before extract_h1.run() on success."""
        call_order = []

        def links_run():
            call_order.append("extract_links.run")

        def h1_run():
            call_order.append("extract_h1.run")

        with patch.object(scheduler.extract_links, "run", side_effect=links_run), \
             patch.object(scheduler.extract_h1, "run", side_effect=h1_run):
            scheduler._run_scrape_job()

        self.assertIn("extract_links.run", call_order, "extract_links.run was not called")
        self.assertIn("extract_h1.run", call_order, "extract_h1.run was not called")
        links_index = call_order.index("extract_links.run")
        h1_index = call_order.index("extract_h1.run")
        self.assertLess(
            links_index,
            h1_index,
            f"extract_links.run (index {links_index}) was not called before "
            f"extract_h1.run (index {h1_index}). Call order: {call_order}",
        )

    def test_both_scraping_functions_are_called_on_success(self):
        """Both extract_links.run() and extract_h1.run() must be called on a successful run."""
        with patch.object(scheduler.extract_links, "run") as mock_links, \
             patch.object(scheduler.extract_h1, "run") as mock_h1:
            scheduler._run_scrape_job()

        mock_links.assert_called_once()
        mock_h1.assert_called_once()


class TestRunScrapeJobLockReleasedOnExtractLinksException(unittest.TestCase):
    """
    Test that the scrape lock is released when extract_links.run() raises an exception.

    Requirements: 3.3, 5.2
    """

    def setUp(self):
        reset_scheduler_state()

    def test_lock_released_when_extract_links_raises(self):
        """Lock must be released even when extract_links.run() raises an exception."""
        with patch.object(scheduler.extract_links, "run", side_effect=RuntimeError("links failed")), \
             patch.object(scheduler.extract_h1, "run"):
            scheduler._run_scrape_job()

        self.assertFalse(
            scheduler._scrape_lock.locked(),
            "Lock was still held after extract_links.run() raised an exception",
        )

    def test_lock_released_when_extract_links_raises_value_error(self):
        """Lock must be released for any exception type from extract_links.run()."""
        with patch.object(scheduler.extract_links, "run", side_effect=ValueError("bad value")), \
             patch.object(scheduler.extract_h1, "run"):
            scheduler._run_scrape_job()

        self.assertFalse(
            scheduler._scrape_lock.locked(),
            "Lock was still held after extract_links.run() raised a ValueError",
        )

    def test_extract_h1_not_called_when_extract_links_raises(self):
        """extract_h1.run() must not be called if extract_links.run() raises."""
        with patch.object(scheduler.extract_links, "run", side_effect=RuntimeError("links failed")), \
             patch.object(scheduler.extract_h1, "run") as mock_h1:
            scheduler._run_scrape_job()

        mock_h1.assert_not_called()


class TestRunScrapeJobLockReleasedOnExtractH1Exception(unittest.TestCase):
    """
    Test that the scrape lock is released when extract_h1.run() raises an exception.

    Requirements: 3.3, 5.2
    """

    def setUp(self):
        reset_scheduler_state()

    def test_lock_released_when_extract_h1_raises(self):
        """Lock must be released even when extract_h1.run() raises an exception."""
        with patch.object(scheduler.extract_links, "run"), \
             patch.object(scheduler.extract_h1, "run", side_effect=RuntimeError("h1 failed")):
            scheduler._run_scrape_job()

        self.assertFalse(
            scheduler._scrape_lock.locked(),
            "Lock was still held after extract_h1.run() raised an exception",
        )

    def test_lock_released_when_extract_h1_raises_io_error(self):
        """Lock must be released for any exception type from extract_h1.run()."""
        with patch.object(scheduler.extract_links, "run"), \
             patch.object(scheduler.extract_h1, "run", side_effect=IOError("io error")):
            scheduler._run_scrape_job()

        self.assertFalse(
            scheduler._scrape_lock.locked(),
            "Lock was still held after extract_h1.run() raised an IOError",
        )

    def test_extract_links_was_called_before_extract_h1_raised(self):
        """extract_links.run() must have been called even when extract_h1.run() raises."""
        with patch.object(scheduler.extract_links, "run") as mock_links, \
             patch.object(scheduler.extract_h1, "run", side_effect=RuntimeError("h1 failed")):
            scheduler._run_scrape_job()

        mock_links.assert_called_once()


class TestRunScrapeJobSkippedWhenLockHeld(unittest.TestCase):
    """
    Test that execution is skipped and a warning is logged when the lock is already held.

    Requirements: 3.1, 3.2
    """

    def setUp(self):
        reset_scheduler_state()

    def test_scraping_skipped_when_lock_already_held(self):
        """Neither extract_links.run() nor extract_h1.run() should be called when lock is held."""
        acquired = scheduler._scrape_lock.acquire(blocking=False)
        self.assertTrue(acquired, "Test setup failed: could not pre-acquire the lock")
        try:
            with patch.object(scheduler.extract_links, "run") as mock_links, \
                 patch.object(scheduler.extract_h1, "run") as mock_h1:
                scheduler._run_scrape_job()

            mock_links.assert_not_called()
            mock_h1.assert_not_called()
        finally:
            scheduler._scrape_lock.release()

    def test_warning_logged_when_lock_already_held(self):
        """A warning must be logged when the lock is already held and the job is skipped."""
        acquired = scheduler._scrape_lock.acquire(blocking=False)
        self.assertTrue(acquired, "Test setup failed: could not pre-acquire the lock")
        try:
            with self.assertLogs("scheduler", level="WARNING") as log_ctx:
                with patch.object(scheduler.extract_links, "run"), \
                     patch.object(scheduler.extract_h1, "run"):
                    scheduler._run_scrape_job()

            warning_messages = [r for r in log_ctx.output if "WARNING" in r]
            self.assertTrue(
                len(warning_messages) > 0,
                "No WARNING log was emitted when the lock was already held",
            )
        finally:
            scheduler._scrape_lock.release()

    def test_lock_remains_held_by_original_owner_after_skip(self):
        """The pre-acquired lock must still be held after the skipped job returns."""
        acquired = scheduler._scrape_lock.acquire(blocking=False)
        self.assertTrue(acquired, "Test setup failed: could not pre-acquire the lock")
        try:
            with patch.object(scheduler.extract_links, "run"), \
                 patch.object(scheduler.extract_h1, "run"):
                scheduler._run_scrape_job()

            # The lock should still be held (by us, the original acquirer)
            self.assertTrue(
                scheduler._scrape_lock.locked(),
                "Lock was unexpectedly released by the skipped job",
            )
        finally:
            scheduler._scrape_lock.release()


class TestSchedulerLoop(unittest.TestCase):
    """
    Unit tests for scheduler._scheduler_loop().

    Covers:
    - The loop calls _run_scrape_job() and then waits 30 seconds before the next call
    - Setting _stop_event causes the loop to exit without executing another job
    - stop_scheduler() interrupts the sleep immediately rather than waiting the full 30 seconds

    Requirements: 2.1, 5.3, 6.3
    """

    def setUp(self):
        reset_scheduler_state()

    def test_loop_calls_run_scrape_job_and_waits_30_seconds(self):
        """
        The loop must call _run_scrape_job() once and then call _stop_event.wait(timeout=30)
        before checking the stop condition again.

        Requirements: 2.1
        """
        # We'll let the loop run one iteration, then stop it by having the
        # patched wait() set the stop event so the while condition fails.
        call_order = []

        def fake_run_scrape_job():
            call_order.append("_run_scrape_job")

        def fake_wait(timeout=None):
            # Record the wait call, then set the stop event so the loop exits.
            call_order.append(("_stop_event.wait", timeout))
            scheduler._stop_event.set()

        with patch.object(scheduler, "_run_scrape_job", side_effect=fake_run_scrape_job), \
             patch.object(scheduler._stop_event, "wait", side_effect=fake_wait):
            t = threading.Thread(target=scheduler._scheduler_loop, daemon=True)
            t.start()
            t.join(timeout=5)

        self.assertFalse(t.is_alive(), "Scheduler loop thread did not exit in time")
        self.assertIn("_run_scrape_job", call_order, "_run_scrape_job was not called")
        wait_calls = [c for c in call_order if isinstance(c, tuple) and c[0] == "_stop_event.wait"]
        self.assertTrue(len(wait_calls) >= 1, "_stop_event.wait was not called")
        self.assertEqual(
            wait_calls[0][1],
            30,
            f"_stop_event.wait was called with timeout={wait_calls[0][1]}, expected 30",
        )
        # Verify order: _run_scrape_job must come before the wait call
        job_index = call_order.index("_run_scrape_job")
        wait_index = call_order.index(wait_calls[0])
        self.assertLess(
            job_index,
            wait_index,
            "_run_scrape_job was not called before _stop_event.wait",
        )

    def test_stop_event_set_before_loop_prevents_job_execution(self):
        """
        If _stop_event is already set before the loop starts, _run_scrape_job()
        must never be called.

        Requirements: 5.3
        """
        # Pre-set the stop event so the while condition is False from the start.
        scheduler._stop_event.set()

        with patch.object(scheduler, "_run_scrape_job") as mock_job:
            t = threading.Thread(target=scheduler._scheduler_loop, daemon=True)
            t.start()
            t.join(timeout=5)

        self.assertFalse(t.is_alive(), "Scheduler loop thread did not exit in time")
        mock_job.assert_not_called()

    def test_stop_event_set_during_sleep_exits_quickly(self):
        """
        Setting _stop_event while the loop is sleeping must cause the loop to
        exit well within the 30-second sleep window (i.e., within ~1 second).

        This verifies that _stop_event.wait(timeout=30) is used instead of
        time.sleep(30), so stop_scheduler() can interrupt the sleep immediately.

        Requirements: 6.3
        """
        import time as _time

        # Allow _run_scrape_job to be a no-op but use the real _stop_event.wait
        # so we can test the actual interrupt behaviour.
        with patch.object(scheduler, "_run_scrape_job"):
            t = threading.Thread(target=scheduler._scheduler_loop, daemon=True)
            t.start()

            # Give the loop a moment to reach the _stop_event.wait() call.
            _time.sleep(0.1)

            # Set the stop event — this should interrupt the 30-second wait.
            start = _time.time()
            scheduler._stop_event.set()
            t.join(timeout=3)
            elapsed = _time.time() - start

        self.assertFalse(
            t.is_alive(),
            "Scheduler loop thread did not exit after stop event was set",
        )
        self.assertLess(
            elapsed,
            2.0,
            f"Loop took {elapsed:.2f}s to exit after stop event — expected < 2s "
            "(suggests time.sleep is used instead of _stop_event.wait)",
        )


class TestStartStopScheduler(unittest.TestCase):
    """
    Unit tests for start_scheduler() and stop_scheduler().

    Covers:
    - start_scheduler() creates a daemon thread and sets _is_running = True
    - Calling start_scheduler() twice logs a warning and does not create a second thread
    - stop_scheduler() sets the stop event
    - Calling stop_scheduler() when not running logs a warning
    - A stop-then-start cycle produces exactly one active thread with no orphans

    Requirements: 1.2, 1.3, 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2
    """

    def setUp(self):
        reset_scheduler_state()

    def tearDown(self):
        # Always clean up: signal stop and join any running thread.
        if scheduler._is_running:
            scheduler.stop_scheduler()
        if scheduler._scheduler_thread is not None and scheduler._scheduler_thread.is_alive():
            scheduler._scheduler_thread.join(timeout=3)

    def _patched_loop(self):
        """
        Replacement for _scheduler_loop that blocks on _stop_event so the real
        loop body (and scraping) never runs during tests.
        """
        scheduler._stop_event.wait()

    def test_start_scheduler_creates_daemon_thread_and_sets_is_running(self):
        """
        start_scheduler() must create a daemon thread and set _is_running = True.

        Requirements: 1.2, 1.3, 6.1
        """
        with patch.object(scheduler, "_scheduler_loop", side_effect=self._patched_loop):
            scheduler.start_scheduler()

        self.assertTrue(scheduler._is_running, "_is_running should be True after start_scheduler()")
        self.assertIsNotNone(scheduler._scheduler_thread, "_scheduler_thread should not be None")
        self.assertTrue(
            scheduler._scheduler_thread.is_alive(),
            "Scheduler thread should be alive after start_scheduler()",
        )
        self.assertTrue(
            scheduler._scheduler_thread.daemon,
            "Scheduler thread must be a daemon thread",
        )

    def test_start_scheduler_twice_logs_warning_and_no_second_thread(self):
        """
        Calling start_scheduler() a second time must log a warning and must not
        create an additional thread.

        Requirements: 6.4
        """
        with patch.object(scheduler, "_scheduler_loop", side_effect=self._patched_loop):
            scheduler.start_scheduler()
            first_thread = scheduler._scheduler_thread

            with self.assertLogs("scheduler", level="WARNING") as log_ctx:
                scheduler.start_scheduler()

        # The thread reference must not have changed
        self.assertIs(
            scheduler._scheduler_thread,
            first_thread,
            "start_scheduler() must not replace the existing thread on a duplicate call",
        )
        # Exactly one scheduler thread should be alive
        alive_scheduler_threads = [
            t for t in threading.enumerate()
            if t is scheduler._scheduler_thread
        ]
        self.assertEqual(
            len(alive_scheduler_threads),
            1,
            "There should be exactly one active scheduler thread after a duplicate start call",
        )
        warning_messages = [r for r in log_ctx.output if "WARNING" in r]
        self.assertTrue(
            len(warning_messages) > 0,
            "No WARNING log was emitted on a duplicate start_scheduler() call",
        )

    def test_stop_scheduler_sets_stop_event(self):
        """
        stop_scheduler() must set the stop event so the loop can exit.

        Requirements: 6.2, 6.3
        """
        with patch.object(scheduler, "_scheduler_loop", side_effect=self._patched_loop):
            scheduler.start_scheduler()

        self.assertFalse(
            scheduler._stop_event.is_set(),
            "Stop event should not be set before stop_scheduler() is called",
        )

        scheduler.stop_scheduler()

        self.assertTrue(
            scheduler._stop_event.is_set(),
            "Stop event must be set after stop_scheduler() is called",
        )
        self.assertFalse(
            scheduler._is_running,
            "_is_running must be False after stop_scheduler()",
        )

    def test_stop_scheduler_when_not_running_logs_warning(self):
        """
        Calling stop_scheduler() when the scheduler is not running must log a warning.

        Requirements: 6.5
        """
        self.assertFalse(scheduler._is_running, "Precondition: scheduler should not be running")

        with self.assertLogs("scheduler", level="WARNING") as log_ctx:
            scheduler.stop_scheduler()

        warning_messages = [r for r in log_ctx.output if "WARNING" in r]
        self.assertTrue(
            len(warning_messages) > 0,
            "No WARNING log was emitted when stop_scheduler() was called while not running",
        )

    def test_stop_then_start_produces_exactly_one_active_thread(self):
        """
        A stop-then-start cycle must produce exactly one active scheduler thread
        with no orphaned threads from the previous run.

        Requirements: 8.1, 8.2
        """
        with patch.object(scheduler, "_scheduler_loop", side_effect=self._patched_loop):
            # First start
            scheduler.start_scheduler()
            first_thread = scheduler._scheduler_thread
            self.assertTrue(first_thread.is_alive(), "First thread should be alive")

            # Stop
            scheduler.stop_scheduler()
            first_thread.join(timeout=3)
            self.assertFalse(first_thread.is_alive(), "First thread should have exited after stop")

            # Second start
            reset_scheduler_state()
            scheduler.start_scheduler()
            second_thread = scheduler._scheduler_thread

        self.assertIsNot(second_thread, first_thread, "A new thread should have been created")
        self.assertTrue(second_thread.is_alive(), "New thread should be alive after restart")
        self.assertFalse(first_thread.is_alive(), "Old thread must not be alive (no orphan)")
        self.assertTrue(scheduler._is_running, "_is_running must be True after restart")

        # Count active scheduler threads — should be exactly one
        alive_scheduler_threads = [
            t for t in threading.enumerate()
            if t is second_thread
        ]
        self.assertEqual(
            len(alive_scheduler_threads),
            1,
            "There should be exactly one active scheduler thread after stop-then-start",
        )


if __name__ == "__main__":
    unittest.main()
