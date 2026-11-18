# Project: LoanLens (Commercial Loan Intake Assistant)

A demo internal tool for a fictional commercial property lender. See README.md for what it does and docs/discovery.md for why. The working plan is in notes/PLAN.md.

## How to work

- Build one stage at a time, in the order in notes/PLAN.md. Do not start the next stage or any optional item unless asked.
- After each piece, explain in plain language what was built and why it was designed that way. The developer needs to be able to explain every part.
- When a design decision is made or changed, update README.md and notes/interview-notes.md in the same change.
- Never put a result in README.md that has not been measured. Leave it marked TBC.

## Conventions

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2. Type hints everywhere. Run `pytest` before saying a task is done.
- Frontend: React + TypeScript + Vite, shadcn/ui, TanStack Query. No `any`.
- All policy numbers (LVR limits and so on) live in one place: `backend/app/pipeline/rules.py`, mirrored in `backend/data/credit_policy.md`. Change both together.
- Numeric policy decisions are deterministic Python. Never ask the LLM to decide them.
- Every extracted field carries value, confidence, evidence and page.
- Critical risk flags come only from rules. LLM-raised flags are capped at warning and must cite a policy section.
- LLM provider and model name come from environment variables. Never hardcode keys or model names.
- Write endpoints require the API key or demo passcode. The public demo is read-only without it.
- Public files (everything outside notes/) are in English, Australian spelling.

## Data and privacy

- All sample data is fictional. Never use real company names, logos or people anywhere in the repository.
- `notes/` is private and git-ignored. Nothing in it is referenced from public files.
- `.env` is never committed. Keep `.env.example` up to date instead.

## Git

- Small commits with clear messages; one feature per branch and pull request.
