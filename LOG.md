# Development log

## 2026-10-22: Plan

**Goal:** a job application tracker where a model does real work on every run, for AI 201 Artifact 3 and for my own job search.

**Shape:** a Python CLI that runs Claude Code headless (`claude -p`) as one step of a pipeline. I chose this over the API because the course's Claude Code access covers it and the API doesn't.

**Split of responsibilities (decided up front):**
- Model: (1) extract structured fields from a messy posting; (2) judge resume fit, quote evidence and rewrite bullets.
- Code: everything else, plus checking every model claim against the source text.

**Key design decision:** have the model *quote* its evidence instead of just asserting it, so code can verify each quote with a substring check. This turns "did the model hallucinate?" into a check code can run on every output.

## 2026-10-22: Build, day 1

- Checked `claude --help`: `--json-schema` returns a `structured_output` field and `--tools ""` disables tools. Used both. `--system-prompt` replaces the default agent prompt, which keeps each call small and focused.
- `claude` was not on PATH (it's bundled with the VS Code extension), so `find_claude()` falls back to the extension's binary.
- Run the CLI from a temp dir so this repo's CLAUDE.md isn't loaded into the extraction prompt.
- Wrote `validate.py` as pure functions plus 20 unit tests that don't call the model.
- **Bug found by tests:** quote normalization replaced markdown `**` with spaces, which turned `**Python**,` into `python ,`, so it didn't match `Python,`. Changed it to delete the markers instead.
- Moved "missing skills" from the model to code: it's just the job's skills minus the verified matches, so there's no reason to let the model guess it.
- Added a check for invented numbers on rewritten bullets: any number in the rewrite must also appear in the source line. This stops "Containerized 3 projects" from becoming "Containerized 12 services".
- First real run on the 2 sample postings: all fields correct, 0 of 34 claims dropped. The match score (68) and the code-computed coverage (78%) are shown side by side so disagreements are visible.

## Next ideas
- Run it on 20+ real postings and record the drop rate from `jobtrack stats`
- Add a `followup <id>` command that drafts a follow-up email for stale applications
- Make `add` accept a whole folder of saved postings
