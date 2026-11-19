"""The fields LoanLens reads from every application.

One list, used everywhere: to build the schema the LLM must fill, to check
required fields, to compare against the ground truth, and to label the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["text", "money", "integer", "percent", "date", "enum"]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: Kind
    required: bool
    description: str
    options: tuple[str, ...] = ()


BORROWER_TYPES = ("company", "trust", "individual", "smsf")
LOAN_PURPOSES = ("purchase", "refinance", "construction", "equity_release", "bridging")
PROPERTY_TYPES = ("office", "retail", "industrial", "residential_dev", "land", "mixed_use")

FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("borrower_name", "Borrower", "text", True,
              "Legal name of the borrowing entity, exactly as written."),
    FieldSpec("borrower_type", "Borrower type", "enum", True,
              "What kind of entity the borrower is. A trustee of a super fund is smsf.",
              BORROWER_TYPES),
    FieldSpec("abn", "ABN", "text", False,
              "Australian Business Number as 11 digits with spaces removed. Copy it exactly "
              "as written, even if it looks wrong."),
    FieldSpec("broker_name", "Broker", "text", False,
              "Firm that introduced the application."),
    FieldSpec("loan_amount", "Loan amount", "money", True,
              "Amount of the new loan requested, in AUD. Not the purchase price or existing debt."),
    FieldSpec("loan_purpose", "Purpose", "enum", True,
              "Why the loan is needed. Buying a property is purchase.", LOAN_PURPOSES),
    FieldSpec("loan_term_months", "Term (months)", "integer", True,
              "Loan term in months."),
    FieldSpec("property_address", "Property address", "text", True,
              "Full address of the security property."),
    FieldSpec("property_type", "Property type", "enum", True,
              "Type of security property. A warehouse is industrial; a site for new "
              "dwellings is residential_dev; vacant land is land.", PROPERTY_TYPES),
    FieldSpec("property_value", "Property value", "money", True,
              "Market value from a valuation, in AUD. A purchase price is NOT a valuation: "
              "return null if no valuation figure is given."),
    FieldSpec("valuation_date", "Valuation date", "date", False,
              "Date of the valuation report, as YYYY-MM-DD."),
    FieldSpec("valuer", "Valuer", "text", False,
              "Firm that prepared the valuation."),
    FieldSpec("stated_lvr", "Stated LVR (%)", "percent", False,
              "Loan-to-value ratio as written in the document, as a percentage number "
              "(55.0 for 55%). Only if the document states one; never calculate it."),
    FieldSpec("existing_debt", "Existing debt", "money", False,
              "Debt currently secured on the property that the loan will repay, in AUD."),
    FieldSpec("exit_strategy", "Exit strategy", "text", False,
              "How the loan will be repaid at the end of the term, in a short phrase."),
    FieldSpec("presales_pct", "Presales (%)", "percent", False,
              "For development loans, qualifying presales as a percentage number."),
)

FIELDS_BY_NAME = {f.name: f for f in FIELDS}
REQUIRED_FIELDS = tuple(f.name for f in FIELDS if f.required)
