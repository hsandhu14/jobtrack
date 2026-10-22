"""Checks applied to every model output before it is stored.

These functions are pure (no I/O, no model) so they are fully unit-tested.
Each returns (clean_data, issues) where issues is a list of human-readable
strings describing what was dropped or flagged. Fatal problems raise
ValidationError and nothing is stored.
"""
import re
from datetime import date

WORK_MODES = {"onsite", "hybrid", "remote"}
MAX_BULLETS = 3


class ValidationError(Exception):
    pass


_PUNCT = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                        "–": "-", "—": "-", "*": None, "`": None})


def norm(s):
    return " ".join(s.translate(_PUNCT).lower().split())


def appears_in(needle, haystack):
    n = norm(needle)
    return bool(n) and n in norm(haystack)


def numbers_in(s):
    return set(re.findall(r"\d+(?:[.,]\d+)*", s))


def _opt_str(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def _opt_int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def check_extraction(raw, posting, today=None):
    today = today or date.today()
    issues = []

    company, role = _opt_str(raw.get("company")), _opt_str(raw.get("role"))
    if not company or not role:
        raise ValidationError("model returned no company or role")
    if not appears_in(company, posting):
        issues.append(f"company '{company}' not found in posting; check it")

    work_mode = raw.get("work_mode")
    if work_mode not in WORK_MODES:
        work_mode = None

    skills, seen = [], set()
    for s in raw.get("required_skills") or []:
        s = _opt_str(s)
        if not s or norm(s) in seen:
            continue
        if appears_in(s, posting):
            skills.append(s)
            seen.add(norm(s))
        else:
            issues.append(f"dropped skill '{s}': not in posting")

    deadline = _opt_str(raw.get("deadline"))
    if deadline:
        try:
            d = date.fromisoformat(deadline)
            if d < today:
                issues.append(f"deadline {deadline} is already past")
        except ValueError:
            issues.append(f"dropped unparseable deadline '{deadline}'")
            deadline = None

    smin, smax = _opt_int(raw.get("salary_min")), _opt_int(raw.get("salary_max"))
    if (smin, smax) != (None, None) and "$" not in posting and "usd" not in norm(posting):
        issues.append("dropped salary: posting mentions no pay")
        smin = smax = None
    if smin is not None and smax is not None and smin > smax:
        issues.append(f"dropped salary range {smin}>{smax}")
        smin = smax = None

    clean = {
        "company": company, "role": role, "location": _opt_str(raw.get("location")),
        "work_mode": work_mode, "skills": skills, "deadline": deadline,
        "salary_min": smin, "salary_max": smax,
    }
    return clean, issues


def check_match(raw, resume, job_skills):
    issues = []

    score = raw.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        raise ValidationError(f"score {score!r} is not an integer 0-100")

    by_norm = {norm(s): s for s in job_skills}
    matched, seen = [], set()
    for m in raw.get("matched") or []:
        skill, evidence = _opt_str(m.get("skill")), _opt_str(m.get("evidence"))
        if not skill or not evidence:
            continue
        key = norm(skill)
        if key not in by_norm:
            issues.append(f"dropped match '{skill}': not one of the job's skills")
        elif not appears_in(evidence, resume):
            issues.append(f"dropped match '{skill}': evidence not quoted from resume")
        elif key not in seen:
            seen.add(key)
            matched.append({"skill": by_norm[key], "evidence": evidence})

    # Missing skills and coverage are computed here, not by the model.
    missing = [s for s in job_skills if norm(s) not in seen]
    coverage = round(100 * len(matched) / len(job_skills)) if job_skills else None

    bullets = []
    for b in raw.get("bullets") or []:
        source, rewritten = _opt_str(b.get("source")), _opt_str(b.get("rewritten"))
        if not source or not rewritten:
            continue
        if not appears_in(source, resume):
            issues.append("dropped bullet: source line not in resume")
            continue
        invented = numbers_in(rewritten) - numbers_in(source)
        if invented:
            issues.append(f"dropped bullet: invented numbers {sorted(invented)}")
            continue
        bullets.append({"source": source, "rewritten": rewritten})
    if len(bullets) > MAX_BULLETS:
        bullets = bullets[:MAX_BULLETS]

    clean = {
        "score": score, "coverage": coverage, "summary": _opt_str(raw.get("summary")) or "",
        "matched": matched, "missing": missing, "bullets": bullets,
    }
    return clean, issues


def count_claims(raw, kind):
    """How many individual claims the model made, for drop-rate stats."""
    if kind == "extract":
        return len(raw.get("required_skills") or []) + 2
    return len(raw.get("matched") or []) + len(raw.get("bullets") or [])
