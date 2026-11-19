"""Mask personal details before anything is written to logs.

Logs are read by more people and kept longer than the database, so they get
references and counts, never names, emails, phone numbers or ABNs.
"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b"), "[abn]"),
    (re.compile(r"(?:\+61\s?|\b0)[2-478](?:[\s-]?\d){8}\b"), "[phone]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
