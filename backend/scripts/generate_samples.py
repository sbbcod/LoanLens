"""Generate the ten fictional sample loan applications as PDFs.

The PDFs are printed from data/samples/ground_truth.json, so the answer key
is correct by construction. Four layouts are used so the extraction is tested
on more than one kind of document:

    form      - broker application form, mostly tables, two pages
    letter    - broker cover letter, figures written in sentences
    email     - informal broker email saved as PDF
    conflict  - letter + summary table that disagree on the loan amount

Run from the backend folder:

    .venv/bin/python scripts/generate_samples.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Same input always gives byte-identical PDFs (no timestamps or random IDs),
# so regenerating the samples doesn't show up as a change in git.
rl_config.invariant = 1

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
GROUND_TRUTH = SAMPLES_DIR / "ground_truth.json"

# Lodgement details that belong to the document, not to the extracted fields.
LODGEMENT: dict[str, dict[str, str]] = {
    "S01": {"ref": "HFP-2026-0411", "date": "2026-10-06", "contact": "Daniel Okafor"},
    "S02": {"ref": "HFP-2026-0418", "date": "2026-10-08", "contact": "Priya Raman"},
    "S03": {"ref": "HFP-2026-0423", "date": "2026-10-12", "contact": "Daniel Okafor"},
    "S04": {"ref": "HFP-2026-0430", "date": "2026-10-14", "contact": "Priya Raman"},
    "S05": {"ref": "HFP-2026-0436", "date": "2026-10-19", "contact": "Daniel Okafor"},
    "S06": {"ref": "HFP-2026-0441", "date": "2026-10-21", "contact": "Priya Raman"},
    "S07": {"ref": "HFP-2026-0447", "date": "2026-10-23", "contact": "Mel Hartigan"},
    "S08": {"ref": "HFP-2026-0452", "date": "2026-10-26", "contact": "Daniel Okafor"},
    "S09": {"ref": "HFP-2026-0458", "date": "2026-10-28", "contact": "Priya Raman"},
    "S10": {"ref": "HFP-2026-0463", "date": "2026-10-30", "contact": "Daniel Okafor"},
}

BORROWER_TYPE_LABEL = {
    "company": "Company",
    "trust": "Trust",
    "individual": "Individual",
    "smsf": "Self-managed superannuation fund",
}
PURPOSE_LABEL = {
    "purchase": "Acquisition",
    "refinance": "Refinance",
    "construction": "Construction",
    "equity_release": "Equity release",
    "bridging": "Bridging",
}
PROPERTY_TYPE_LABEL = {
    "office": "Office",
    "retail": "Retail",
    "industrial": "Industrial / warehouse",
    "residential_dev": "Residential development site",
    "land": "Vacant land",
    "mixed_use": "Mixed use (retail and residential)",
}

NAVY = colors.HexColor("#1F3A5F")
GREY = colors.HexColor("#5B6573")
RULE = colors.HexColor("#C9D1DC")
SHADE = colors.HexColor("#EEF2F7")


# ---------------------------------------------------------------- formatting


def money(amount: float) -> str:
    """4950000 -> '$4,950,000'"""
    return f"${amount:,.0f}"


def long_date(iso: str) -> str:
    """'2026-08-14' -> '14 August 2026'"""
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%B %Y}"


def abn_text(abn: str) -> str:
    """'88707297339' -> '88 707 297 339' (how ABNs are usually printed)"""
    return f"{abn[:2]} {abn[2:5]} {abn[5:8]} {abn[8:]}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def a_or_an(word: str) -> str:
    """'industrial' -> 'an industrial', 'retail' -> 'a retail'"""
    return f"{'an' if word[0].lower() in 'aeiou' else 'a'} {word}"


# ------------------------------------------------------------------- styles

_base = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=_base["BodyText"], fontName="Helvetica",
                      fontSize=10, leading=14, spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, leading=11, textColor=GREY)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=15,
                    leading=19, textColor=NAVY, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=11,
                    leading=14, textColor=NAVY, spaceBefore=10, spaceAfter=4)
RIGHT = ParagraphStyle("right", parent=SMALL, alignment=TA_RIGHT)
MONO = ParagraphStyle("mono", parent=BODY, fontName="Courier", fontSize=9.5, leading=13)
CELL = ParagraphStyle("cell", parent=BODY, spaceAfter=0)
CELL_LABEL = ParagraphStyle("cell_label", parent=CELL, fontName="Helvetica-Bold", textColor=GREY)


class Rule(Flowable):
    """A thin horizontal line across the page."""

    def __init__(self, width: float, colour: colors.Color = RULE, thickness: float = 0.8):
        super().__init__()
        self.width, self.colour, self.thickness = width, colour, thickness

    def wrap(self, *_: Any) -> tuple[float, float]:
        return self.width, self.thickness + 4

    def draw(self) -> None:
        self.canv.setStrokeColor(self.colour)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.width, 2)


def field_table(rows: list[tuple[str, str]], width: float) -> Table:
    """Two-column label/value table used by the form layouts."""
    data = [[Paragraph(label, CELL_LABEL), Paragraph(value, CELL)] for label, value in rows]
    table = Table(data, colWidths=[width * 0.36, width * 0.64])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), SHADE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("BOX", (0, 0), (-1, -1), 0.8, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def letterhead(broker: str, lodge: dict[str, str], width: float) -> list[Flowable]:
    return [
        Paragraph(broker, H1),
        Paragraph("Commercial Finance Brokers &middot; Level 9, 200 Kent Row, Sydney NSW 2000", SMALL),
        Spacer(1, 3 * mm),
        Rule(width, NAVY, 1.4),
        Paragraph(f"Our reference: {lodge['ref']} &nbsp;&nbsp;|&nbsp;&nbsp; {long_date(lodge['date'])}", RIGHT),
        Spacer(1, 4 * mm),
    ]


def footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(doc.leftMargin, 12 * mm,
                      "Fictional sample document generated for the LoanLens demo.")
    canvas.drawRightString(A4[0] - doc.rightMargin, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ------------------------------------------------------------------ layouts


def build_form(s: dict[str, Any], broker: str, lodge: dict[str, str], width: float) -> list[Flowable]:
    """Application form: tables, with security and valuation on page 2."""
    f = s["fields"]
    story = letterhead(broker, lodge, width)
    story.append(Paragraph("Commercial Loan Application", H1))
    story.append(Paragraph(f"Submitted by {lodge['contact']}, {broker}", SMALL))

    borrower_rows = [
        ("Borrower", f["borrower_name"]),
        ("Borrower type", BORROWER_TYPE_LABEL[f["borrower_type"]]),
    ]
    if f["abn"]:
        borrower_rows.append(("ABN", abn_text(f["abn"])))
    borrower_rows.append(("Introducing broker", f["broker_name"]))
    story += [Paragraph("1. Borrower", H2), field_table(borrower_rows, width)]

    loan_rows = [
        ("Loan amount", money(f["loan_amount"])),
        ("Loan purpose", PURPOSE_LABEL[f["loan_purpose"]]),
        ("Term", f"{f['loan_term_months']} months"),
    ]
    if f["existing_debt"] is not None:
        loan_rows.append(("Existing debt to be repaid", money(f["existing_debt"])))
    story += [Paragraph("2. Loan request", H2), field_table(loan_rows, width)]

    story.append(PageBreak())

    security_rows = [
        ("Property address", f["property_address"]),
        ("Property type", PROPERTY_TYPE_LABEL[f["property_type"]]),
    ]
    if f["presales_pct"] is not None:
        security_rows.append(("Qualifying presales", f"{f['presales_pct']:.0f}% of total units"))
    story += [Paragraph("3. Security", H2), field_table(security_rows, width)]

    valuation_rows = []
    if f["property_value"] is not None:
        valuation_rows.append(("Market value", money(f["property_value"])))
    if f["valuation_date"]:
        valuation_rows.append(("Date of valuation", long_date(f["valuation_date"])))
    if f["valuer"]:
        valuation_rows.append(("Valuer", f["valuer"]))
    if f["stated_lvr"] is not None:
        valuation_rows.append(("Loan-to-value ratio", pct(f["stated_lvr"])))
    story += [Paragraph("4. Valuation", H2), field_table(valuation_rows, width)]

    story += [
        Paragraph("5. Exit strategy", H2),
        Paragraph(f"{f['exit_strategy']}.", BODY),
        Paragraph("6. Broker declaration", H2),
        Paragraph("The information in this application has been provided by the borrower. "
                  "We are not aware of anything that would make it misleading.", BODY),
    ]
    return story


def build_letter(s: dict[str, Any], broker: str, lodge: dict[str, str], width: float) -> list[Flowable]:
    """Cover letter: every figure is inside a sentence."""
    f = s["fields"]
    doc_extra = s.get("document", {})
    purpose = PURPOSE_LABEL[f["loan_purpose"]].lower()
    ptype = PROPERTY_TYPE_LABEL[f["property_type"]].lower()
    abn = f" (ABN {abn_text(f['abn'])})" if f["abn"] else ""

    paras = [
        "Dear Credit Team,",
        f"<b>Re: {PURPOSE_LABEL[f['loan_purpose']]} facility for {f['borrower_name']}</b>",
        f"We are pleased to introduce {f['borrower_name']}{abn}, "
        f"{a_or_an(BORROWER_TYPE_LABEL[f['borrower_type']].lower())} client of ours, who is seeking a "
        f"first-mortgage {purpose} facility of {money(f['loan_amount'])} over a term of "
        f"{f['loan_term_months']} months.",
        f"The security is {a_or_an(ptype)} property at {f['property_address']}.",
    ]

    if f["existing_debt"] is not None:
        paras.append(f"The new facility will repay the existing loan of {money(f['existing_debt'])} "
                     "with the incumbent lender, with the balance applied to costs.")

    if f["property_value"] is not None:
        sentence = (f"{f['valuer']} has valued the property at {money(f['property_value'])} "
                    f"in a report dated {long_date(f['valuation_date'])}")
        if f["stated_lvr"] is not None:
            sentence += f", which gives a loan-to-value ratio of {pct(f['stated_lvr'])}"
        paras.append(sentence + ".")
    else:
        paras.append(f"The contract purchase price is {money(doc_extra['purchase_price'])}. "
                     "A formal valuation has been ordered and will follow under separate cover.")

    if f["borrower_type"] == "smsf":
        paras.append("The fund will hold the property through a bare trust under a limited recourse "
                     "borrowing arrangement. The members have received advice from their accountant.")

    paras += [
        f"The intended exit is: {f['exit_strategy'].lower()}.",
        "We would appreciate an indicative response at your earliest convenience. "
        "Please let me know if you need anything further.",
        "Kind regards,",
        f"{lodge['contact']}<br/>Senior Broker, {broker}",
    ]
    return letterhead(broker, lodge, width) + [Paragraph(p, BODY) for p in paras]


def build_email(s: dict[str, Any], broker: str, lodge: dict[str, str], width: float) -> list[Flowable]:
    """Informal email printed to PDF. Round, casual figures."""
    f = s["fields"]
    header = [
        f"From:    {lodge['contact']} &lt;mel.h@harbourline.example&gt;",
        "To:      loans@lender.example",
        f"Sent:    {date.fromisoformat(lodge['date']):%A} {long_date(lodge['date'])} 4:52 PM",
        f"Subject: Loan Application - {f['borrower_name']} - quick one",
    ]
    body = [
        "Hi team,",
        "Hope you're well! Got a good one for you before the weekend.",
        f"Client is {f['borrower_name']} (ABN {abn_text(f['abn'])}), they're buying a warehouse at "
        f"{f['property_address']}. Looking for $2.35m over {f['loan_term_months']} months, "
        "interest only.",
        f"{f['valuer']} valued it at about 3.9 mil, report dated "
        f"{long_date(f['valuation_date'])} - copy attached. Good tenant demand in the area.",
        f"Plan is to {f['exit_strategy'][0].lower() + f['exit_strategy'][1:]}.",
        "Directors have done a couple of these before so should be straightforward. "
        "Shout if you need anything else!",
        "Cheers,",
        f"Mel<br/>{broker}",
        "<i>Sent from my iPhone</i>",
    ]
    story: list[Flowable] = [Paragraph(line, MONO) for line in header]
    story += [Spacer(1, 2 * mm), Rule(width), Spacer(1, 3 * mm)]
    story += [Paragraph(p, BODY) for p in body]
    return story


def build_conflict(s: dict[str, Any], broker: str, lodge: dict[str, str], width: float) -> list[Flowable]:
    """Letter whose wording and summary table give different loan amounts."""
    f = s["fields"]
    body_amount = s["document"]["body_loan_amount_text"]
    story = letterhead(broker, lodge, width)
    story += [
        Paragraph("Dear Credit Team,", BODY),
        Paragraph(f"<b>Re: Equity release - {f['borrower_name']}</b>", BODY),
        Paragraph(f"Our client {f['borrower_name']} owns "
                  f"{a_or_an(PROPERTY_TYPE_LABEL[f['property_type']].lower())} property at {f['property_address']} and is seeking {body_amount} to release "
                  "equity for its other business interests.", BODY),
        Paragraph("The property is unencumbered. A summary of the proposal is set out below.", BODY),
        Paragraph("Proposal summary", H2),
        field_table([
            ("Borrower", f["borrower_name"]),
            ("ABN", abn_text(f["abn"])),
            ("Facility amount", money(f["loan_amount"])),
            ("Purpose", PURPOSE_LABEL[f["loan_purpose"]]),
            ("Term", f"{f['loan_term_months']} months"),
            ("Security", f["property_address"]),
            ("Valuation", f"{money(f['property_value'])} ({f['valuer']}, {long_date(f['valuation_date'])})"),
            ("Exit", f["exit_strategy"]),
        ], width),
        Spacer(1, 4 * mm),
        Paragraph("Kind regards,", BODY),
        Paragraph(f"{lodge['contact']}<br/>Senior Broker, {broker}", BODY),
    ]
    return story


LAYOUTS = {
    "form": build_form,
    "letter": build_letter,
    "email": build_email,
    "conflict": build_conflict,
}


# --------------------------------------------------------------------- main


def generate(sample: dict[str, Any], broker: str, out_dir: Path) -> Path:
    path = out_dir / f"{sample['id']}.pdf"
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=22 * mm,
        title=f"Loan application {sample['id']}", author=broker,
    )
    story = LAYOUTS[sample["layout"]](sample, broker, LODGEMENT[sample["id"]], doc.width)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path


def main() -> None:
    truth = json.loads(GROUND_TRUTH.read_text())
    broker = truth["broker_on_letterhead"]
    for sample in truth["samples"]:
        path = generate(sample, broker, SAMPLES_DIR)
        print(f"{sample['id']}  {sample['layout']:<8}  {path.name}")


if __name__ == "__main__":
    main()
