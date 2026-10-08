# Module 5: HTTP API and Integration

## In plain words

This module is the front door. It receives HTTP requests, calls the already-built modules, and turns their results into HTTP responses.

## Why there are three main endpoints

They perform three different actions: submit a bulk job, check that job, and download one file. A PDF download is a file response, while job status is JSON, so combining them would make the client harder to use. `/health` is only a small diagnostic check.

## Proposed files

- `app/main.py` — creates the FastAPI application and attaches routes.
- `app/routes.py` — defines request paths and calls modules 1-4.
- `tests/test_api.py` — tests requests through FastAPI's test client.

## Endpoints

### A. Submit a bulk job

`POST /api/v1/certificate-jobs`

Input example:

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

Expected response (`202 Accepted`):

```json
{
  "job_id": "<generated-id>",
  "status": "queued",
  "total_recipients": 2,
  "status_url": "/api/v1/certificate-jobs/<generated-id>"
}
```

The response means “request accepted”; it does not promise that the PDFs are already finished.

### B. Check progress and results

`GET /api/v1/certificate-jobs/{job_id}`

Expected response shape:

```json
{
  "job_id": "<generated-id>",
  "status": "completed_with_errors",
  "total": 2,
  "succeeded": 1,
  "invalid": 0,
  "failed": 1,
  "progress_percent": 100,
  "recipients": [
    {
      "recipient_id": "<id-1>",
      "name": "Asha Kumar",
      "status": "succeeded",
      "certificate_url": "/api/v1/certificate-jobs/<generated-id>/recipients/<id-1>/certificate"
    },
    {
      "recipient_id": "<id-2>",
      "name": "Ravi Shah",
      "status": "failed",
      "error": "Certificate could not be generated."
    }
  ]
}
```

This is the endpoint a client polls for progress. Unknown job IDs return `404`.

### C. Download one certificate

`GET /api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/certificate`

Expected response: the PDF file with `Content-Type: application/pdf`. If the job/recipient is unknown or generation did not succeed, return a clear `404` or `409` response, not an internal file path.

### D. Process health

`GET /health` returns a small JSON response such as `{"status":"ok"}`. This confirms only that the API process is responding; it does not prove background jobs or file storage are healthy.

## Dependencies

Modules 1-4. This is the integration module and should be completed after those modules' independent checks pass.

## Tests and done check

- Submit multiple recipients with one HTTP call and receive a job ID.
- Read job status and recipient results.
- Download a successful PDF and verify its content type and bytes.
- Unknown IDs and invalid input return clear expected HTTP errors.
- Verify that no endpoint exposes stack traces, private paths, or secret configuration.

Done means the routes use the modules instead of duplicating their validation, database, PDF, or job-processing rules.

## Interview explanation

“The routes are the front door. They accept the bulk request, return a job ID, show saved progress, and send back a PDF when asked.”
