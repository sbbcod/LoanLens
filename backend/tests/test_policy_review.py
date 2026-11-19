from app.llm.base import ReviewRisk
from app.pipeline.policy_review import accept, clauses, policy_text


def test_policy_clauses_are_parsed():
    known = clauses(policy_text())
    assert known["§4.2"] is True    # system check
    assert known["§7.2"] is False   # judgement
    assert "§9.9" not in known


def test_only_real_judgement_clauses_are_kept_and_never_critical():
    risks = [
        ReviewRisk("§7.2", "Exit depends on rezoning", "Not yet approved.", "warning"),
        ReviewRisk("7.2", "Same clause without the symbol", "x", "info"),
        ReviewRisk("§4.2", "LVR too high", "Rules already cover this.", "warning"),
        ReviewRisk("§12.1", "Invented clause", "x", "warning"),
        ReviewRisk("§2.4", "SMSF", "x", "critical"),
    ]
    accepted, rejected = accept(risks, policy_text())
    assert [f.policy_ref for f in accepted] == ["§7.2", "§7.2", "§2.4"]
    assert {r.policy_ref for r in rejected} == {"§4.2", "§12.1"}
    assert all(f.severity in ("info", "warning") and f.source == "llm" for f in accepted)
