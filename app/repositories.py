"""Small persistence operations used by the job-processing and API modules."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import GenerationJob, RecipientResult


def create_job(
    session: Session,
    job_id: str,
    recipients: list[dict[str, str | int]],
    shared_fields: dict[str, str],
) -> GenerationJob:
    """Save one job and its recipient rows in a single transaction.

    Each recipient's ``row_index`` is the original, 1-based input row number.
    Shared fields are stored on the job so background work can reload them.
    """
    statuses = [recipient.get("status", "queued") for recipient in recipients]
    job = GenerationJob(
        id=job_id,
        status="queued",
        event_name=shared_fields["event_name"],
        issue_date=shared_fields["issue_date"],
        issuer_name=shared_fields["issuer_name"],
        total_recipients=len(recipients),
        succeeded_count=statuses.count("succeeded"),
        invalid_count=statuses.count("invalid"),
        failed_count=statuses.count("failed"),
    )
    job.recipients = [
        RecipientResult(
            id=recipient.get("id", str(uuid4())),
            row_index=recipient["row_index"],
            name=recipient["name"],
            email=recipient["email"],
            status=recipient.get("status", "queued"),
            error_message=recipient.get("error_message"),
        )
        for recipient in recipients
    ]
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job(session: Session, job_id: str) -> GenerationJob | None:
    """Fetch a job and all of its recipient results, or return None."""
    statement = (
        select(GenerationJob)
        .where(GenerationJob.id == job_id)
        .options(selectinload(GenerationJob.recipients))
    )
    return session.scalar(statement)


def get_recipient(session: Session, recipient_id: str) -> RecipientResult | None:
    """Fetch one recipient result, or return None."""
    return session.get(RecipientResult, recipient_id)


def update_job_status(session: Session, job_id: str, status: str) -> GenerationJob | None:
    """Change a job's lifecycle status and return the updated record."""
    job = session.get(GenerationJob, job_id)
    if job is None:
        return None
    job.status = status
    session.commit()
    session.refresh(job)
    return job


def update_recipient_result(
    session: Session,
    recipient_id: str,
    status: str,
    certificate_path: str | None = None,
    error_message: str | None = None,
) -> RecipientResult | None:
    """Update an outcome and refresh its parent job's outcome counts."""
    recipient = session.get(RecipientResult, recipient_id)
    if recipient is None:
        return None

    recipient.status = status
    recipient.certificate_path = certificate_path
    recipient.error_message = error_message
    session.flush()

    job = recipient.job
    results = session.scalars(
        select(RecipientResult).where(RecipientResult.job_id == job.id)
    ).all()
    job.succeeded_count = sum(result.status == "succeeded" for result in results)
    job.invalid_count = sum(result.status == "invalid" for result in results)
    job.failed_count = sum(result.status == "failed" for result in results)

    session.commit()
    session.refresh(recipient)
    return recipient
