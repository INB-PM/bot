"""
Property-based tests for scheduler.py using Hypothesis.

# Tag: Feature: auto-scraper-scheduler, Property 1: Lock is always released after a scrape job
"""

import sys
import threading
import types
import unittest
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

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


# Strategies
exception_types = st.sampled_from([ValueError, RuntimeError, IOError, OSError])
injection_points = st.integers(min_value=0, max_value=2)
# 0 = before extract_links.run()  → extract_links.run raises
# 1 = between calls               → extract_h1.run raises
# 2 = after extract_h1.run()      → both calls succeed (no exception)


class TestLockAlwaysReleased(unittest.TestCase):
    """
    Property 1: Lock is always released after a scrape job.

    Validates: Requirements 3.3, 5.2
    """

    @given(exc_type=exception_types, injection_point=injection_points)
    @settings(max_examples=100)
    def test_lock_always_released(self, exc_type, injection_point):
        # Tag: Feature: auto-scraper-scheduler, Property 1: Lock is always released after a scrape job
        reset_scheduler_state()

        if injection_point == 0:
            # Raise inside extract_links.run() — before any scraping work
            with patch.object(scheduler.extract_links, "run", side_effect=exc_type("injected")):
                with patch.object(scheduler.extract_h1, "run"):
                    scheduler._run_scrape_job()

        elif injection_point == 1:
            # extract_links.run() succeeds, extract_h1.run() raises
            with patch.object(scheduler.extract_links, "run"):
                with patch.object(scheduler.extract_h1, "run", side_effect=exc_type("injected")):
                    scheduler._run_scrape_job()

        elif injection_point == 2:
            # Both calls succeed — no exception; lock should still be released normally
            with patch.object(scheduler.extract_links, "run"):
                with patch.object(scheduler.extract_h1, "run"):
                    scheduler._run_scrape_job()

        # Core assertion: lock must not be held after _run_scrape_job() returns
        self.assertFalse(
            scheduler._scrape_lock.locked(),
            f"Lock was still held after _run_scrape_job() with "
            f"injection_point={injection_point}, exc_type={exc_type.__name__}",
        )


class TestOverlapPrevention(unittest.TestCase):
    """
    Property 2: Overlap prevention.

    When the _scrape_lock is already held (simulating a running job),
    _run_scrape_job() must not call extract_links.run or extract_h1.run.

    Validates: Requirements 3.1, 3.2
    """

    # Tag: Feature: auto-scraper-scheduler, Property 2: Overlap prevention
    @given(st.integers(min_value=0, max_value=99))
    @settings(max_examples=100)
    def test_overlap_prevention(self, _unused):
        # Tag: Feature: auto-scraper-scheduler, Property 2: Overlap prevention
        reset_scheduler_state()

        # Pre-acquire the lock to simulate a job already in progress
        acquired = scheduler._scrape_lock.acquire(blocking=False)
        self.assertTrue(acquired, "Test setup failed: could not pre-acquire the lock")
        try:
            with patch.object(scheduler.extract_links, "run") as mock_links, \
                 patch.object(scheduler.extract_h1, "run") as mock_h1:
                scheduler._run_scrape_job()

                # Neither scraping function should have been called
                mock_links.assert_not_called()
                mock_h1.assert_not_called()
        finally:
            # Always release the pre-acquired lock so state is clean
            scheduler._scrape_lock.release()


class TestScrapeJobSequence(unittest.TestCase):
    """
    Property 5: Scrape job sequence is preserved.

    For any number of successful and failing scrape job executions,
    extract_links.run() is always called before extract_h1.run()
    when both calls are made.

    Validates: Requirements 7.1
    """

    # Tag: Feature: auto-scraper-scheduler, Property 5: Scrape job sequence is preserved
    @given(executions=st.lists(st.booleans(), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_scrape_job_sequence(self, executions):
        # Tag: Feature: auto-scraper-scheduler, Property 5: Scrape job sequence is preserved
        # executions: list of booleans where True = success, False = failure
        # (failure means extract_h1.run raises; extract_links.run always succeeds
        #  so that both calls are attempted and we can verify order)
        for success in executions:
            reset_scheduler_state()

            call_order = []

            def links_run():
                call_order.append("extract_links.run")

            def h1_run_success():
                call_order.append("extract_h1.run")

            def h1_run_failure():
                call_order.append("extract_h1.run")
                raise RuntimeError("simulated failure")

            h1_side_effect = h1_run_success if success else h1_run_failure

            with patch.object(scheduler.extract_links, "run", side_effect=links_run), \
                 patch.object(scheduler.extract_h1, "run", side_effect=h1_side_effect):
                scheduler._run_scrape_job()

            # When both calls were made, verify extract_links.run came first
            if "extract_links.run" in call_order and "extract_h1.run" in call_order:
                links_index = call_order.index("extract_links.run")
                h1_index = call_order.index("extract_h1.run")
                self.assertLess(
                    links_index,
                    h1_index,
                    f"extract_links.run (index {links_index}) was not called before "
                    f"extract_h1.run (index {h1_index}). Call order: {call_order}",
                )


class TestStopThenStartThreadCount(unittest.TestCase):
    """
    Property 3: Stop-then-start produces exactly one active thread.

    For any sequence of stop_scheduler() followed by start_scheduler() calls,
    the scheduler SHALL have exactly one active Scheduler_Thread and no
    orphaned threads from the previous run.

    Validates: Requirements 8.1, 8.2
    """

    # Tag: Feature: auto-scraper-scheduler, Property 3: Stop-then-start produces exactly one active thread
    @given(cycles=st.integers(min_value=1, max_value=10))
    @settings(max_examples=50)
    def test_stop_then_start_thread_count(self, cycles):
        # Tag: Feature: auto-scraper-scheduler, Property 3: Stop-then-start produces exactly one active thread
        reset_scheduler_state()

        with patch.object(scheduler, "_scheduler_loop", side_effect=lambda: scheduler._stop_event.wait()):
            previous_thread = None

            for cycle in range(cycles):
                # --- START phase ---
                scheduler.start_scheduler()

                current_thread = scheduler._scheduler_thread

                # _is_running must be True after start
                self.assertTrue(
                    scheduler._is_running,
                    f"Cycle {cycle}: _is_running should be True after start_scheduler()",
                )

                # There must be a thread reference
                self.assertIsNotNone(
                    current_thread,
                    f"Cycle {cycle}: _scheduler_thread should not be None after start_scheduler()",
                )

                # The current thread must be alive
                self.assertTrue(
                    current_thread.is_alive(),
                    f"Cycle {cycle}: _scheduler_thread should be alive after start_scheduler()",
                )

                # No orphaned thread from the previous cycle should still be alive
                if previous_thread is not None:
                    self.assertFalse(
                        previous_thread.is_alive(),
                        f"Cycle {cycle}: orphaned thread from previous cycle is still alive",
                    )

                # The new thread must be a different object from the previous one
                if previous_thread is not None:
                    self.assertIsNot(
                        current_thread,
                        previous_thread,
                        f"Cycle {cycle}: start_scheduler() reused the old thread instead of creating a new one",
                    )

                # --- STOP phase ---
                scheduler.stop_scheduler()

                # _is_running must be False after stop
                self.assertFalse(
                    scheduler._is_running,
                    f"Cycle {cycle}: _is_running should be False after stop_scheduler()",
                )

                # Wait for the thread to actually exit (short timeout to avoid hangs)
                current_thread.join(timeout=2)

                # After joining, the thread should no longer be alive
                self.assertFalse(
                    current_thread.is_alive(),
                    f"Cycle {cycle}: thread did not exit within timeout after stop_scheduler()",
                )

                previous_thread = current_thread


class TestDuplicateStartIsNoOp(unittest.TestCase):
    """
    Property 4: Duplicate start is a no-op.

    When the scheduler is already running, calling start_scheduler() N more
    times must not create additional threads — exactly one Scheduler_Thread
    remains alive throughout.

    Validates: Requirements 6.4
    """

    # Tag: Feature: auto-scraper-scheduler, Property 4: Duplicate start is a no-op
    @given(n=st.integers(min_value=1, max_value=20))
    @settings(max_examples=100)
    def test_duplicate_start_is_no_op(self, n):
        # Tag: Feature: auto-scraper-scheduler, Property 4: Duplicate start is a no-op
        reset_scheduler_state()

        with patch.object(scheduler, "_scheduler_loop", side_effect=lambda: scheduler._stop_event.wait()):
            # Start the scheduler once — this is the legitimate first start
            scheduler.start_scheduler()

            first_thread = scheduler._scheduler_thread
            self.assertIsNotNone(first_thread, "Expected a thread after first start_scheduler()")
            self.assertTrue(first_thread.is_alive(), "Thread should be alive after first start")

            # Call start_scheduler() N more times — each must be a no-op
            for _ in range(n):
                scheduler.start_scheduler()

            # The thread reference must still point to the original thread
            self.assertIs(
                scheduler._scheduler_thread,
                first_thread,
                "start_scheduler() created a new thread instead of being a no-op",
            )

            # Count alive threads whose name starts with "Thread-" that are the scheduler thread
            # More robustly: verify only one thread is alive that is our scheduler thread
            self.assertTrue(
                first_thread.is_alive(),
                "The original scheduler thread should still be alive",
            )

            # Verify _is_running is still True (not toggled by duplicate calls)
            self.assertTrue(scheduler._is_running, "_is_running should remain True")

        # Clean up: signal the thread to stop
        scheduler.stop_scheduler()
        first_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
