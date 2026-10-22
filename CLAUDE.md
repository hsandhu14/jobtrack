# jobtrack: notes for Claude

A Python CLI job tracker that calls Claude Code headless (`claude -p`) for two narrow tasks. Uses only the standard library.

## Ground rules
- **Only `jobtrack/llm.py` talks to the model.** Keep prompts, schemas and the subprocess call there.
- **Every model output goes through `jobtrack/validate.py` before it is stored or printed.** Validators are pure functions that return `(clean, issues)`. A fatal problem raises `ValidationError`.
- The model **extracts posting fields** and **judges resume fit / rewrites bullets**. Nothing else.
- Code owns anything that can be computed deterministically: missing skills, coverage %, staleness, status history and stats. Don't move these into prompts.
- Every new kind of model claim needs a grounding check in `validate.py` (verbatim-in-source, in an allowed set, or in range) and a unit test.
- Log each model call with `db.log_call`, including the claims and drop counts.

## Commands
- Tests: `python -m unittest` (no model calls; keep it that way)
- Run: `python -m jobtrack <cmd>`; use `JOBTRACK_DB=data/test.db` for experiments

## Log
Append to `LOG.md` whenever a plan is made or behavior changes. Give the date, what changed and why.
