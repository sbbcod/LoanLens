"""Step 1: turn a PDF into text, page by page."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pdfplumber


class NoTextError(Exception):
    """The PDF has no text layer — most likely a scanned image."""


@dataclass(frozen=True)
class Page:
    number: int  # 1-based, as a person would count
    text: str


def read_pages(source: Path | bytes) -> list[Page]:
    """Accepts a file path or the PDF's bytes (as stored in the database)."""
    with pdfplumber.open(BytesIO(source) if isinstance(source, bytes) else source) as pdf:
        pages = [Page(i, (p.extract_text() or "").strip()) for i, p in enumerate(pdf.pages, 1)]
    if not any(p.text for p in pages):
        raise NoTextError(
            "No text could be read from this PDF. It is probably a scanned document; "
            "scanned PDFs need OCR, which LoanLens does not support yet."
        )
    return pages


def as_prompt_text(pages: list[Page]) -> str:
    """Pages joined with markers, so the model can say which page a quote is on."""
    return "\n\n".join(f"=== Page {p.number} ===\n{p.text}" for p in pages)
