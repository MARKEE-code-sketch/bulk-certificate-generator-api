"""Unit tests for bulk job creation and recipient failure isolation."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.database import create_database, initialize_database
from app.job_service import JobService
from app.repositories import get_job
from app.schemas import parse_bulk_request


class JobServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.engine, self.session_factory = create_database("sqlite://")
        initialize_database(self.engine)
        self.addCleanup(self.engine.dispose)
        self.output_dir = Path(self.temp_dir.name) / "certificates"

    def load_job(self, job_id: str):
        with self.session_factory() as session:
            return get_job(session, job_id)

    def test_create_job_persists_all_recipients_and_shared_fields(self) -> None:
        parsed = parse_bulk_request(
            {
                "event_name": "Applied AI Workshop",
                "issue_date": "2026-10-08",
                "issuer_name": "Applied AI Team",
                "recipients": [
                    {"name": "Asha Kumar", "email": "asha@example.com"},
                    {"name": "Broken", "email": "not-an-email"},
                    {"name": "Ravi Shah", "email": "ravi@example.com"},
                ],
            }
        )
        service = JobService(self.session_factory, self.output_dir)

        job_id = service.create_job(parsed)
        job = self.load_job(job_id)

        self.assertEqual(job.status, "queued")
        self.assertEqual(job.total_recipients, 3)
        self.assertEqual(job.event_name, "Applied AI Workshop")
        self.assertEqual([row.row_index for row in job.recipients], [1, 2, 3])
        self.assertEqual([row.status for row in job.recipients], ["queued", "invalid", "queued"])
        self.assertEqual(job.recipients[1].name, "Row 2")
        self.assertTrue(job.recipients[1].error_message)

    def test_process_job_continues_after_render_error_and_skips_invalid(self) -> None:
        parsed = parse_bulk_request(
            {
                "event_name": "Applied AI Workshop",
                "issue_date": "2026-10-08",
                "issuer_name": "Applied AI Team",
                "recipients": [
                    {"name": "Asha Kumar", "email": "asha@example.com"},
                    {"name": "Broken", "email": "not-an-email"},
                    {"name": "Ravi Shah", "email": "ravi@example.com"},
                ],
            }
        )
        rendered: list[str] = []

        def renderer(recipient, shared_fields, output_path):
            rendered.append(recipient["name"])
            self.assertEqual(shared_fields["event_name"], "Applied AI Workshop")
            if recipient["name"] == "Asha Kumar":
                raise RuntimeError("internal path or provider details are not user-safe")
            Path(output_path).write_bytes(b"fake pdf")
            return Path(output_path)

        service = JobService(self.session_factory, self.output_dir, renderer=renderer)
        job_id = service.create_job(parsed)
        service.process_job(job_id)

        job = self.load_job(job_id)
        recipients = sorted(job.recipients, key=lambda row: row.row_index)
        self.assertEqual(rendered, ["Asha Kumar", "Ravi Shah"])
        self.assertEqual([row.status for row in recipients], ["failed", "invalid", "succeeded"])
        self.assertEqual(job.status, "completed_with_errors")
        self.assertEqual((job.succeeded_count, job.invalid_count, job.failed_count), (1, 1, 1))
        self.assertEqual(recipients[0].error_message, "Certificate generation failed.")
        self.assertTrue(recipients[2].certificate_path)
        self.assertTrue(Path(recipients[2].certificate_path).is_file())

    def test_process_job_completes_when_every_render_succeeds(self) -> None:
        parsed = parse_bulk_request(
            {
                "event_name": "Applied AI Workshop",
                "issue_date": "2026-10-08",
                "issuer_name": "Applied AI Team",
                "recipients": [{"name": "Asha Kumar", "email": "asha@example.com"}],
            }
        )

        def renderer(_recipient, _shared_fields, output_path):
            Path(output_path).write_bytes(b"fake pdf")

        service = JobService(self.session_factory, self.output_dir, renderer=renderer)
        job_id = service.create_job(parsed)
        service.process_job(job_id)

        job = self.load_job(job_id)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.succeeded_count, 1)
        self.assertEqual(job.recipients[0].status, "succeeded")


if __name__ == "__main__":
    unittest.main()
