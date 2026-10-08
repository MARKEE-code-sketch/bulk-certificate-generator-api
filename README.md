# Bulk Certificate Generator API

A small Python API that accepts one request containing several recipients, creates one PDF certificate per valid recipient, records each outcome, and lets you check progress or download a finished PDF.

## How the pieces work

```text
POST request
    -> Module 1: validate shared details and each recipient row
    -> Module 2: save the job and recipient outcomes in SQLite
    -> Module 4: process valid rows one at a time
    -> Module 3: render each certificate as a PDF
    -> Module 2: save progress and results
    -> status endpoint / PDF download endpoint
```

- **Module 1 — `app/schemas.py`:** trims and validates the request. Invalid recipients remain visible as individual results; they do not stop valid rows.
- **Module 2 — `app/database.py`, `app/models.py`, `app/repositories.py`:** stores job and recipient status in a relational SQLite database.
- **Module 3 — `app/certificate_generator.py`:** creates the single predefined PDF design.
- **Module 4 — `app/job_service.py`:** processes each valid recipient and records success or failure.
- **Module 5 — `app/routes.py`, `app/main.py`:** HTTP endpoints and application setup.
- **Module 6 — this README and `scripts/benchmark_api.py`:** setup and repeatable throughput measurement.

## Requirements

Python 3.10 or newer is recommended. The project uses FastAPI, SQLite through SQLAlchemy, and ReportLab for PDF creation.

## Clone the public repository

Repository publication is in progress. Once it is published, clone it with:

```sh
git clone https://github.com/MARKEE-code-sketch/bulk-certificate-generator-api.git
cd bulk-certificate-generator-api
```

Then follow the setup instructions below. The repository contains the application and its documentation; local environment files, generated PDFs/database files, and the assignment documents are not part of the public source.

### Windows PowerShell setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, call the virtual-environment Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS/Linux setup

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Start the API

From the project folder:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On Windows, you can instead run `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

Open interactive API documentation at <http://127.0.0.1:8000/docs>. The default database is `data/certificates.db`, and generated files go to `data/certificates/`. These local paths can be changed with `DATABASE_URL` and `CERTIFICATE_OUTPUT_DIR` environment variables.

## Create a bulk certificate job

Send one POST request. The initial guardrail is **100 recipient rows per job**. This limits the size of a single request; it does not say how many HTTP requests the server can handle per second.

Save the following as `request.json`:

```json
{
  "event_name": "Applied AI Workshop",
  "issue_date": "2026-10-08",
  "issuer_name": "Applied AI Team",
  "recipients": [
    {"name": "Asha Kumar", "email": "asha@example.com"},
    {"name": "Ravi Shah", "email": "ravi@example.com"}
  ]
}
```

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/certificate-jobs -ContentType 'application/json' -InFile request.json
```

macOS/Linux:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/certificate-jobs \
  -H 'Content-Type: application/json' --data @request.json
```

The response is HTTP `202 Accepted`, with this shape:

```json
{
  "job_id": "<generated-id>",
  "status": "queued",
  "total_recipients": 2,
  "status_url": "/api/v1/certificate-jobs/<generated-id>"
}
```

The response means the work was accepted. The PDFs may still be generating. A request-wide problem (for example, an invalid date or more than 100 rows) returns a clear `422` response. A malformed individual recipient is stored as an `invalid` result while other rows continue.

## Check status and retrieve a certificate

Use the returned job ID:

```sh
curl http://127.0.0.1:8000/api/v1/certificate-jobs/<job_id>
```

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/certificate-jobs/<job_id>
```

The status response includes overall status, total/succeeded/invalid/failed counts, percent complete, and recipient results. Each successful row has a `certificate_url`; each invalid or failed row has a safe error message. Poll the status endpoint until the status is `completed` or `completed_with_errors`.

Download a successful recipient's PDF using its `recipient_id`:

```sh
curl -L http://127.0.0.1:8000/api/v1/certificate-jobs/<job_id>/recipients/<recipient_id>/certificate \
  --output certificate.pdf
```

PowerShell:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/certificate-jobs/<job_id>/recipients/<recipient_id>/certificate -OutFile certificate.pdf
```

The download response is `application/pdf`. A job or recipient that does not exist returns `404`; a certificate that is not ready returns `409`.

## Use the API from Postman

Start the local API first, then create requests in Postman. No API key is required for local use.

### Valid request

Create a `POST` request to `http://127.0.0.1:8000/api/v1/certificate-jobs`. Select **Body → raw → JSON** and use:

```json
{
  "event_name": "Applied AI Workshop",
  "issue_date": "2026-10-09",
  "issuer_name": "Applied AI Team",
  "recipients": [
    { "name": "Asha Kumar", "email": "asha@example.com" },
    { "name": "Ravi Shah", "email": "ravi@example.com" }
  ]
}
```

Select **Send**. The API should return `202 Accepted` with a `job_id`. Make a `GET` request to `http://127.0.0.1:8000/api/v1/certificate-jobs/{job_id}` (replace `{job_id}` with the returned value) to see progress and recipient IDs. For a successful recipient, make a `GET` request to the returned `certificate_url`; use the arrow beside **Send** and choose **Send and Download** to save the PDF.

### Invalid recipient row

Send another `POST` with one malformed recipient and one valid one:

```json
{
  "event_name": "Applied AI Workshop",
  "issue_date": "2026-10-09",
  "issuer_name": "Applied AI Team",
  "recipients": [
    { "name": "Asha Kumar", "email": "asha@example.com" },
    { "name": "Ravi Shah", "email": "not-an-email" }
  ]
}
```

This still returns `202 Accepted`: the job is valid, so the API records Ravi's row as `invalid` and continues processing Asha's certificate. Use the returned status URL. The final job should show `succeeded: 1`, `invalid: 1`, and `status: "completed_with_errors"`.

### Invalid shared field

To check request-level validation, change `issue_date` to `"not-a-date"` and send the request again. The API should return `422 Unprocessable Entity` because the job's shared details cannot be used to create certificates.

## Health check

```sh
curl http://127.0.0.1:8000/health
```

Expected response: `{"status":"ok"}`. This confirms that the API process answers; it does not check whether background work or disk storage is healthy.

## Tests

Run all tests from the project folder:

```sh
python -m unittest discover -s tests -v
```

With the Windows virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover request validation, database/repository behavior, PDF creation, job progress and per-recipient failure isolation, and HTTP behavior. They do not measure production-scale capacity.

Latest local verification (2026-10-09): **28 tests passed** with the command above.

## Measure HTTP throughput locally

The initial local measurement is recorded below. It is a measured workload, not a guaranteed maximum or a hosted-production capacity claim. Do not treat the 100-recipient job guardrail as a requests-per-second claim.

The benchmark starts a local Uvicorn process with a temporary database and PDF directory, concurrently submits small jobs, polls them to completion, reports request counts/status codes/errors and both job-submission and total HTTP request rates, then stops the server and removes temporary files. It measures local runs, not hosted or production capacity.

```sh
python scripts/benchmark_api.py --requests 10 --workers 2
```

Windows virtual-environment command:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_api.py --requests 10 --workers 2
```

### Initial measurement

- Run date: 2026-10-09.
- Environment: Windows 11 (build 26300), Python 3.14.2, 12 logical CPUs.
- Workload: 50 one-recipient certificate jobs, up to 5 concurrent client operations, run twice.
- Outcome: both runs accepted 50/50 POST requests (`202`) with 0 errors; status reads returned `200`.
- Timing across the two runs: 3.92–4.07 seconds end-to-end; 13.70–16.80 accepted jobs/second during submission and 24.57–29.09 total HTTP requests/second including status polling.

This verifies two runs of the small local workload above. The rate varied between runs, and SQLite/background work share one local process and disk, so these figures are only a rough local reference. They do not establish a maximum sustained rate or production capacity. Run the benchmark again on the target deployment before making a hosted capacity promise.

When sharing a new result, include the machine/OS, Python version, job count, worker count, elapsed time, total request count, status-code counts, errors, and both rates printed by the script. Run it more than once before using the result as a planning estimate.

## Design choices and limitations

- **FastAPI:** a small Python framework that provides HTTP routes and interactive docs.
- **SQLite + SQLAlchemy:** SQLite is a relational database that keeps local setup simple; SQLAlchemy provides the Python interface to it.
- **ReportLab:** draws the fixed certificate design into PDF files.
- **In-process background work:** the API returns a job ID while the same server process generates PDFs. This is simple, but it is not a durable job queue. If the process stops unexpectedly, unfinished work is not automatically resumed.
- **One process and local files:** this first version is intended for local demonstration. Local SQLite and disk files are not shared automatically between multiple app instances and may not persist on some hosting platforms.
- **No authentication:** anyone able to reach the API can submit jobs and download available certificates. Do not expose it publicly as-is.
- **No public-hosting guarantee:** no hosting provider, durable queue, object storage, or production deployment is configured here.
- **Request-size guardrail:** at most 100 recipient rows can be included in one job. This is a validation limit, not measured HTTP throughput.
- **Throughput:** not load-tested yet. No requests-per-second capacity is claimed.
