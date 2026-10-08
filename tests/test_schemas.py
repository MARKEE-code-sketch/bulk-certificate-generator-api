import unittest
from datetime import date

from app.schemas import MAX_RECIPIENTS_PER_JOB, parse_bulk_request


def request_payload():
    return {
        "event_name": "  Applied AI Workshop  ",
        "issue_date": "2026-10-08",
        "issuer_name": "  Applied AI Team  ",
        "recipients": [
            {"name": "  Asha Kumar ", "email": " asha@example.com "},
            {"name": "Ravi Shah", "email": "ravi@example.com"},
        ],
    }


class BulkRequestValidationTests(unittest.TestCase):
    def test_valid_request_cleans_shared_and_recipient_text(self):
        parsed = parse_bulk_request(request_payload())

        self.assertEqual(parsed.event_name, "Applied AI Workshop")
        self.assertEqual(parsed.issue_date, date(2026, 10, 8))
        self.assertEqual(parsed.issuer_name, "Applied AI Team")
        self.assertEqual(
            [(person.index, person.name, person.email) for person in parsed.valid_recipients],
            [
                (1, "Asha Kumar", "asha@example.com"),
                (2, "Ravi Shah", "ravi@example.com"),
            ],
        )
        self.assertEqual(parsed.invalid_recipients, [])

    def test_invalid_recipient_does_not_reject_valid_rows(self):
        payload = request_payload()
        payload["recipients"].insert(1, {"name": "No email", "email": "bad"})

        parsed = parse_bulk_request(payload)

        self.assertEqual(
            [(person.index, person.name) for person in parsed.valid_recipients],
            [(1, "Asha Kumar"), (3, "Ravi Shah")],
        )
        self.assertEqual(len(parsed.invalid_recipients), 1)
        self.assertEqual(parsed.invalid_recipients[0].index, 2)
        self.assertEqual(
            parsed.invalid_recipients[0].message,
            "Recipient email must be a valid email address.",
        )

    def test_non_object_recipient_is_reported(self):
        payload = request_payload()
        payload["recipients"] = ["not an object"]

        parsed = parse_bulk_request(payload)

        self.assertEqual(parsed.valid_recipients, [])
        self.assertEqual(parsed.invalid_recipients[0].index, 1)
        self.assertEqual(parsed.invalid_recipients[0].message, "Recipient row must be an object.")

    def test_missing_shared_field_is_rejected_clearly(self):
        payload = request_payload()
        del payload["issuer_name"]

        with self.assertRaisesRegex(ValueError, "Missing required field: issuer_name"):
            parse_bulk_request(payload)

    def test_empty_shared_text_is_rejected(self):
        payload = request_payload()
        payload["event_name"] = "  "

        with self.assertRaisesRegex(ValueError, "event_name must be non-empty text"):
            parse_bulk_request(payload)

    def test_invalid_date_is_rejected(self):
        payload = request_payload()
        payload["issue_date"] = "08-10-2026"

        with self.assertRaisesRegex(ValueError, "issue_date must be a valid date"):
            parse_bulk_request(payload)

    def test_empty_recipients_are_rejected(self):
        payload = request_payload()
        payload["recipients"] = []

        with self.assertRaisesRegex(ValueError, "recipients must be a non-empty list"):
            parse_bulk_request(payload)

    def test_non_list_recipients_are_rejected_as_shared_error(self):
        payload = request_payload()
        payload["recipients"] = {"name": "Asha", "email": "asha@example.com"}

        with self.assertRaisesRegex(ValueError, "recipients must be a non-empty list"):
            parse_bulk_request(payload)

    def test_oversized_batch_is_rejected_with_configured_maximum(self):
        payload = request_payload()
        payload["recipients"] = [
            {"name": "Asha", "email": "asha@example.com"}
        ] * (MAX_RECIPIENTS_PER_JOB + 1)

        with self.assertRaisesRegex(
            ValueError, f"no more than {MAX_RECIPIENTS_PER_JOB} rows"
        ):
            parse_bulk_request(payload)

    def test_non_object_request_is_rejected_without_internal_details(self):
        with self.assertRaisesRegex(ValueError, "Request body must be a JSON object"):
            parse_bulk_request([])


if __name__ == "__main__":
    unittest.main()
