"""Focused tests for the standalone certificate PDF renderer."""

import tempfile
import unittest
from pathlib import Path

from app.certificate_generator import generate_certificate


class CertificateGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output = Path(self.temp_dir.name) / "certificate.pdf"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_creates_pdf_with_certificate_details(self):
        result = generate_certificate(
            {"name": "Asha Kumar"},
            {
                "event_name": "Applied AI Workshop",
                "issue_date": "2026-10-08",
                "issuer_name": "Applied AI Team",
            },
            self.output,
        )

        contents = result.read_bytes()
        self.assertEqual(result, self.output)
        self.assertTrue(contents.startswith(b"%PDF-"))
        self.assertIn(b"Asha Kumar", contents)
        self.assertIn(b"Applied AI Workshop", contents)
        self.assertIn(b"2026-10-08", contents)
        self.assertIn(b"Applied AI Team", contents)
        self.assertIn(b"%%EOF", contents)

    def test_long_name_and_event_title_remain_in_pdf(self):
        long_name = "Alexandria-Catherine Montgomery-Worthington"
        long_event = "Advanced Applied Artificial Intelligence and Responsible Machine Learning Workshop"

        generate_certificate(
            {"name": long_name},
            {"event_name": long_event, "issue_date": "2026-10-08", "issuer_name": "AI Team"},
            self.output,
        )

        contents = self.output.read_bytes()
        for word in long_name.split():
            self.assertIn(word.encode("ascii"), contents)
        for word in long_event.split():
            self.assertIn(word.encode("ascii"), contents)

    def test_rejects_text_that_cannot_fit_readably(self):
        with self.assertRaisesRegex(ValueError, "too long to fit"):
            generate_certificate(
                {"name": "A" * 300},
                {"event_name": "Workshop", "issue_date": "2026-10-08", "issuer_name": "AI Team"},
                self.output,
            )

    def test_invalid_output_path_reports_normal_file_error(self):
        missing_parent = Path(self.temp_dir.name) / "missing" / "certificate.pdf"
        with self.assertRaises(OSError):
            generate_certificate(
                {"name": "Asha Kumar"},
                {"event_name": "Workshop", "issue_date": "2026-10-08", "issuer_name": "AI Team"},
                missing_parent,
            )


if __name__ == "__main__":
    unittest.main()
