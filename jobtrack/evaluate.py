"""Score the extraction step against hand-labeled real postings in eval/.

Scoring is plain code. Each posting runs through the same llm.extract ->
validate.check_extraction path that `jobtrack add` uses.
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import llm, validate

EVAL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval")
FIELDS = ["company", "role", "work_mode", "deadline", "salary"]
SALARY_TOLERANCE = 0.02

ALIASES = {"golang": "go", "node": "node.js", "nodejs": "node.js", "postgres": "postgresql",
           "k8s": "kubernetes", "js": "javascript", "ts": "typescript", "gcp": "google cloud",
           "google cloud platform": "google cloud", "amazon web services": "aws"}


def skill_key(s):
    n = validate.norm(s)
    return ALIASES.get(n, n)


def split_skills(skills):
    """'C/C++' and 'JavaScript/TypeScript' count as separate skills."""
    out = []
    for s in skills:
        out += [p for p in re.split(r"\s*/\s*|\s*,\s*", s) if p.strip()]
    return out


def score_salary(pred_min, pred_max, gold):
    values = [v for v in (pred_min, pred_max) if v is not None]
    if gold is None:
        return not values
    lo, hi = gold[0] * (1 - SALARY_TOLERANCE), gold[1] * (1 + SALARY_TOLERANCE)
    return bool(values) and all(lo <= v <= hi for v in values)


def score_one(pred, gold):
    """Field-level correctness plus skill hit counts for one posting."""
    if pred is None:
        return {"fields": {f: False for f in FIELDS}, "tp": 0, "fp": 0, "fn": len(gold["skills"]),
                "false_positives": [], "missed": gold["skills"]}
    # Compare titles as word sets so "[Summer 2027] SWE Intern" == "SWE Intern (Summer 2027)".
    pr, gr = (set(re.findall(r"[a-z0-9+#]+", validate.norm(x))) for x in (pred["role"], gold["role"]))
    fields = {
        "company": validate.norm(pred["company"]) in {validate.norm(c) for c in gold["company"]},
        "role": pr <= gr or gr <= pr,
        "work_mode": pred["work_mode"] in gold["work_mode"],
        "deadline": pred["deadline"] == gold["deadline"],
        "salary": score_salary(pred["salary_min"], pred["salary_max"], gold["salary"]),
    }
    core = {skill_key(s) for s in gold["skills"]}
    allowed = core | {skill_key(s) for s in gold["skills_optional"]}
    predicted = {skill_key(s): s for s in split_skills(pred["skills"])}
    false_pos = [s for k, s in predicted.items() if k not in allowed]
    missed = [s for s in gold["skills"] if skill_key(s) not in predicted]
    return {"fields": fields, "tp": len(core & predicted.keys()), "fp": len(false_pos),
            "fn": len(missed), "false_positives": false_pos, "missed": missed}


def summarize(records, model):
    n = len(records)
    tp, fp, fn = (sum(r["score"][k] for r in records) for k in ("tp", "fp", "fn"))
    costs = [r["cost_usd"] for r in records if r.get("cost_usd") is not None]
    times = [r["duration_ms"] for r in records if r.get("duration_ms")]
    return {
        "model": model, "postings": n, "date": date.today().isoformat(),
        "errors": sum(1 for r in records if r["error"]),
        "field_accuracy": {f: round(sum(r["score"]["fields"][f] for r in records) / n, 3)
                           for f in FIELDS},
        "all_fields_correct": round(sum(all(r["score"]["fields"].values()) for r in records) / n, 3),
        "skill_precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "skill_recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "claims_dropped_by_validators": sum(
            sum(i.startswith("dropped") for i in r["issues"]) for r in records),
        "avg_seconds": round(sum(times) / len(times) / 1000, 1) if times else None,
        "total_cost_usd": round(sum(costs), 4) if costs else None,
    }


def _run_one(item):
    with open(os.path.join(EVAL_DIR, "postings", item["file"]), encoding="utf-8") as f:
        posting = f.read()
    rec = {"file": item["file"], "pred": None, "issues": [], "error": None}
    try:
        raw, meta = llm.extract(posting)
        rec.update(meta)
        rec["pred"], rec["issues"] = validate.check_extraction(raw, posting, date.today())
    except (llm.LLMError, validate.ValidationError) as e:
        rec["error"] = str(e)
    rec["score"] = score_one(rec["pred"], item)
    return rec


def run(model=None, limit=None, workers=4):
    if model:
        llm.MODEL = model
    with open(os.path.join(EVAL_DIR, "labels.json"), encoding="utf-8") as f:
        labels = json.load(f)[:limit]
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(_run_one, labels))
    summary = summarize(records, llm.MODEL)
    summary["wall_seconds"] = round(time.monotonic() - start, 1)

    out_dir = os.path.join(EVAL_DIR, "results")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{summary['date']}-{llm.MODEL}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "records": records}, f, indent=2)
    return summary, records, path
