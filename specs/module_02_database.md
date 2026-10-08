# Module 2: Database and Repository

## In plain words

This module remembers the job and the result for every recipient, so a client can ask later whether work is waiting, running, successful, or failed.

## Why it exists

The API and background processor run at different times. Shared database records are how they communicate progress and how status survives an API request finishing.

## Proposed files

- `app/database.py` — opens database sessions and creates tables.
- `app/models.py` — defines the job and recipient tables.
- `app/repositories.py` — small save/find/update operations.
- `tests/test_repositories.py` — database behavior tests using an isolated test database.

## Data to store

**GenerationJob:** unique ID, created time, status, event name, issue date, issuer name, recipient total, and success/failure/invalid counts. Shared certificate details are saved so the background processor can reload them after the HTTP request returns.

**RecipientResult:** unique ID, parent job ID, original 1-based row number, recipient name/email, status, optional PDF path, and a safe error message. Invalid data may not include a name or email, so the row number and validation reason still identify it.

Do not store secrets or unrelated personal information. Keep PDF bytes in files, not inside the database.

## Dependencies

Module 1's field definitions. The job service and API use this module to save or read state.

## Tests and done check

- Create and retrieve a job and its recipient records.
- Change a recipient status and see correct counts/progress when reading the job.
- A recipient cannot be attached to a nonexistent job.
- Tests use a temporary database and do not modify real project data.

Done means repository functions are small, predictable, and do not contain HTTP or PDF drawing logic.

## Interview explanation

“The relational database is the job ledger. It stores who was requested and each person's current result; the actual PDF is stored as a file.”
