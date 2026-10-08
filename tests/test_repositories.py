"""Isolated tests for the job and recipient repository."""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from app.database import create_database, initialize_database
from app.repositories import (
    create_job,
    get_job,
    get_recipient,
    update_job_status,
    update_recipient_result,
)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        self.engine, self.session_factory = create_database(f"sqlite:///{database_path}")
        initialize_database(self.engine)
        self.session = self.session_factory()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_create_and_retrieve_job_and_recipients(self):
        job = create_job(
            self.session,
            "job-1",
            [
                {"id": "recipient-1", "row_index": 1, "name": "Asha Kumar", "email": "asha@example.com"},
                {"id": "recipient-2", "row_index": 2, "name": "Ravi Shah", "email": "ravi@example.com"},
                {
                    "id": "recipient-3",
                    "row_index": 3,
                    "name": "Invalid Example",
                    "email": "invalid-email",
                    "status": "invalid",
                    "error_message": "Email address is invalid.",
                },
            ],
            {"event_name": "Applied AI Workshop", "issue_date": "2026-10-08", "issuer_name": "Applied AI Team"},
        )

        fetched = get_job(self.session, "job-1")
        self.assertEqual(job.status, "queued")
        self.assertEqual(fetched.total_recipients, 3)
        self.assertEqual(fetched.invalid_count, 1)
        self.assertEqual(fetched.event_name, "Applied AI Workshop")
        self.assertEqual(fetched.issue_date, "2026-10-08")
        self.assertEqual(fetched.issuer_name, "Applied AI Team")
        self.assertEqual(
            [row.name for row in fetched.recipients],
            ["Asha Kumar", "Ravi Shah", "Invalid Example"],
        )
        self.assertEqual([row.row_index for row in fetched.recipients], [1, 2, 3])
        self.assertIsNone(get_job(self.session, "missing"))

    def test_status_and_outcome_counts_are_updated(self):
        create_job(
            self.session,
            "job-2",
            [
                {"id": "recipient-1", "row_index": 1, "name": "Asha", "email": "asha@example.com"},
                {"id": "recipient-2", "row_index": 2, "name": "Ravi", "email": "ravi@example.com"},
            ],
            {"event_name": "Applied AI Workshop", "issue_date": "2026-10-08", "issuer_name": "Applied AI Team"},
        )

        update_job_status(self.session, "job-2", "processing")
        update_recipient_result(self.session, "recipient-1", "succeeded", "out/recipient-1.pdf")
        update_recipient_result(self.session, "recipient-2", "failed", error_message="Render failed")

        job = get_job(self.session, "job-2")
        self.assertEqual(job.status, "processing")
        self.assertEqual(job.succeeded_count, 1)
        self.assertEqual(job.failed_count, 1)
        self.assertEqual(get_recipient(self.session, "recipient-1").certificate_path, "out/recipient-1.pdf")

    def test_recipient_cannot_reference_missing_job(self):
        from app.models import RecipientResult

        self.session.add(
            RecipientResult(
                id="orphan", job_id="missing-job", row_index=1, name="Asha", email="asha@example.com", status="queued"
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()


if __name__ == "__main__":
    unittest.main()
