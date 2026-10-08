# Module 6: README and Measured Limits

## In plain words

The README is the project guide: a new developer should be able to install the project, run it, submit one bulk job, check it, and download a certificate.

## Proposed file

- `README.md` — setup, run, API examples, retrieval, tests, design choices, and limitations.

## Required README sections

1. What the API does and its simple module/data-flow diagram.
2. Python setup and dependency installation.
3. Start the local API and open interactive API docs.
4. Submit the example bulk request.
5. Check the job and download a PDF.
6. Run the test suite and understand what it covers.
7. Explain FastAPI, relational storage, PDF rendering, and background processing in plain terms.
8. State known limitations: single process, background work is not restart-safe, local file storage, and no authentication/public-hosting guarantee.
9. State tested limits only with the exact test environment and method.

## Limits: two different numbers

- **Recipients per job:** configured maximum items in one POST request. This is a request-size guardrail. Add a test at the limit and one above it.
- **API throughput:** number of HTTP requests or jobs served in a time window. Do not guess this. If measured, include machine details, test tool/settings, duration, concurrency, results, and errors. Otherwise say “not load-tested” rather than inventing a number.

## Tests and done check

- Follow the README steps in a clean virtual environment.
- Examples match the implemented API response fields.
- Capacity claims have repeatable evidence; unsupported claims are removed.
- Limitations are stated in plain language.

Done means a beginner can reproduce one full request-to-PDF flow using only the README.

## Implementation verification record

- Full test suite: 28 tests passed on 2026-10-09.
- Local benchmark: two runs of 50 one-recipient jobs each, with up to 5 concurrent client operations; all jobs were accepted and there were no request errors. The measured rates and environment are recorded in `README.md`.
- The certificate renderer was also rendered to an image and visually checked for spacing, hierarchy, and readable content.

## Interview explanation

“The README is the operating manual. It shows how to run the API, what it can handle based on actual checks, and what would need to change for a larger production deployment.”
