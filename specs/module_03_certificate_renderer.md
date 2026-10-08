# Module 3: Certificate PDF Renderer

## In plain words

This module takes one valid recipient and draws one finished certificate PDF using our single fixed design.

## Why it exists

Keeping PDF layout code in one place makes it easier to test and change without mixing page drawing into database or API code.

## Proposed files

- `app/certificate_generator.py` — draws and saves one PDF.
- `tests/test_certificate_generator.py` — checks files and their content/layout boundaries.
- `app/assets/` — only if a small original font or design asset is genuinely needed; no copied online template or logo.

## Proposed visual design

- Landscape page, warm white background, thin navy border, restrained gold detail.
- Strong centered title: “Certificate of Completion”.
- Recipient name is the largest text on the page.
- Event/course name, issue date, and issuer/signature line follow in a clear reading order.
- Comfortable margins and empty space make it look formal rather than crowded.
- Use an original vector layout and standard/bundled fonts; do not create a fake institution seal or logo.

## Input and output

Input: validated event name, issue date, issuer name, recipient name, and an output location.

Output: path to one readable PDF. Any controlled rendering error is returned to Module 4 for that recipient only.

## Dependencies

Module 1's field definitions. Module 4 calls this once per valid recipient.

## Tests and done check

- Create a PDF and confirm it opens as a PDF.
- Confirm the PDF includes the right recipient and event details.
- Try short and long names/course titles to ensure text remains within the page.
- Inject an invalid output path and confirm the renderer reports a normal error that Module 4 can record.

Done means output is one page, readable, professional, and uses only the one approved template.

## Interview explanation

“The renderer is a document printer: it receives clean certificate details and returns a PDF path. It does not know about HTTP requests or job progress.”
