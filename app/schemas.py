"""Request shapes and recipient-level validation for certificate jobs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


MAX_RECIPIENTS_PER_JOB = 100
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BulkRequest(BaseModel):
    """Shared certificate details and recipient rows as received from JSON."""

    model_config = ConfigDict(strict=True)

    event_name: str
    issue_date: date
    issuer_name: str
    recipients: list[Any]

    @field_validator("event_name", "issuer_name", mode="before")
    @classmethod
    def clean_required_text(cls, value: Any) -> Any:
        if not isinstance(value, str):
            raise ValueError("must be text")
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("issue_date", mode="before")
    @classmethod
    def parse_issue_date(cls, value: Any) -> date:
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            raise ValueError("must use YYYY-MM-DD format")
        try:
            parsed = date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError("must use YYYY-MM-DD format") from exc
        if parsed.isoformat() != value.strip():
            raise ValueError("must use YYYY-MM-DD format")
        return parsed

    @field_validator("recipients")
    @classmethod
    def validate_recipients_list(cls, value: list[Any]) -> list[Any]:
        if not value:
            raise ValueError("must contain at least one recipient")
        if len(value) > MAX_RECIPIENTS_PER_JOB:
            raise ValueError(
                f"cannot contain more than {MAX_RECIPIENTS_PER_JOB} recipients"
            )
        return value


@dataclass(frozen=True)
class ValidRecipient:
    index: int
    name: str
    email: str


@dataclass(frozen=True)
class InvalidRecipient:
    index: int
    message: str


@dataclass(frozen=True)
class ParsedBulkRequest:
    event_name: str
    issue_date: date
    issuer_name: str
    valid_recipients: list[ValidRecipient]
    invalid_recipients: list[InvalidRecipient]


def parse_bulk_request(payload: Any) -> ParsedBulkRequest:
    """Validate shared fields and classify each recipient row independently.

    Recipient indexes in invalid outcomes are one-based to match the row number
    a caller sees in the submitted list.
    """
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    try:
        request = BulkRequest.model_validate(payload)
    except ValidationError as exc:
        issue = exc.errors()[0]
        field = issue["loc"][0] if issue["loc"] else "request"
        reason = issue["msg"]
        if reason.startswith("Field required"):
            raise ValueError(f"Missing required field: {field}.") from None
        messages = {
            "event_name": "event_name must be non-empty text.",
            "issuer_name": "issuer_name must be non-empty text.",
            "issue_date": "issue_date must be a valid date in YYYY-MM-DD format.",
            "recipients": "recipients must be a non-empty list with no more than "
            f"{MAX_RECIPIENTS_PER_JOB} rows.",
        }
        raise ValueError(messages.get(field, f"Invalid {field} field.")) from None

    valid: list[ValidRecipient] = []
    invalid: list[InvalidRecipient] = []
    for index, row in enumerate(request.recipients, start=1):
        outcome = _parse_recipient(row, index)
        if isinstance(outcome, InvalidRecipient):
            invalid.append(outcome)
        else:
            valid.append(outcome)

    return ParsedBulkRequest(
        event_name=request.event_name,
        issue_date=request.issue_date,
        issuer_name=request.issuer_name,
        valid_recipients=valid,
        invalid_recipients=invalid,
    )


def _parse_recipient(row: Any, index: int) -> ValidRecipient | InvalidRecipient:
    if not isinstance(row, dict):
        return InvalidRecipient(index=index, message="Recipient row must be an object.")

    name = row.get("name")
    email = row.get("email")
    if not isinstance(name, str) or not name.strip():
        return InvalidRecipient(index=index, message="Recipient name must be non-empty text.")
    if not isinstance(email, str) or not _EMAIL_PATTERN.fullmatch(email.strip()):
        return InvalidRecipient(index=index, message="Recipient email must be a valid email address.")
    return ValidRecipient(index=index, name=name.strip(), email=email.strip())
