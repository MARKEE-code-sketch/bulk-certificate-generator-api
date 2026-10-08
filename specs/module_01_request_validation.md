# Module 1: Request Validation

## In plain words

This module checks the request before we save work or create PDFs. It tells us whether the shared certificate details are usable and which recipient rows have problems.

## Why it exists

Bad input should produce a useful explanation instead of a crash or a broken certificate. A bad recipient should not block valid recipients in the same bulk request.

## Proposed files

- `app/schemas.py` — request and response data shapes.
- `tests/test_schemas.py` — focused validation tests.

## Input and output

Input is the JSON sent to `POST /api/v1/certificate-jobs`.

Proposed shared fields:

- `event_name`: required non-empty text.
- `issue_date`: required valid date (`YYYY-MM-DD`).
- `issuer_name`: required non-empty text.
- `recipients`: a non-empty list of recipient rows.

Proposed recipient fields:

- `name`: required non-empty text.
- `email`: required valid email format, used to identify the recipient only. The system will not email certificates.

Output is a cleaned shared request plus recipient rows marked valid or invalid with a simple reason. Shared-field errors or an empty list reject the whole request. Recipient-level errors are retained for the job result; valid recipients continue.

## Rules

- Trim leading/trailing spaces from text fields.
- Reject missing shared fields, invalid dates, empty recipient lists, and malformed JSON fields with clear messages.
- Store invalid recipient rows as `invalid` outcomes; do not send them to the PDF renderer.
- Set a maximum recipients-per-job guardrail. Its exact value will be recorded in configuration and README; it is not an API throughput claim.

## Dependencies

None. Other modules use this module's clean data shapes.

## Tests and done check

- Valid request with several recipients is accepted.
- Missing shared information, malformed date, or empty list is rejected clearly.
- Invalid recipient is identified while a valid recipient in the same request remains valid.
- Oversized batch is rejected with the configured maximum in the message.

Done means every rule above has a focused test and error messages do not expose stack traces or machine paths.

## Interview explanation

“This is the API's input check. It catches request-wide errors early and marks bad recipient rows individually, so valid people can still receive certificates.”
