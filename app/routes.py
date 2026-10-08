"""HTTP routes for creating, monitoring, and downloading certificate jobs."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.repositories import get_job, get_recipient
from app.schemas import parse_bulk_request


router = APIRouter()


def get_session(request: Request):
    """Yield one database session for the duration of the request."""
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/v1/certificate-jobs", status_code=202)
def submit_job(
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    try:
        parsed = parse_bulk_request(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    service = request.app.state.job_service
    job_id = service.create_job(parsed)
    background_tasks.add_task(service.process_job, job_id)
    return {
        "job_id": job_id,
        "status": "queued",
        "total_recipients": len(parsed.valid_recipients) + len(parsed.invalid_recipients),
        "status_url": f"/api/v1/certificate-jobs/{job_id}",
    }


@router.get("/api/v1/certificate-jobs/{job_id}")
def read_job(job_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Certificate job not found.")

    recipients = []
    for result in sorted(job.recipients, key=lambda item: item.row_index):
        row: dict[str, object] = {
            "recipient_id": result.id,
            "row_index": result.row_index,
            "name": result.name,
            "status": result.status,
        }
        if result.status == "succeeded":
            row["certificate_url"] = (
                f"/api/v1/certificate-jobs/{job.id}/recipients/{result.id}/certificate"
            )
        elif result.status in {"invalid", "failed"}:
            row["error"] = result.error_message or "Certificate could not be generated."
        recipients.append(row)

    total = job.total_recipients
    succeeded = sum(result.status == "succeeded" for result in job.recipients)
    invalid = sum(result.status == "invalid" for result in job.recipients)
    failed = sum(result.status == "failed" for result in job.recipients)
    completed = succeeded + invalid + failed
    progress = round(completed * 100 / total) if total else 100
    return {
        "job_id": job.id,
        "status": job.status,
        "total": total,
        "succeeded": succeeded,
        "invalid": invalid,
        "failed": failed,
        "progress_percent": progress,
        "recipients": recipients,
    }


@router.get("/api/v1/certificate-jobs/{job_id}/recipients/{recipient_id}/certificate")
def download_certificate(
    job_id: str,
    recipient_id: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Certificate job not found.")

    recipient = get_recipient(session, recipient_id)
    if recipient is None or recipient.job_id != job_id:
        raise HTTPException(status_code=404, detail="Certificate recipient not found.")
    if recipient.status != "succeeded" or not recipient.certificate_path:
        raise HTTPException(status_code=409, detail="Certificate is not ready for download.")

    path = Path(recipient.certificate_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Certificate file not found.")

    safe_name = "certificate.pdf"
    return FileResponse(path, media_type="application/pdf", filename=safe_name)
