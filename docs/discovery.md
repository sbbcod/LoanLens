# Discovery: loan application intake

This page records the problem LoanLens is built to solve, who it is for, and how success would be measured. The lender is fictional. The process below is an assumed one, typical of a non-bank commercial property lender; in a real engagement it would be confirmed by sitting with the analysts before anything was built.

## Users

| Who | What they do today | What they need |
|---|---|---|
| **Credit analyst** | Receives broker emails, re-keys figures from the PDF, checks them against policy, writes a summary for the credit manager | To stop typing and start assessing; to trust that nothing was misread |
| **Credit manager** | Reads the analyst's summary and approves or declines | A short, reliable summary with the risks stated up front, wherever they are |
| **Broker** (external) | Sends applications in whatever format they have | Nothing changes for them |

## Current process

1. Broker emails an application PDF to a shared mailbox.
2. An analyst opens it and types borrower, loan and security details into the loan system.
3. The analyst works out the LVR and checks loan size, term, valuation age and presales against the credit policy.
4. The analyst writes up the application and emails it to a credit manager.
5. The manager replies with a decision; the analyst updates the system.

## Pain points

- Re-keying is slow and adds nothing.
- Every broker uses a different layout, so figures are easy to misread.
- Policy checks depend on the analyst remembering the limits for each loan type.
- Approval happens in email, so the decision and its reasons are hard to find later.
- There is no record of what the source document said versus what was entered.

## Success measures

These are targets to test against, not results.

| Measure | How it is measured | Target |
|---|---|---|
| Time from email arriving to application ready for review | Timestamps in the audit log | Under 1 minute |
| Field-level extraction accuracy | Evaluation script against labelled samples | 90% or better |
| Policy breaches caught by rules | Every sample with a known breach raises the expected flag | 100% |
| Fields the analyst has to correct | Share of AI values changed by a human, tracked on the metrics page | Falling over time |
| LLM cost per application | Token usage recorded per call | Cents, not dollars |
| Decisions made without a human | Count of approvals with no named approver | Zero, by design |

## What the solution must not do

- Approve or decline a loan.
- Present a figure without showing where in the document it came from.
- Let a model decide whether a number breaches a policy limit.
- Send borrower details anywhere beyond the LLM call needed to read the document.

## Where AI fits and where it does not

AI is useful for one thing here: reading inconsistent documents and pulling out the same fields every time, and noticing soft risks a rule cannot express, such as an exit strategy that depends on a single buyer.

Everything else is ordinary software: arithmetic, thresholds, routing, record keeping. Those parts are deterministic code and standard Microsoft 365 connectors.

## Out of scope for this version

- Scanned PDFs (OCR).
- User accounts and role-based permissions.
- Writing approved applications into a loan origination system.
- Real customer data of any kind.

## Questions to put to real users

- How long does intake take per application today, and how many arrive each week?
- Which fields cause the most errors or back-and-forth with brokers?
- Which policy limits change most often, and who owns them?
- What must be recorded about an approval for audit or for funders?
- Where does the document need to live for records management?
