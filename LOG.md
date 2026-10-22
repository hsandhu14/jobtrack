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

## 2026-10-22: Dashboard redesign with company logos

- **Plan:** make the dashboard look like a real product: a logo for each company, a fit-score ring, and skill chips that show which skills were verified.
- Added `logos.py` (plain code, no model): maps company names to domains for about 50 well-known employers, otherwise reads the domain from the posting URL, skipping job boards like Greenhouse and Lever.
- Chose not to commit any logo image files. Icons load from the company's domain when the page is viewed, with a colored-initials monogram as fallback, so the repo carries no trademarked artwork and unknown companies still look good.
- Added a "Target companies" strip of 16 popular SWE employers. Each links to its careers page and gets a checkmark once a job at that company is tracked. It can be overridden with `targets.txt`.
- Job cards now show the model's fit score as a ring next to the code-verified coverage %, with matched skills in green and missing skills dashed, so you can see where the model's opinion and the verified evidence disagree.
- Checked the result by taking a headless Edge screenshot: all 16 target logos loaded.
- 5 new unit tests for domain lookup (25 total).

## 2026-10-22: Extraction eval on real postings, CI, screenshot

- **Plan:** measure how accurate extraction actually is instead of judging by eye. Add CI and a README screenshot so the repo shows its quality at a glance.
- Pulled 20 current early-career SWE postings from 15 companies through the public Greenhouse and Lever job-board APIs. Picked them to cover edge cases: monthly, hourly and multi-location pay, a deadline with no year, a start-by date that isn't a deadline, postings with mixed or missing work modes, and "not required" tech stacks.
- Wrote labels for all 20 **before running the model on any of them**. Labeling rules are in `eval/README.md`. Optional skills, such as nice-to-haves or a team's stack, are neither required nor penalized, so precision isn't unfair to the model.
- Added `jobtrack eval` (`evaluate.py`), which reuses the exact `add` path and scores it in plain code.
- **Baseline (Sonnet):** all 5 fields 100% correct, but skill precision was only 90%. The model listed concepts like "data structures and algorithms" and "distributed systems" because the prompt said "concrete technical skills" without defining that.
- **Fix:** the prompt now lists the categories to include and the concepts to exclude. Skill precision went to 100% and recall stayed at 99%.
- **Scorer bug:** "[Summer 2027] Software Engineer Intern" and "Software Engineer Intern (Summer 2027)" were scored as different titles. Role comparison now uses word sets. Rescored all saved runs from their stored predictions with no new model calls, so every run is judged the same way.
- **Haiku vs Sonnet:** same field accuracy, but Haiku's skill recall was 89% because it skipped language lists phrased as examples. It costs about 1/12 as much at list price but is no faster through the CLI. Kept Sonnet as the default.
- Kept the Pinterest work-mode label even though the model's `null` is defensible. I didn't want to edit labels to match model output. Noted the caveat that the prompt was tuned on the same 20 postings.
- Added GitHub Actions running the 32 unit tests on Python 3.10–3.13, plus a README badge.
- Rebuilt the demo dashboard from real postings (so real logos appear) using the example resume, and saved a screenshot to `docs/dashboard.png`. Fixed two display issues it showed: "$153k–$153k" for a single figure, and a deadline countdown on rejected jobs.

## Next ideas
- Label 10–20 *new* postings as a held-out set to check that the prompt fix generalizes
- Run it on 20+ real postings and record the drop rate from `jobtrack stats`
- Add a `followup <id>` command that drafts a follow-up email for stale applications
- Make `add` accept a whole folder of saved postings
