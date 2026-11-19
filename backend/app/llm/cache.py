"""File cache for LLM answers, keyed by the exact inputs.

The same document, model, effort and prompt version always gives a cache
hit, so re-seeding or re-evaluating doesn't pay twice. Changing the prompt
bumps its entry in PROMPT_VERSIONS and those entries are ignored.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.llm.base import Extraction, FieldReading, Review, ReviewRisk, Usage

# Bump the one whose prompt or schema changed; the other call's cache stays valid.
PROMPT_VERSIONS = {"extract": "3", "review": "4"}


def key(purpose: str, *parts: str) -> str:
    version = PROMPT_VERSIONS[purpose]
    return hashlib.sha256("|".join((version, purpose, *parts)).encode()).hexdigest()[:32]


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
