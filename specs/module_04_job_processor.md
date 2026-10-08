# Module 4: Bulk Job Processor

## In plain words

This module is the factory-line supervisor. It takes a saved job, handles each recipient in order, asks the PDF renderer to make valid certificates, and records every result.

It is **not a public API route**. The client does not call Module 4 directly. The API starts it after accepting a job; the client checks its work through the job-status endpoint.

## Why it exists

Generating many PDFs can take longer than one quick web request. The client should receive a job ID and be able to check progress while the server works. One failed PDF should not stop the rest of the list.

## Proposed files

- `app/job_service.py` — creates/processes job state and updates recipient outcomes.
- `tests/test_job_service.py` — uses a fake renderer and a temporary database to test the work flow.

## What happens, step by step

1. API passes a validated bulk request to the service.
2. Service saves the job and all recipient rows in the database.
3. API schedules the service as a FastAPI in-process background task and returns the job ID.
4. Service marks the job `processing` and handles recipients one at a time.
5. If a recipient is invalid, it records `invalid` and moves on.
6. For a valid recipient, it calls Module 3 to render a PDF.
7. It records `succeeded` and the PDF path if rendering works. If it fails, it records `failed` and a safe reason.
8. It continues to the next recipient and finally marks the job `completed` or `completed_with_errors`.

Module 2 is the shared ledger: this service updates it after each recipient, and the status API reads it to show progress.

## Progress example

If a job has four recipients and two are in a final state, progress is `2 / 4 = 50%`. The response also gives exact successful, invalid, and failed counts so the percentage is not the only useful detail.

## Dependencies

Module 2 database/repository and Module 3 PDF renderer. It consumes Module 1's accepted data shape.

## Important limitation

FastAPI's in-process background task is the simplest option for this assignment, but it is not a durable queue. If the process stops unexpectedly, unfinished work may not resume automatically. The database records progress already saved, but reliable resumption would require a separate worker/queue, which is outside this first version.

## Tests and done check

- Job moves from queued to processing to a final status.
- Progress and counts update after each recipient.
- Fake renderer fails for one recipient; later recipients still get processed.
- Invalid recipient is recorded and never sent to the renderer.
- Tests do not require real background timing or external services.

Done means the failure-isolation test proves that one bad item does not cancel the whole batch.

## Interview explanation

“The API returns a job number quickly. This service does the slower per-person work and updates the database after each person. If one PDF fails, it records that failure and continues.”
