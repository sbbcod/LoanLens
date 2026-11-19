"""Step 4: credit policy rules, in plain Python.

Every number here mirrors a [System check] clause in data/credit_policy.md.
Change both together. The LLM is never asked to make these decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.pipeline.fields import REQUIRED_FIELDS

# --- Policy numbers (credit_policy.md) --------------------------------------

LVR_LIMIT_INCOME_PRODUCING = 65.0  # §4.2 office, retail, industrial, mixed use
LVR_LIMIT_CONSTRUCTION = 60.0      # §4.2 construction purpose or residential development
LVR_LIMIT_LAND = 50.0              # §4.2 vacant land
LVR_MISMATCH_TOLERANCE = 2.0       # §4.4 percentage points
MIN_LOAN = 500_000                 # §3.1
MAX_LOAN = 50_000_000              # §3.1
MAX_TERM_MONTHS = 36               # §3.2
MAX_VALUATION_AGE_MONTHS = 6       # §5.2
MIN_PRESALES_PCT = 50.0            # §6.1

ABN_WEIGHTS = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)


@dataclass(frozen=True)
class Flag:
    code: str
    severity: str  # info | warning | critical
    message: str
    policy_ref: str | None
    source: str = "rule"


@dataclass(frozen=True)
class RuleResult:
    calculated_lvr: float | None
    flags: list[Flag]


# --- Helpers ---------------------------------------------------------------


def calculate_lvr(loan_amount: float | None, property_value: float | None) -> float | None:
    """Loan ÷ value as a percentage. None when either figure is missing."""
    if not loan_amount or not property_value:
        return None
    return loan_amount / property_value * 100


def lvr_limit(property_type: str | None, loan_purpose: str | None) -> tuple[float, str]:
    """The maximum LVR for this security, and why. The lowest limit that applies wins (§4.3)."""
    candidates = [(LVR_LIMIT_INCOME_PRODUCING, "income-producing property")]
    if loan_purpose == "construction" or property_type == "residential_dev":
        candidates.append((LVR_LIMIT_CONSTRUCTION, "construction or development"))
    if property_type == "land":
        candidates.append((LVR_LIMIT_LAND, "vacant land"))
    return min(candidates)


def abn_is_valid(abn: str) -> bool:
    """ATO check-digit test: subtract 1 from the first digit, weight, sum, divisible by 89."""
    digits = abn.replace(" ", "")
    if len(digits) != 11 or not digits.isdigit():
        return False
    values = [int(d) for d in digits]
    values[0] -= 1
    return sum(v * w for v, w in zip(values, ABN_WEIGHTS)) % 89 == 0


def add_months(d: date, months: int) -> date:
    year, month = divmod(d.month - 1 + months, 12)
    year += d.year
    month += 1
    # Clamp the day for short months (31 Aug + 6 months -> 28/29 Feb).
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(f"cannot add {months} months to {d}")


def _money(v: float) -> str:
    return f"${v:,.0f}"


# --- The rules -------------------------------------------------------------


def evaluate(values: dict[str, Any], assessment_date: date) -> RuleResult:
    """Run every policy rule against the field values (the human-corrected ones, when present)."""
    flags: list[Flag] = []
    loan = values.get("loan_amount")
    value = values.get("property_value")
    term = values.get("loan_term_months")
    ptype = values.get("property_type")
    purpose = values.get("loan_purpose")

    # §8.1 required information
    missing = [name for name in REQUIRED_FIELDS if values.get(name) in (None, "")]
    if missing:
        flags.append(Flag("MISSING_REQUIRED", "warning",
                          f"Required information missing: {', '.join(missing)}.", "§8.1"))

    # §5.1 valuation present
    if not value:
        flags.append(Flag("VALUATION_MISSING", "critical",
                          "No valuation figure was found. The application cannot proceed "
                          "without one.", "§5.1"))

    # §4.2–4.3 LVR limit
    lvr = calculate_lvr(loan, value)
    if lvr is not None:
        limit, reason = lvr_limit(ptype, purpose)
        if lvr > limit:
            flags.append(Flag("LVR_OVER_LIMIT", "critical",
                              f"LVR is {lvr:.1f}%, above the {limit:.0f}% limit for {reason}.",
                              "§4.2"))

        # §4.4 stated vs calculated
        stated = values.get("stated_lvr")
        if stated is not None and abs(stated - lvr) > LVR_MISMATCH_TOLERANCE:
            flags.append(Flag("LVR_MISMATCH", "warning",
                              f"Document states LVR {stated:.1f}%, but loan ÷ valuation is "
                              f"{lvr:.1f}%.", "§4.4"))

    # §3.1 loan size
    if loan and not MIN_LOAN <= loan <= MAX_LOAN:
        flags.append(Flag("AMOUNT_OUT_OF_RANGE", "warning",
                          f"Loan amount {_money(loan)} is outside the "
                          f"{_money(MIN_LOAN)}–{_money(MAX_LOAN)} range.", "§3.1"))

    # §3.2 term
    if term and term > MAX_TERM_MONTHS:
        flags.append(Flag("TERM_TOO_LONG", "warning",
                          f"Term of {term} months is longer than the "
                          f"{MAX_TERM_MONTHS}-month maximum.", "§3.2"))

    # §5.2 valuation age
    val_date = values.get("valuation_date")
    if isinstance(val_date, str):
        val_date = date.fromisoformat(val_date)
    if val_date and add_months(val_date, MAX_VALUATION_AGE_MONTHS) < assessment_date:
        flags.append(Flag("VALUATION_STALE", "warning",
                          f"Valuation dated {val_date:%d %b %Y} is more than "
                          f"{MAX_VALUATION_AGE_MONTHS} months old.", "§5.2"))

    # §6.1 presales, development loans only
    presales = values.get("presales_pct")
    is_development = purpose == "construction" or ptype == "residential_dev"
    if is_development and presales is not None and presales < MIN_PRESALES_PCT:
        flags.append(Flag("PRESALES_LOW", "warning",
                          f"Presales of {presales:.0f}% are below the "
                          f"{MIN_PRESALES_PCT:.0f}% minimum for development loans.", "§6.1"))

    # §2.2 ABN check digit
    abn = values.get("abn")
    if abn and not abn_is_valid(abn):
        flags.append(Flag("ABN_INVALID", "warning",
                          f"ABN {abn} fails the check-digit test. It may be mistyped.", "§2.2"))

    return RuleResult(calculated_lvr=round(lvr, 2) if lvr is not None else None, flags=flags)
