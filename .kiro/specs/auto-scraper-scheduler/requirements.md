# Requirements Document

## Introduction

This feature converts the existing manual Flask-based web scraping application into a fully automated scraping system. Currently, scraping is triggered by a user clicking a "Run Scraper" button in the browser, which calls the `/run` route. The goal is to remove this manual dependency and have the scraping process execute automatically on a fixed 30-second interval as soon as the application starts, while keeping all existing scraping logic in `extract_links.py` and `extract_h1.py` completely unchanged.

The automation must be production-friendly: it must prevent overlapping scrape executions, recover gracefully from errors, log all lifecycle events, and expose start/stop control functions so the scheduler can be paused or resumed without restarting the application.

## Glossary

- **Scheduler**: The component responsible for triggering scraping jobs on a fixed time interval.
- **Scrape_Job**: A single end-to-end execution of `extract_links.run()` followed by `extract_h1.run()`.
- **Scrape_Lock**: A threading lock that prevents more than one Scrape_Job from running concurrently.
- **Scheduler_Thread**: A background daemon thread that runs the scheduling loop independently of Flask's request-handling threads.
- **Interval**: The fixed wait period of 30 seconds between the end of one Scrape_Job and the start of the next.
- **Logger**: The Python `logging` module instance used to emit structured lifecycle messages to the console.
- **Flask_App**: The existing Flask application defined in `app.py`.

## Requirements

---

### Requirement 1: Automatic Startup

**User Story:** As a developer, I want the scraping automation to start automatically when the application starts, so that no manual action is required to begin data collection.

#### Acceptance Criteria

1. WHEN the Flask_App process starts, THE Scheduler SHALL begin executing Scrape_Jobs without any manual trigger.
2. THE Scheduler SHALL start on a Scheduler_Thread so that it does not block Flask's request-handling loop.
3. THE Scheduler_Thread SHALL be configured as a daemon thread so that it does not prevent the process from exiting when Flask shuts down.

---

### Requirement 2: Fixed-Interval Execution

**User Story:** As a developer, I want scraping to repeat every 30 seconds, so that data is refreshed on a predictable schedule.

#### Acceptance Criteria

1. WHEN a Scrape_Job completes, THE Scheduler SHALL wait exactly 30 seconds before starting the next Scrape_Job.
2. THE Scheduler SHALL log the timestamp of the next scheduled run after each Scrape_Job completes.
3. THE Scheduler SHALL use a single Scheduler_Thread and a single timing loop, so that no duplicate intervals or duplicate threads are created.

---

### Requirement 3: Overlap Prevention

**User Story:** As a developer, I want to ensure only one scraping process runs at a time, so that file output is not corrupted by concurrent writes.

#### Acceptance Criteria

1. WHEN a Scrape_Job is already running, THE Scheduler SHALL skip the next scheduled execution and log a warning that the previous job is still in progress.
2. THE Scheduler SHALL use the Scrape_Lock to determine whether a Scrape_Job is currently active before starting a new one.
3. WHEN the Scrape_Lock is acquired, THE Scheduler SHALL release the Scrape_Lock upon Scrape_Job completion regardless of whether the job succeeded or failed.

---

### Requirement 4: Lifecycle Logging

**User Story:** As a developer, I want clear console output for every scraping lifecycle event, so that I can monitor the system's behaviour in production.

#### Acceptance Criteria

1. WHEN a Scrape_Job starts, THE Logger SHALL emit a message containing the word "started" and the current timestamp.
2. WHEN a Scrape_Job completes successfully, THE Logger SHALL emit a message containing the word "completed" and the elapsed duration in seconds.
3. WHEN a Scrape_Job fails, THE Logger SHALL emit a message containing the word "error" and the exception details.
4. WHEN the Scheduler calculates the next run time, THE Logger SHALL emit a message containing the next scheduled run timestamp.
5. WHEN the Scheduler starts, THE Logger SHALL emit a message indicating that the automation has been activated.
6. WHEN the Scheduler stops, THE Logger SHALL emit a message indicating that the automation has been deactivated.

---

### Requirement 5: Error Resilience

**User Story:** As a developer, I want the scheduler to continue running even if a scrape fails, so that a single network or browser error does not halt the entire automation.

#### Acceptance Criteria

1. IF a Scrape_Job raises an exception, THEN THE Scheduler SHALL catch the exception, log the error details, and continue scheduling future Scrape_Jobs.
2. IF a Scrape_Job raises an exception, THEN THE Scheduler SHALL release the Scrape_Lock so that subsequent jobs are not permanently blocked.
3. WHILE the Scheduler is running, THE Scheduler SHALL execute the next Scrape_Job after the 30-second Interval regardless of whether the previous job succeeded or failed.

---

### Requirement 6: Start/Stop Control

**User Story:** As a developer, I want to be able to pause and resume the automation without restarting the application, so that I can perform maintenance or debugging without downtime.

#### Acceptance Criteria

1. THE Scheduler SHALL expose a `start_scheduler()` function that activates the scheduling loop.
2. THE Scheduler SHALL expose a `stop_scheduler()` function that deactivates the scheduling loop.
3. WHEN `stop_scheduler()` is called, THE Scheduler SHALL complete the currently running Scrape_Job before halting the loop.
4. WHEN `start_scheduler()` is called while the Scheduler is already running, THE Scheduler SHALL log a warning and take no further action, so that duplicate Scheduler_Threads are not created.
5. WHEN `stop_scheduler()` is called while the Scheduler is not running, THE Scheduler SHALL log a warning and take no further action.

---

### Requirement 7: Reuse of Existing Scraping Logic

**User Story:** As a developer, I want the automation to reuse the existing `/run` route handler logic internally, so that there is no duplication of scraping code.

#### Acceptance Criteria

1. THE Scheduler SHALL invoke `extract_links.run()` and `extract_h1.run()` in the same sequence as the existing `/run` route handler.
2. THE Scheduler SHALL NOT modify, copy, or duplicate any code inside `extract_links.py` or `extract_h1.py`.
3. THE Flask_App SHALL retain the `/run` route so that manual scraping via the browser remains available.

---

### Requirement 8: Memory Safety

**User Story:** As a developer, I want the scheduler to be free of memory leaks and duplicate timers, so that the application remains stable during long-running deployments.

#### Acceptance Criteria

1. THE Scheduler SHALL use exactly one Scheduler_Thread for the scheduling loop at any given time.
2. WHEN `stop_scheduler()` is called and then `start_scheduler()` is called again, THE Scheduler SHALL create a new single Scheduler_Thread without leaving orphaned threads.
3. THE Scheduler SHALL NOT use `threading.Timer` objects that reschedule themselves recursively, so that timer accumulation is prevented.
