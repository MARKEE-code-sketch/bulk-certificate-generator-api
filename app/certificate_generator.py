"""Create a single, original certificate PDF using ReportLab."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Mapping

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


NAVY = HexColor("#18324B")
GOLD = HexColor("#B58B45")
INK = HexColor("#28323B")
MUTED = HexColor("#65717B")
PAPER = HexColor("#FBFAF6")


def _wrap_text(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    """Wrap words to the available width, splitting exceptionally long words."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = ""
        part = ""
        for character in word:
            if part and stringWidth(part + character, font_name, font_size) > max_width:
                lines.append(part)
                part = character
            else:
                part += character
        current = part
    if current:
        lines.append(current)
    return lines or [""]


def _fitting_lines(text: str, max_width: float, max_height: float,
                   font_name: str, start_size: int, min_size: int) -> tuple[list[str], int]:
    for size in range(start_size, min_size - 1, -1):
        lines = _wrap_text(text, font_name, size, max_width)
        if len(lines) * (size * 1.35) <= max_height:
            return lines, size
    raise ValueError("Text is too long to fit legibly on the certificate")


def generate_certificate(
    recipient: Mapping[str, object],
    shared_fields: Mapping[str, object],
    output_path: str | Path,
) -> Path:
    """Render a one-page certificate and return its path.

    ``recipient`` must contain ``name``. ``shared_fields`` must contain
    ``event_name``, ``issue_date`` and ``issuer_name``. These values are
    expected to have been validated by the request-validation module.
    """
    recipient_name = str(recipient["name"]).strip()
    event_name = str(shared_fields["event_name"]).strip()
    issue_date = shared_fields["issue_date"]
    date_text = issue_date.isoformat() if isinstance(issue_date, date) else str(issue_date)
    issuer_name = str(shared_fields["issuer_name"]).strip()

    if not all((recipient_name, event_name, date_text, issuer_name)):
        raise ValueError("Certificate fields must not be empty")

    path = Path(output_path)
    page_width, page_height = landscape(letter)
    pdf = canvas.Canvas(str(path), pagesize=(page_width, page_height), pageCompression=0)
    pdf.setTitle(f"Certificate - {recipient_name}")
    pdf.setAuthor(issuer_name)

    # Warm paper and a quiet double frame establish a formal, original design.
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(2)
    pdf.rect(30, 30, page_width - 60, page_height - 60, fill=0, stroke=1)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.8)
    pdf.rect(38, 38, page_width - 76, page_height - 76, fill=0, stroke=1)

    center = page_width / 2
    pdf.setFillColor(GOLD)
    pdf.setLineWidth(1.4)
    pdf.line(center - 62, 520, center + 62, 520)
    pdf.circle(center, 520, 2.5, fill=1, stroke=0)

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawCentredString(center, 476, "CERTIFICATE OF COMPLETION")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(center, 447, "THIS CERTIFICATE IS PRESENTED TO")

    name_lines, name_size = _fitting_lines(recipient_name, page_width - 130, 54,
                                           "Helvetica-Bold", 34, 18)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", name_size)
    name_y = 394 + (len(name_lines) - 1) * (name_size * 1.2) / 2
    for line in name_lines:
        pdf.drawCentredString(center, name_y, line)
        name_y -= name_size * 1.2

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(center, 326, "for successfully completing")

    event_lines, event_size = _fitting_lines(event_name, page_width - 150, 64,
                                             "Helvetica-Bold", 21, 12)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", event_size)
    event_y = 294 + (len(event_lines) - 1) * (event_size * 1.25) / 2
    for line in event_lines:
        pdf.drawCentredString(center, event_y, line)
        event_y -= event_size * 1.25

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(center, 223, f"Issued on {date_text}")

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.8)
    pdf.line(center - 105, 132, center + 105, 132)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(center, 111, issuer_name)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(center, 94, "ISSUER")

    pdf.showPage()
    pdf.save()
    return path
