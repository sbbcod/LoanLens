from app.pipeline.fields import FIELDS_BY_NAME
from app.pipeline.grounding import check, numbers_in
from app.pipeline.pdf_text import Page

PAGES = [
    Page(1, "Loan amount $4,950,000\nTerm 24 months"),
    Page(2, "Fenwick Property Advisory valued it at about 3.9 mil, report dated\n21 August 2026"),
]
LOAN = FIELDS_BY_NAME["loan_amount"]
VALUE = FIELDS_BY_NAME["property_value"]
VALUER = FIELDS_BY_NAME["valuer"]


def test_quote_found_and_value_matches():
    result = check(LOAN, 4_950_000, "Loan amount $4,950,000", 1, PAGES)
    assert result.grounded and result.page == 1


def test_informal_amount_is_understood():
    assert numbers_in("$2.35m") == [2_350_000]
    assert check(VALUE, 3_900_000, "valued it at about 3.9 mil", 2, PAGES).grounded


def test_quote_across_a_line_break_still_matches():
    assert check(VALUER, "Fenwick", "about 3.9 mil, report dated 21 August 2026", 2, PAGES).grounded


def test_wrong_page_is_corrected():
    result = check(LOAN, 4_950_000, "Loan amount $4,950,000", 2, PAGES)
    assert result.grounded and result.page == 1


def test_invented_quote_fails():
    result = check(LOAN, 4_950_000, "The facility limit is $4,950,000", 1, PAGES)
    assert not result.grounded


def test_real_quote_with_wrong_number_fails():
    result = check(LOAN, 5_000_000, "Loan amount $4,950,000", 1, PAGES)
    assert not result.grounded
    assert "does not contain" in result.reason


def test_value_without_quote_fails():
    assert not check(LOAN, 4_950_000, None, None, PAGES).grounded


def test_null_value_needs_no_quote():
    assert check(LOAN, None, None, None, PAGES).grounded
