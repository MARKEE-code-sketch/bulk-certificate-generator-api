# Bulk Certificate Generator API

A Python API that accepts one request for several people, creates a separate PDF certificate for each valid recipient, and reports the result for every row.

## Contents

- [What it does](#what-it-does)
- [Clone the repository](#clone-the-repository)
- [Set up the project](#set-up-the-project)
- [Run the API](#run-the-api)
- [Try it in Postman](#try-it-in-postman)
- [Get a certificate](#get-a-certificate)
- [Run the tests](#run-the-tests)
- [How it is built](#how-it-is-built)
- [Limits and measured performance](#limits-and-measured-performance)

## What it does

1. Accepts certificate details and a list of recipients in one `POST` request.
2. Checks shared fields and validates each recipient row.
3. Creates one PDF for each valid recipient and records each outcome.
4. Lets you check job progress and download successful certificates.

The API uses one predefined certificate design. An invalid recipient row does not prevent valid rows in the same job from being processed.

## Clone the repository

Clone the public repository with:

```sh
git clone https://github.com/MARKEE-code-sketch/bulk-certificate-generator-api.git
cd bulk-certificate-generator-api
```

## Set up the project

Python 3.10 or newer is recommended.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell does not allow virtual-environment activation, call its Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Windows Command Prompt

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

### macOS or Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the API

From the project directory, start the local server:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On Windows, if you are not activating the virtual environment, use:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep this terminal open while using the API. Open <http://127.0.0.1:8000/docs> for interactive API documentation. The health endpoint is <http://127.0.0.1:8000/health> and returns `{"status":"ok"}` when the API process is responding.

By default, the API stores its SQLite database at `data/certificates.db` and generated PDFs under `data/certificates/`. You can set `DATABASE_URL` and `CERTIFICATE_OUTPUT_DIR` to use different locations.

## Try it in Postman

Start the API first. No API key is needed for local use.

### 1. Submit a valid bulk request

Create a request with:

- **Method:** `POST`
- **URL:** `http://127.0.0.1:8000/api/v1/certificate-jobs`
- **Body:** select **raw**, then **JSON**

Paste this JSON and select **Send**:

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

The API responds with `202 Accepted` and a job ID:

```json
{
  "job_id": "<generated-job-id>",
  "status": "queued",
  "total_recipients": 2,
  "status_url": "/api/v1/certificate-jobs/<generated-job-id>"
}
```

`202 Accepted` means the job was received. Certificate generation may still be running.

### 2. Check the job and recipient results

Create a `GET` request using the `job_id` from the response:

```text
http://127.0.0.1:8000/api/v1/certificate-jobs/<job-id>
```

Replace `<job-id>` with the actual ID. The response includes job status, progress, recipient IDs, and a `certificate_url` for each successful recipient. Check again until the job status is `completed` or `completed_with_errors`.

### 3. Try an invalid recipient row

Submit another `POST` request with one valid and one invalid email:

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

The request still returns `202 Accepted`. The job continues: Asha's row can succeed, while Ravi's row is reported as `invalid`. The final job status is `completed_with_errors` when a job contains invalid or failed rows.

### 4. Try an invalid shared field

Submit a request with an invalid date, such as:

```json
{
  "event_name": "Applied AI Workshop",
  "issue_date": "not-a-date",
  "issuer_name": "Applied AI Team",
  "recipients": [
    { "name": "Asha Kumar", "email": "asha@example.com" }
  ]
}
```

The API returns `422 Unprocessable Entity`; a job is not created because the shared date applies to every certificate. The same `422` response is used when required shared fields are missing, text fields are blank, the recipient list is empty, or a request contains more than 100 recipient rows.

## Get a certificate

From the job status response, copy the `certificate_url` for a recipient whose status is `succeeded`. Make a `GET` request to that URL. For example:

```text
http://127.0.0.1:8000/api/v1/certificate-jobs/<job-id>/recipients/<recipient-id>/certificate
```

In Postman, use the arrow next to **Send** and select **Send and Download** to save the PDF. The endpoint returns `application/pdf` when the file is ready. A job or recipient that does not exist returns `404`; a certificate that is not ready returns `409`.

You can also download it from a terminal:

```powershell
Invoke-WebRequest `
  -Uri 'http://127.0.0.1:8000/api/v1/certificate-jobs/<job-id>/recipients/<recipient-id>/certificate' `
  -OutFile 'certificate.pdf'
```

Replace both IDs with values from your job response.

## Run the tests

Run the full test suite from the project directory:

```sh
python -m unittest discover -s tests -v
```

On Windows, you can use the virtual-environment Python directly:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover input validation, database records, PDF generation, job status and progress, per-recipient failure handling, and the HTTP endpoints. The latest recorded run on 2026-10-09 passed all 28 tests.

## How it is built

| Part | File(s) | Responsibility |
|---|---|---|
| Request validation | `app/schemas.py` | Checks shared certificate fields and classifies recipient rows as valid or invalid. |
| Database | `app/database.py`, `app/models.py`, `app/repositories.py` | Stores jobs, recipient outcomes, and certificate file locations in SQLite. |
| PDF generation | `app/certificate_generator.py` | Draws the fixed certificate design and writes a PDF for a valid recipient. |
| Job processing | `app/job_service.py` | Processes recipients and records each success or failure. |
| API setup and routes | `app/main.py`, `app/routes.py` | Starts the FastAPI application and provides job, status, health, and download endpoints. |

### Main design decisions

- **FastAPI** provides the HTTP API and interactive documentation at `/docs`.
- **SQLite and SQLAlchemy** provide relational storage with a simple local setup.
- **ReportLab** generates PDF certificates from one fixed design.
- **Background processing in the API process** lets the API return a job ID while it creates certificates. It avoids a separate queue service, but unfinished work is not automatically resumed after a process restart.
- **One result per recipient** keeps a single bad row or rendering failure from blocking the rest of the job.

## Limits and measured performance

- A job accepts at most **100 recipient rows**. This is a request-size limit, not a requests-per-second claim.
- Jobs run in the API process. There is no durable task queue, so a server restart can interrupt unfinished work.
- The database and PDF files are stored locally by default. They are not shared between multiple server instances.
- The API has no authentication. Keep it local or add access controls before exposing it to other users.
- The project does not configure cloud hosting or production storage.

A small local benchmark was run twice on Windows 11 (build 26300), Python 3.14.2, with 12 logical CPUs. Each run submitted 50 one-recipient jobs with up to five concurrent client operations. Both runs accepted all 50 jobs without errors. Submission measured 13.70 to 16.80 accepted jobs per second; the full run, including status polling, measured 24.57 to 29.09 HTTP requests per second over 3.92 to 4.07 seconds.

These numbers describe only those small local runs. They do not establish a maximum rate or guarantee performance on another machine or hosted service. To repeat the measurement:

```sh
python scripts/benchmark_api.py --requests 10 --workers 2
```

On Windows:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_api.py --requests 10 --workers 2
```
