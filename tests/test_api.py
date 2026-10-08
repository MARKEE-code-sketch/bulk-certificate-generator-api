"""HTTP-level tests for the certificate API integration."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.job_service import JobService
from app.main import create_app
from app.repositories import get_job


VALID_BODY = {
    "event_name": "Applied AI Workshop",
    "issue_date": "2026-10-08",
    "issuer_name": "Applied AI Team",
    "recipients": [
        {"name": "Asha Kumar", "email": "asha@example.com"},
        {"name": "Ravi Shah", "email": "ravi@example.com"},
    ],
}


class CertificateApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.output_dir = root / "certificates"
        self.app = create_app(
            database_url=f"sqlite:///{root / 'api-test.db'}",
            output_dir=self.output_dir,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def submit_without_running_background_job(self, payload=None):
        with patch.object(JobService, "process_job"):
            return self.client.post(
                "/api/v1/certificate-jobs", json=payload or VALID_BODY
            )

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_rejects_invalid_shared_input(self):
        body = dict(VALID_BODY, issue_date="not-a-date")
        response = self.client.post("/api/v1/certificate-jobs", json=body)
        self.assertEqual(response.status_code, 422)
        self.assertIn("issue_date", response.json()["detail"])

    def test_submit_returns_accepted_job_and_status_url(self):
        response = self.submit_without_running_background_job()
        self.assertEqual(response.status_code, 202)
        result = response.json()
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["total_recipients"], 2)
        self.assertEqual(
            result["status_url"], f"/api/v1/certificate-jobs/{result['job_id']}"
        )

    def test_status_includes_counts_row_numbers_and_no_private_file_paths(self):
        body = dict(VALID_BODY)
        body["recipients"] = [
            {"name": "Asha Kumar", "email": "asha@example.com"},
            {"name": "", "email": "bad-email"},
        ]
        created = self.submit_without_running_background_job(body).json()

        response = self.client.get(created["status_url"])
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["invalid"], 1)
        self.assertEqual(result["progress_percent"], 50)
        self.assertEqual([row["row_index"] for row in result["recipients"]], [1, 2])
        self.assertNotIn("certificate_path", response.text)

    def test_unknown_job_returns_404(self):
        response = self.client.get("/api/v1/certificate-jobs/no-such-job")
        self.assertEqual(response.status_code, 404)

    def test_download_returns_pdf_for_successful_recipient(self):
        created = self.submit_without_running_background_job().json()
        pdf_path = self.output_dir / "ready.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\noriginal test file\n%%EOF")

        session = self.app.state.session_factory()
        try:
            job = get_job(session, created["job_id"])
            recipient = job.recipients[0]
            recipient.status = "succeeded"
            recipient.certificate_path = str(pdf_path)
            job.succeeded_count = 1
            session.commit()
            recipient_id = recipient.id
        finally:
            session.close()

        response = self.client.get(
            f"/api/v1/certificate-jobs/{created['job_id']}"
            f"/recipients/{recipient_id}/certificate"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_download_rejects_unknown_or_not_ready_recipient(self):
        created = self.submit_without_running_background_job().json()
        # Read the recipient ID from the public status endpoint, then request it
        # while it is queued to verify that unfinished PDFs are not downloadable.
        status = self.client.get(created["status_url"]).json()
        recipient_id = status["recipients"][0]["recipient_id"]

        response = self.client.get(
            f"/api/v1/certificate-jobs/{created['job_id']}"
            f"/recipients/{recipient_id}/certificate"
        )
        self.assertEqual(response.status_code, 409)

        response = self.client.get(
            f"/api/v1/certificate-jobs/{created['job_id']}"
            "/recipients/unknown-recipient/certificate"
        )
        self.assertEqual(response.status_code, 404)

    def test_download_rejects_recipient_from_another_job(self):
        first = self.submit_without_running_background_job().json()
        second = self.submit_without_running_background_job().json()
        first_recipient = self.client.get(first["status_url"]).json()["recipients"][0]["recipient_id"]

        response = self.client.get(
            f"/api/v1/certificate-jobs/{second['job_id']}"
            f"/recipients/{first_recipient}/certificate"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
