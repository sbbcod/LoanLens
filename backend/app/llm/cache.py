"""File cache for LLM answers, keyed by the exact inputs.

The same document, model, effort and prompt version always gives a cache
hit, so re-seeding or re-evaluating doesn't pay twice. Changing the prompt
bumps PROMPT_VERSION and every entry is ignored.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.llm.base import Extraction, FieldReading, Review, ReviewRisk, Usage

PROMPT_VERSION = "1"


def key(*parts: str) -> str:
    return hashlib.sha256("|".join((PROMPT_VERSION, *parts)).encode()).hexdigest()[:32]


def load(cache_dir: Path, k: str) -> dict[str, Any] | None:
    path = cache_dir / f"{k}.json"
    return json.loads(path.read_text()) if path.exists() else None


def save(cache_dir: Path, k: str, data: Any) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{k}.json").write_text(json.dumps(asdict(data), default=str))


def extraction_from(data: dict[str, Any]) -> Extraction:
    return Extraction(
        fields={n: FieldReading(**r) for n, r in data["fields"].items()},
        summary=data["summary"],
        usage=Usage(**data["usage"]),
    )


def review_from(data: dict[str, Any]) -> Review:
    return Review(risks=[ReviewRisk(**r) for r in data["risks"]],
                  usage=Usage(**data["usage"]) if data["usage"] else None)
