# Evaluation results

Model: **claude-opus-5-5, effort medium**  
Samples: 10 synthetic applications, assessment date 2026-11-01

| Measure | Result |
|---|---|
| Field-level accuracy | 159/160 (99%) |
| Missing fields correctly left empty | 22/23 |
| Values without a verifiable quote | 1/138 |
| Samples raising exactly the expected policy flags | 10/10 |
| Conflicting figures flagged as low confidence | 1/1 |
| Average LLM time per application | 21.0s |
| Average LLM cost per application | $0.0611 |

## Per sample

| Sample | Scenario | Fields correct | Flags as expected | Confidence | Needs review | Cost |
|---|---|---|---|---|---|---|
| S01 | Clean office acquisition, LVR 55% | 16/16 | yes | 0.80 | no | $0.0566 |
| S02 | Industrial warehouse refinance, LVR 70% | 16/16 | yes | 0.90 | yes | $0.0699 |
| S03 | Residential development construction loan, presales 35% | 16/16 | yes | 0.90 | no | $0.0584 |
| S04 | Valuation missing | 16/16 | yes | 0.85 | yes | $0.0610 |
| S05 | Valuation nine months old | 16/16 | yes | 0.90 | no | $0.0574 |
| S06 | Loan amount differs between body text and summary table | 15/16 | yes | 0.40 | yes | $0.0695 |
| S07 | Chatty broker email saved as PDF | 16/16 | yes | 0.70 | yes | $0.0647 |
| S08 | Land loan, LVR 52% | 16/16 | yes | 0.75 | yes | $0.0525 |
| S09 | SMSF borrower buying a retail shop | 16/16 | yes | 0.80 | no | $0.0655 |
| S10 | Stated LVR does not match calculated LVR | 16/16 | yes | 0.90 | no | $0.0559 |

## Per field

| Field | Correct |
|---|---|
| borrower_name | 10/10 |
| borrower_type | 10/10 |
| abn | 10/10 |
| broker_name | 10/10 |
| loan_amount | 10/10 |
| loan_purpose | 10/10 |
| loan_term_months | 10/10 |
| property_address | 10/10 |
| property_type | 10/10 |
| property_value | 10/10 |
| valuation_date | 10/10 |
| valuer | 10/10 |
| stated_lvr | 10/10 |
| existing_debt | 9/10 |
| exit_strategy | 10/10 |
| presales_pct | 10/10 |

## Wrong values

| Sample | Field | Expected | Got |
|---|---|---|---|
| S06 | existing_debt | None | 0.0 |
