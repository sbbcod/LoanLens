"""End to end on all ten samples, with the mock provider: every expected flag fires, nothing else."""

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.llm.mock_provider import MockProvider
from app.pipeline.analyse import analyse
from app.pipeline.redact import redact

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
TRUTH = json.loads((SAMPLES / "ground_truth.json").read_text())["samples"]


@pytest.mark.parametrize("sample", TRUTH, ids=[s["id"] for s in TRUTH])
def test_sample_raises_exactly_the_expected_rule_flags(sample):
    result = analyse(SAMPLES / f"{sample['id']}.pdf", MockProvider(), get_settings())
    rule_flags = {f.code for f in result.flags if f.source == "rule"}
    assert rule_flags == set(sample["expected_flags"])
    assert result.calculated_lvr == sample["calculated_lvr"]


@pytest.mark.parametrize("sample", TRUTH, ids=[s["id"] for s in TRUTH])
def test_every_mock_value_is_grounded(sample):
    result = analyse(SAMPLES / f"{sample['id']}.pdf", MockProvider(), get_settings())
    ungrounded = [f.name for f in result.fields.values() if not f.grounded]
    assert ungrounded == []


def test_critical_flag_forces_review():
    s08 = analyse(SAMPLES / "S08.pdf", MockProvider(), get_settings())  # land LVR 52%
    assert s08.needs_review


def test_logs_are_redacted():
    line = "Sent by mel.h@harbourline.example, ABN 20 838 632 364, ph 0412 345 678"
    assert redact(line) == "Sent by [email], ABN [abn], ph [phone]"
