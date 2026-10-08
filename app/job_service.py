"""Create bulk jobs and process recipient certificates one at a time."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.certificate_generator import generate_certificate
from app.repositories import (
    create_job as save_job,
    get_job,
    update_job_status,
    update_recipient_result,
)
from app.schemas import ParsedBulkRequest


class JobService:
    """Coordinate persistence and rendering for a single-process job worker."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        output_dir: str | Path,
        renderer: Callable = generate_certificate,
    ) -> None:
        self.session_factory = session_factory
        self.output_dir = Path(output_dir)
        self.renderer = renderer

    def create_job(self, parsed: ParsedBulkRequest) -> str:
        """Persist a job and every recipient outcome in one repository call."""
        job_id = str(uuid4())
        rows: list[dict[str, object]] = []

        for recipient in parsed.valid_recipients:
            row_index = getattr(recipient, "row_index", getattr(recipient, "index", 0))
            rows.append(
                {
                    "row_index": row_index,
                    "name": recipient.name,
                    "email": recipient.email,
                    "status": "queued",
                }
            )

        for recipient in parsed.invalid_recipients:
            row_index = getattr(recipient, "row_index", getattr(recipient, "index", 0))
            name = getattr(recipient, "name", None)
            email = getattr(recipient, "email", None)
            rows.append(
                {
                    "row_index": row_index,
                    "name": name.strip() if isinstance(name, str) and name.strip() else f"Row {row_index}",
                    "email": email.strip() if isinstance(email, str) else "",
                    "status": "invalid",
                    "error_message": recipient.message,
                }
            )

        rows.sort(key=lambda row: int(row["row_index"]))
        shared_fields = {
            "event_name": parsed.event_name,
            "issue_date": parsed.issue_date.isoformat(),
            "issuer_name": parsed.issuer_name,
        }
        with self.session_factory() as session:
            save_job(session, job_id, rows, shared_fields)
        return job_id

    def process_job(self, job_id: str) -> None:
        """Render valid recipients sequentially, recording errors and continuing."""
        with self.session_factory() as session:
            job = get_job(session, job_id)
            if job is None:
                return
            recipients = sorted(job.recipients, key=lambda row: row.row_index)
            shared_fields = {
                "event_name": job.event_name,
                "issue_date": job.issue_date,
                "issuer_name": job.issuer_name,
            }

        with self.session_factory() as session:
            update_job_status(session, job_id, "processing")

        for recipient in recipients:
            if recipient.status == "invalid":
                continue

            recipient_id = recipient.id
            output_path = self.output_dir / f"{uuid4()}.pdf"
            with self.session_factory() as session:
                update_recipient_result(session, recipient_id, "processing")

            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                self.renderer(
                    {"name": recipient.name, "email": recipient.email},
                    shared_fields,
                    output_path,
                )
            except Exception:
                with self.session_factory() as session:
                    update_recipient_result(
                        session,
                        recipient_id,
                        "failed",
                        error_message="Certificate generation failed.",
                    )
                continue

            with self.session_factory() as session:
                update_recipient_result(
                    session,
                    recipient_id,
                    "succeeded",
                    certificate_path=str(output_path),
                )

        with self.session_factory() as session:
            final_job = get_job(session, job_id)
            if final_job is None:
                return
            has_errors = any(row.status in {"invalid", "failed"} for row in final_job.recipients)
            update_job_status(
                session,
                job_id,
                "completed_with_errors" if has_errors else "completed",
            )
