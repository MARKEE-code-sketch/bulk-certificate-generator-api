# Bulk Certificate Generator API Blueprint

**Status: Approved for implementation by the user's instruction on 2026-10-09.**

## 1. What, why, and how

**What:** Build a Python API that accepts one bulk request for certificates, validates each recipient, creates one PDF per valid recipient from a single fixed design, tracks the job and each recipient's outcome, and lets the client check status and retrieve generated certificates.

**Why:** An organization should be able to issue certificates to many participants with one request, while seeing which outputs succeeded or failed.

**How:** Keep validation, database access, PDF creation, job processing, and HTTP routes in separate modules. Test each module on its own, then connect them in the final API integration step.

## 2. Source of truth and boundaries

The sole product specification is `Bulk_Certificate_Generator_Backend_Assignment.docx`. This is a separate project from `Razorpay.md`.

### In scope

- Bulk job submission containing shared certificate details and a list of recipients.
- Recipient input validation and clear outcomes for invalid rows.
- One predefined certificate template; recipient-specific text is rendered into a PDF.
- Relational records for jobs and recipients, including status and progress.
- Per-recipient generation isolation: a failed certificate must not stop other recipients.
- API routes to create a job, read job progress/results, and download a generated certificate.
- Required automated tests and a README with setup, run, request, retrieval, testing, and design guidance.

### Out of scope unless the user later approves it

- Frontend, template editor, multiple template designs, authentication, payments, email delivery, public hosting, production queue infrastructure, and automatic certificate expiration/deletion.
- The separate Razorpay website-derived API assignment.

## 3. Requirement traceability

| Assignment requirement | Planned module/task | Test gate | Final evidence |
|---|---|---|---|
| Python and one listed web framework | M1 project setup: Python + FastAPI | App imports and route tests run | README setup and run commands |
| Relational database | M2 persistence: SQLAlchemy models and SQLite development database | Create/read/update job and recipient records | Database module tests and documented schema |
| Accept one bulk generation request | M5 API: create-job endpoint | Submit one request with multiple recipients | API test and README example |
| Validate recipient data | M1 request schemas and validation | Valid, missing, malformed, and invalid-recipient cases | Schema tests and API error/result examples |
| One predefined template with recipient data | M3 PDF renderer | Generate PDF and check expected text/output | Renderer tests and sample retrieval evidence |
| Track job status/progress and per-recipient results | M2 persistence + M4 processor + M5 status endpoint | Pending/running/finished transitions, counts, recipient outcomes | Service/API tests and example response |
| One failure must not stop other valid certificates | M4 per-recipient processing | Inject one renderer failure; verify later recipients still complete | Processor test showing both outcomes |
| Support bulk rather than one call per certificate | M5 create-job endpoint | One request results in multiple recipient records | Integration test and README example |
| Check progress/result and retrieve certificates | M5 status and download endpoints | Status response, successful download, missing job/certificate cases | API tests and documented retrieval command |
| Test all six listed areas | M1-M5 tests | Run full test suite after integration | Exact command and result in final report |
| README setup/run/submit/retrieve/design decisions | M6 documentation | Follow README from a clean setup | README review checklist |
| Explain and modify the implementation in interview | All modules and README | Walk through request-to-PDF data flow; no separate metric | Short architecture and data-flow explanation |

## 4. Proposed technical choices

| Choice | Proposal | Reason and tradeoff |
|---|---|---|
| Framework | FastAPI | Python framework listed by the assignment; straightforward request validation and API docs. Django REST Framework and Flask are valid alternatives, but not needed for this focused API. |
| Database | SQLite + SQLAlchemy for the initial implementation | SQLite is relational and keeps local setup simple. A hosted deployment would need durable database and file storage; deployment is not specified, so this blueprint does not add those services. |
| Certificate format/library | PDF using ReportLab | PDF is a familiar downloadable certificate format. One fixed layout is enough; no template editor or design system is needed. The assignment has no embedded artwork or visual template, so we will create an original, polished design instead of copying an online template. |
| Bulk processing | FastAPI background task, with job and recipient state saved in the database | Lets the request return a job ID while certificates are generated. It avoids adding Redis/Celery. Limitation: an in-process task is not a durable queue; a process restart may interrupt work. If restart-safe processing is required, we should revise the design to use a worker/queue. |
| Generated files | Local output directory, with file path stored per successful recipient | Simple for local development and demonstration. For multi-instance/cloud hosting, persistent object storage would be required and is outside current scope. |

### Certificate design proposal

- One-page landscape PDF with a light warm background, thin navy frame, restrained gold accent, and generous whitespace.
- Clear reading order: “Certificate of Completion”, large recipient name, event/course name, issue date, and issuer/signature line.
- Use typography and vector shapes created by our code; no copied logo, stock template, or fake organization seal.
- Keep all certificate wording fixed in the single template and fill only the approved request fields.
- Check layout with short and long names/course titles so text remains inside the page.

**Deployment note:** The assignment asks for an API, but does not specify a hosting platform or production deployment. The app will be runnable locally. We should not claim cloud production readiness with in-process tasks and local files.

### Capacity and documented limits

- The maximum 100 recipients per job is a **request-size guardrail**, not a claim about overall API throughput.
- README reports two measured local runs (50 one-recipient jobs, up to 5 concurrent client operations): all 100 total POST submissions were accepted across the runs with no errors; accepted-job rate ranged 13.70-16.80 jobs/second; total request rate including status polls ranged 24.57-29.09 requests/second.
- These are small local measurements, not maximum or hosted-production capacity promises. README includes the environment, method, and limitations.

## 5. Proposed API contract

The exact field names and rules are not specified by the assignment. Proposed starter shape for review:

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

Proposed routes:

- `POST /api/v1/certificate-jobs` — accept one bulk request and return a job ID promptly.
- `GET /api/v1/certificate-jobs/{job_id}` — return job status, total/success/failed counts, progress, and per-recipient outcomes; include a download route for successful certificates.
- `GET /api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/certificate` — download that recipient's PDF.
- `GET /health` — simple process check for local run and deployment diagnostics.

Proposed job states: `queued`, `processing`, `completed`, and `completed_with_errors`. Recipient states: `queued`, `processing`, `succeeded`, `invalid`, and `failed`. Progress is terminal recipient count divided by total recipient count; response also reports exact counts. These names are proposals, not assignment wording.

### Validation and failure proposal

- Reject a request if shared job-level data is missing or malformed, or the recipient list is empty.
- Record recipient-specific validation failures in the job result, and continue generating certificates for valid recipients.
- Report a generation error against only the affected recipient; continue the remaining recipients.
- Do not return stack traces or internal file paths from the API.

## 6. Modules and ownership

Modules are developed and checked independently. Parallel subagents may handle independent modules after blueprint approval, with non-overlapping file ownership. Integration stays with one owner after module checks.

| Module | Files (planned) | Responsibility / inputs / outputs | Depends on | Independent test gate |
|---|---|---|---|---|
| M1: Request validation | `app/schemas.py`, `tests/test_schemas.py` | Parse shared certificate details and recipient rows; return validated values or useful field/recipient errors. | None | Test valid input, malformed shared fields, invalid recipient fields, and empty recipients. |
| M2: Database and repository | `app/database.py`, `app/models.py`, `app/repositories.py`, `tests/test_repositories.py` | Store and retrieve job/recipient state and PDF paths in relational tables. Inputs are validated job/recipient data; outputs are persisted records. | M1 data shapes | Test record creation, lookup, status/progress update, and isolated test database setup. |
| M3: PDF certificate renderer | `app/certificate_generator.py`, `app/assets/` (only if needed), `tests/test_certificate_generator.py` | Turn one valid recipient plus shared details into one PDF file using the single fixed layout; return its path. | M1 field definitions | Test PDF is created and readable, includes expected text, and reports a controlled generation error. |
| M4: Job processing service | `app/job_service.py`, `tests/test_job_service.py` | Create job records, process recipients one at a time in the background, isolate errors, and update progress/outcomes. | M2, M3 | Use a fake renderer that fails for one recipient; verify others finish and job counts/status are correct. |
| M5: API and orchestrator | `app/main.py`, `app/routes.py`, `tests/test_api.py` | Wire validation, persistence, processing, and retrieval behind the documented HTTP endpoints. | M1-M4 | Test job creation, status/results, certificate download, and 404/validation responses through the test client. |
| M6: Documentation and handoff | `README.md` | Explain setup, run, tests, request/response, certificate retrieval, architecture, and tradeoffs. | M1-M5 contracts | Checklist: a fresh reader can follow commands and complete one bulk request and download. |

## 7. Data model proposal

- **GenerationJob:** ID, creation time, job status, shared event name/issue date/issuer name, total count, succeeded count, failed/invalid count, and optional error summary.
- **RecipientResult:** ID, job ID, original 1-based row number, recipient name/email, recipient status, certificate file path if successful, and safe error message if not.
- **Certificate request fields:** shared event/course name, issue date, issuer name, and recipient name/email (proposed; needs review).

Store only the fields needed to render certificates and report outcomes. Do not store secrets or unrelated personal information.

## 8. Testing and evidence plan

Each module gets a focused test file. After all modules pass their gates, M5 integration tests exercise the real HTTP contract using a temporary test database and temporary file directory. The full suite should cover:

1. Job creation with multiple recipients.
2. Shared and recipient-level validation.
3. PDF generation and content.
4. Job status and progress counts.
5. One recipient's generation failure while other recipients succeed.
6. Certificate retrieval, plus not-found cases.

Evidence includes the full test command and result, sample request/status responses, successful PDF download coverage, and a local load measurement recorded in `README.md`.

## 9. Risks and open decisions

| Item | Current assumption | Why it matters / decision point |
|---|---|---|
| Recipient fields | Name and email; email is for identification, not delivery | Confirm if certificates need participant ID, course name, completion date, or other fields. |
| Shared certificate fields | Event/course name, issue date, issuer name | Confirm the minimum text that should appear on the predefined certificate. |
| Invalid rows | Keep the job and report invalid recipients individually; process valid recipients | Matches failure-isolation intent, but confirm whether any invalid recipient should reject the whole request. |
| Batch size | Set a modest documented limit after selecting a value | Assignment says “large number” but specifies no count. We should avoid an arbitrary unlimited request. |
| Background durability | In-process background task | Simple, but does not guarantee recovery after process restart. Confirm if restart-safe work is expected. |
| Data retention | Keep generated PDFs and results until manually removed | No retention rule is given; local disk can fill over time. Choose a cleanup policy only if needed. |
| Public deployment/authentication | Local runnable service; no auth | Neither hosting nor auth is required in the DOCX. Public hosting would need revisiting these choices. |

## 10. Definition of done

- All requirements in the traceability table have corresponding implementation and evidence.
- One bulk request produces independent PDF results for valid recipients and clear outcomes for invalid or failed ones.
- One generation failure does not stop other recipients.
- The client can query job progress/results and retrieve a successful certificate.
- All six required test areas pass, and README commands are accurate.
- The user can explain the request flow, database records, background processing tradeoff, and PDF generation module.
- No Razorpay site/API functionality or unapproved optional feature has been added.

## 11. Approval gate

The user authorized module specifications and implementation. The detailed module specs live in `specs/`. Implementation preserved the one-template scope and did not add public hosting or optional product features.

## 12. Implementation and verification record

- Six module specs were prepared before application implementation.
- Independent modules were assigned to subagents; dependent job processing and HTTP integration followed after their data contracts were available.
- Full test command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` — **28 tests passed** on 2026-10-09.
- Local benchmark: two runs of 50 jobs with up to 5 concurrent client operations; 50/50 jobs accepted on each run with no errors. Measured rates and the environment are documented in `README.md`.
- A generated one-page PDF was visually rendered and checked. Its approved visual direction is an original navy/gold landscape design with a clear title, recipient name, event, issue date, and issuer.
- Limits remain: 100 recipient rows per job; single-process in-memory background scheduling; local SQLite and file storage; no authentication or public-hosting guarantee.
