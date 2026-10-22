# Extraction eval

This folder holds 20 real early-career software engineering postings and hand-written labels for them. They're used to measure how accurately `jobtrack add` extracts fields from a posting.

```bash
python -m jobtrack eval                 # default model
python -m jobtrack eval --model haiku   # compare models
```

Each run sends every posting through the same path as `jobtrack add` (`llm.extract`, then `validate.check_extraction`), scores the results in plain code ([evaluate.py](../jobtrack/evaluate.py)), and saves each prediction and score to `results/<date>-<model>.json`.

## Data

- **Postings:** 20 public listings from 15 companies, retrieved on 2026-10-22 through the Greenhouse and Lever public job-board APIs. They cover new-grad, intern and early-career roles, including ML, data and infrastructure jobs and one posting outside the US. [sources.json](sources.json) lists the original URL for each one. They were chosen to include tricky cases:
  - pay stated as monthly, hourly, or as several ranges for different locations
  - an application deadline with no year
  - a start-by date that is not an application deadline
  - postings that state no work mode, or more than one
  - technology lists that are explicitly marked "not required"
- **Labels:** [labels.json](labels.json). These were written before running the model on any of these postings, so they weren't influenced by its output. They were drafted with Claude Code and need a second human review.

## Labeling rules

| Field | Rule |
|---|---|
| company | The employer's name. A list means any of those names is accepted, e.g. "Scale" or "Scale AI". |
| role | The job title. Word order doesn't matter, so "[Summer 2027] SWE Intern" matches "SWE Intern (Summer 2027)". |
| work_mode | The accepted values. It includes `null` when the posting doesn't clearly state a single mode. |
| deadline | An application deadline (YYYY-MM-DD) or `null`. A start-by date or "rolling basis" is not a deadline. |
| salary | `[low, high]` annual USD covering every stated range (hourly ×2080, monthly ×12), or `null`. A prediction is correct if every value is within 2% of that range. |
| skills | Named technologies only (languages, frameworks, databases, cloud platforms, tools) taken from requirements or responsibilities, including examples like "e.g. Python, Java". General concepts such as "algorithms" or "distributed systems" don't count. |
| skills_optional | Technologies a posting mentions but doesn't require, such as nice-to-haves, the team's stack, or "not required" lists. Predicting one isn't penalized, and missing one isn't penalized either. |

Skill precision = predicted skills that are in `skills` or `skills_optional` ÷ all predicted skills. Skill recall = required `skills` that were predicted ÷ all required `skills`. Both are totaled across all postings.

## Results (2026-10-22)

| Run | Company | Role | Work mode | Deadline | Salary | All 5 correct | Skill precision | Skill recall | Cost* |
|---|---|---|---|---|---|---|---|---|---|
| Sonnet, original prompt | 100% | 100% | 100% | 100% | 100% | 100% | 90% | 99% | $0.29 |
| **Sonnet, current prompt** | 100% | 100% | 95% | 100% | 100% | 95% | **100%** | 99% | $0.29 |
| Haiku, current prompt | 100% | 100% | 95% | 100% | 100% | 95% | 100% | 89% | $0.03 |

\*Total for all 20 postings at API list prices, as reported by the CLI. On a Claude Code plan these runs are covered by the subscription. Both models averaged about 6.5 seconds per call, mostly startup overhead from the CLI.

**What changed:** the original prompt asked for "concrete technical skills," so the model also returned concepts like "data structures and algorithms" and "distributed systems." That made skill precision 90%. The prompt now names the categories to include and lists concepts to exclude, which brought precision to 100%.

**Remaining misses:**
- Pinterest internship work mode: the posting says some interns are hybrid and some fully remote. The model returned `null`, which is arguably right. The label was left unchanged rather than edited to fit the output.
- Palantir: Sonnet missed "Bash" in a list of languages.
- Haiku: missed whole language lists in the Stripe and Figma postings, where the languages are phrased as examples ("We work mostly in…", "e.g. C++, JavaScript…"). This is why Sonnet stays the default.

**Caveats:** the prompt was changed after seeing the baseline on these same 20 postings, so the current-prompt results may be optimistic. A new set of held-out postings would give a cleaner number. Each configuration was run once, and results vary somewhat between runs.
