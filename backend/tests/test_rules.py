"""Every policy rule, including the boundaries where off-by-one mistakes hide."""

from datetime import date

import pytest

from app.pipeline.rules import abn_is_valid, add_months, evaluate, lvr_limit

ASSESSED = date(2026, 11, 1)

CLEAN = {
    "borrower_name": "Test Pty Ltd", "borrower_type": "company", "abn": "88707297339",
    "loan_amount": 5_500_000, "loan_purpose": "purchase", "loan_term_months": 24,
    "property_address": "1 Test St", "property_type": "office", "property_value": 10_000_000,
    "valuation_date": "2026-09-01", "stated_lvr": 55.0, "presales_pct": None,
}


def codes(**changes):
    return {f.code for f in evaluate({**CLEAN, **changes}, ASSESSED).flags}


def test_clean_application_raises_nothing():
    assert codes() == set()


def test_lvr_is_calculated_by_code():
    assert evaluate(CLEAN, ASSESSED).calculated_lvr == 55.0


# §4.2 / §4.3 LVR limits ------------------------------------------------------

@pytest.mark.parametrize("loan, flagged", [(6_500_000, False), (6_500_001, True)])
def test_income_producing_limit_65(loan, flagged):
    assert ("LVR_OVER_LIMIT" in codes(loan_amount=loan, stated_lvr=None)) is flagged


def test_construction_limit_60():
    assert "LVR_OVER_LIMIT" in codes(loan_purpose="construction", loan_amount=6_100_000, stated_lvr=None)
    assert "LVR_OVER_LIMIT" not in codes(loan_purpose="construction", loan_amount=6_000_000, stated_lvr=None)


def test_land_limit_50():
    assert "LVR_OVER_LIMIT" in codes(property_type="land", loan_amount=5_200_000, stated_lvr=None)


def test_lowest_limit_applies():
    assert lvr_limit("land", "construction")[0] == 50.0
    assert lvr_limit("residential_dev", "purchase")[0] == 60.0
    assert lvr_limit("industrial", "refinance")[0] == 65.0


# §4.4 stated vs calculated LVR --------------------------------------------------

@pytest.mark.parametrize("stated, flagged", [(57.0, False), (57.1, True), (52.9, True)])
def test_lvr_mismatch_tolerance(stated, flagged):
    assert ("LVR_MISMATCH" in codes(stated_lvr=stated)) is flagged


# §3.1 / §3.2 loan size and term ------------------------------------------------

@pytest.mark.parametrize("loan, flagged", [
    (500_000, False), (499_999, True), (50_000_000, False), (50_000_001, True)])
def test_loan_size_range(loan, flagged):
    result = codes(loan_amount=loan, property_value=200_000_000, stated_lvr=None)
    assert ("AMOUNT_OUT_OF_RANGE" in result) is flagged


@pytest.mark.parametrize("term, flagged", [(36, False), (37, True)])
def test_term_limit(term, flagged):
    assert ("TERM_TOO_LONG" in codes(loan_term_months=term)) is flagged


# §5.1 / §5.2 valuation ---------------------------------------------------------

def test_missing_valuation_is_critical_and_missing_required():
    result = evaluate({**CLEAN, "property_value": None}, ASSESSED)
    by_code = {f.code: f for f in result.flags}
    assert by_code["VALUATION_MISSING"].severity == "critical"
    assert "MISSING_REQUIRED" in by_code
    assert result.calculated_lvr is None


@pytest.mark.parametrize("valued, flagged", [
    ("2026-05-01", False),  # exactly 6 months: allowed
    ("2026-04-30", True),   # one day more
])
def test_valuation_age_boundary(valued, flagged):
    assert ("VALUATION_STALE" in codes(valuation_date=valued)) is flagged


def test_add_months_clamps_short_months():
    assert add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)


# §6.1 presales -----------------------------------------------------------------

def test_presales_only_checked_for_development():
    assert "PRESALES_LOW" in codes(loan_purpose="construction", presales_pct=49, stated_lvr=None,
                                   loan_amount=5_000_000)
    assert "PRESALES_LOW" not in codes(loan_purpose="construction", presales_pct=50, stated_lvr=None,
                                       loan_amount=5_000_000)
    assert "PRESALES_LOW" not in codes(presales_pct=10)  # office purchase: not applicable


# §2.2 ABN ----------------------------------------------------------------------

def test_abn_checksum():
    assert abn_is_valid("88 707 297 339")
    assert not abn_is_valid("20838632364")  # two digits transposed
    assert not abn_is_valid("1234")
    assert "ABN_INVALID" in codes(abn="20838632364")
    assert "ABN_INVALID" not in codes(abn=None)  # optional: absent is fine


# §8.1 required -----------------------------------------------------------------

def test_missing_required_lists_fields():
    flag = next(f for f in evaluate({**CLEAN, "loan_term_months": None}, ASSESSED).flags
                if f.code == "MISSING_REQUIRED")
    assert "loan_term_months" in flag.message
