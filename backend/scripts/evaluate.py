"""Score the pipeline against the ground truth for the ten samples.

    .venv/bin/python scripts/evaluate.py            # print results
    .venv/bin/python scripts/evaluate.py --write    # also write docs/eval_results.md

Uses whichever provider LLM_PROVIDER selects. With the mock provider the
scores only prove the plumbing; run it with LLM_PROVIDER=anthropic to
measure a real model.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.llm import get_provider  # noqa: E402
from app.pipeline.analyse import analyse  # noqa: E402
from app.pipeline.fields import FIELDS, FieldSpec  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
SAMPLES = BACKEND / "data" / "samples"
RESULTS_MD = BACKEND.parent / "docs" / "eval_results.md"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def correct(spec: FieldSpec, got, want) -> bool:
    if want is None or got is None:
        return got is None and want is None
    if spec.kind == "money":
        return abs(got - want) <= want * 0.005
    if spec.kind in ("percent", "integer"):
        return abs(float(got) - float(want)) < 0.05
    if spec.name == "exit_strategy":  # free text: same meaning, different words is fine
        return fuzz.token_set_ratio(_norm(got), _norm(want)) >= 80
    return _norm(str(got)) == _norm(str(want))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write docs/eval_results.md")
    args = parser.parse_args()

    settings = get_settings()
    provider = get_provider(settings)
    truth = json.loads((SAMPLES / "ground_truth.json").read_text())["samples"]

    per_field = defaultdict(lambda: [0, 0])  # name -> [correct, total]
    nulls = [0, 0]                           # correct nulls, expected nulls
    ungrounded = 0
    values_given = 0
    flag_hits = 0
    low_conf_hits = [0, 0]
    cost = latency = 0.0
    failures: list[str] = []
    rows: list[str] = []

    for sample in truth:
        result = analyse(SAMPLES / f"{sample['id']}.pdf", provider, settings)
        wrong = []
        for spec in FIELDS:
            got = result.fields[spec.name].value
            want = sample["fields"][spec.name]
            ok = correct(spec, got, want)
            per_field[spec.name][0] += ok
            per_field[spec.name][1] += 1
            if want is None:
                nulls[1] += 1
                nulls[0] += got is None
            if got is not None:
                values_given += 1
                ungrounded += not result.fields[spec.name].grounded
            if not ok:
                wrong.append(spec.name)
                failures.append(f"| {sample['id']} | {spec.name} | {want!r} | {got!r} |")

        rule_flags = {f.code for f in result.flags if f.source == "rule"}
        flags_ok = rule_flags == set(sample["expected_flags"])
        flag_hits += flags_ok
        for name in sample.get("expected_low_confidence", []):
            low_conf_hits[1] += 1
            low_conf_hits[0] += result.fields[name].confidence < 0.75

        sample_cost = sum(c.usage.cost_usd for c in result.calls)
        sample_ms = sum(c.usage.latency_ms for c in result.calls)
        cost += sample_cost
        latency += sample_ms
        rows.append(f"| {sample['id']} | {sample['scenario']} | {16 - len(wrong)}/16 | "
                    f"{'yes' if flags_ok else 'NO'} | {result.overall_confidence:.2f} | "
                    f"{'yes' if result.needs_review else 'no'} | ${sample_cost:.4f} |")

    n = len(truth)
    total_correct = sum(c for c, _ in per_field.values())
    total = sum(t for _, t in per_field.values())
    model = "mock (perfect reader — checks the pipeline, not a model)" if provider.name == "mock" \
        else f"{provider.model}, effort {settings.llm_effort}"

    lines = [
        "# Evaluation results",
        "",
        f"Model: **{model}**  ",
        f"Samples: {n} synthetic applications, assessment date {settings.assessment_date}",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Field-level accuracy | {total_correct}/{total} ({total_correct / total:.0%}) |",
        f"| Missing fields correctly left empty | {nulls[0]}/{nulls[1]} |",
        f"| Values without a verifiable quote | {ungrounded}/{values_given} |",
        f"| Samples raising exactly the expected policy flags | {flag_hits}/{n} |",
        f"| Conflicting figures flagged as low confidence | {low_conf_hits[0]}/{low_conf_hits[1]} |",
        f"| Average LLM time per application | {latency / n / 1000:.1f}s |",
        f"| Average LLM cost per application | ${cost / n:.4f} |",
        "",
        "## Per sample",
        "",
        "| Sample | Scenario | Fields correct | Flags as expected | Confidence | Needs review | Cost |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## Per field",
        "",
        "| Field | Correct |",
        "|---|---|",
        *[f"| {name} | {c}/{t} |" for name, (c, t) in per_field.items()],
        "",
        "## Wrong values",
        "",
        *(["| Sample | Field | Expected | Got |", "|---|---|---|---|", *failures]
          if failures else ["None."]),
    ]
    report = "\n".join(lines) + "\n"
    print(report)
    if args.write:
        RESULTS_MD.write_text(report)
        print(f"Written to {RESULTS_MD}")


if __name__ == "__main__":
    main()
