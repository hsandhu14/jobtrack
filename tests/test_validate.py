import json
import unittest
from datetime import date

from jobtrack import llm, validate
from jobtrack.validate import ValidationError, check_extraction, check_match

POSTING = """Northwind Labs is hiring a Software Engineer I (Backend) in Seattle, WA (hybrid).
Requirements: Python, PostgreSQL, REST APIs, Docker. Nice to have: Kubernetes.
Salary: $115,000 - $140,000. Apply by 2026-12-01."""

RESUME = """# Sam Student
- Built a Flask REST API serving 2,000 daily requests, backed by PostgreSQL
- Containerized three class projects with Docker
- Skills: Python, Java, SQL, Git"""

TODAY = date(2026, 10, 22)


def extraction(**over):
    raw = {"company": "Northwind Labs", "role": "Software Engineer I", "location": "Seattle, WA",
           "work_mode": "hybrid", "required_skills": ["Python", "PostgreSQL", "Docker"],
           "deadline": "2026-12-01", "salary_min": 115000, "salary_max": 140000}
    raw.update(over)
    return raw


class TestExtraction(unittest.TestCase):
    def test_clean_input_passes_untouched(self):
        job, issues = check_extraction(extraction(), POSTING, TODAY)
        self.assertEqual(issues, [])
        self.assertEqual(job["skills"], ["Python", "PostgreSQL", "Docker"])

    def test_missing_company_is_fatal(self):
        with self.assertRaises(ValidationError):
            check_extraction(extraction(company="  "), POSTING, TODAY)

    def test_hallucinated_skill_dropped(self):
        job, issues = check_extraction(extraction(required_skills=["Python", "Rust"]), POSTING, TODAY)
        self.assertEqual(job["skills"], ["Python"])
        self.assertIn("Rust", issues[0])

    def test_duplicate_skills_collapsed(self):
        job, _ = check_extraction(extraction(required_skills=["Python", "python"]), POSTING, TODAY)
        self.assertEqual(job["skills"], ["Python"])

    def test_company_not_in_posting_flagged_not_dropped(self):
        job, issues = check_extraction(extraction(company="Contoso"), POSTING, TODAY)
        self.assertEqual(job["company"], "Contoso")
        self.assertTrue(any("not found" in i for i in issues))

    def test_bad_and_past_deadlines(self):
        job, issues = check_extraction(extraction(deadline="Dec 1st"), POSTING, TODAY)
        self.assertIsNone(job["deadline"])
        _, issues = check_extraction(extraction(deadline="2026-01-01"), POSTING, TODAY)
        self.assertTrue(any("past" in i for i in issues))

    def test_inverted_salary_dropped(self):
        job, _ = check_extraction(extraction(salary_min=200000, salary_max=100000), POSTING, TODAY)
        self.assertIsNone(job["salary_min"])

    def test_salary_dropped_when_posting_has_no_pay(self):
        posting = POSTING.replace("Salary: $115,000 - $140,000.", "")
        job, issues = check_extraction(extraction(), posting, TODAY)
        self.assertIsNone(job["salary_max"])

    def test_invalid_work_mode_nulled(self):
        job, _ = check_extraction(extraction(work_mode="sometimes"), POSTING, TODAY)
        self.assertIsNone(job["work_mode"])


SKILLS = ["Python", "PostgreSQL", "Docker", "REST APIs"]


def match(**over):
    raw = {"score": 80, "summary": "Strong backend fit.",
           "matched": [{"skill": "Python", "evidence": "Skills: Python, Java"},
                       {"skill": "Docker", "evidence": "Containerized three class projects with Docker"}],
           "bullets": [{"source": "Built a Flask REST API serving 2,000 daily requests, backed by PostgreSQL",
                        "rewritten": "Designed a PostgreSQL-backed REST API in Flask handling 2,000 daily requests"}]}
    raw.update(over)
    return raw


class TestMatch(unittest.TestCase):
    def test_clean_match_and_computed_missing(self):
        m, issues = check_match(match(), RESUME, SKILLS)
        self.assertEqual(issues, [])
        self.assertEqual(m["missing"], ["PostgreSQL", "REST APIs"])
        self.assertEqual(m["coverage"], 50)

    def test_out_of_range_score_is_fatal(self):
        for bad in (101, -1, "90", 85.5, True):
            with self.assertRaises(ValidationError):
                check_match(match(score=bad), RESUME, SKILLS)

    def test_fabricated_evidence_dropped(self):
        raw = match(matched=[{"skill": "Docker", "evidence": "Led Kubernetes migration at Google"}])
        m, issues = check_match(raw, RESUME, SKILLS)
        self.assertEqual(m["matched"], [])
        self.assertIn("evidence", issues[0])

    def test_skill_not_in_job_dropped(self):
        raw = match(matched=[{"skill": "Java", "evidence": "Java"}])
        m, _ = check_match(raw, RESUME, SKILLS)
        self.assertEqual(m["matched"], [])

    def test_matched_skill_uses_job_spelling(self):
        raw = match(matched=[{"skill": "postgresql", "evidence": "backed by PostgreSQL"}])
        m, _ = check_match(raw, RESUME, SKILLS)
        self.assertEqual(m["matched"][0]["skill"], "PostgreSQL")

    def test_bullet_with_invented_number_dropped(self):
        raw = match(bullets=[{"source": "Containerized three class projects with Docker",
                              "rewritten": "Containerized 12 services with Docker"}])
        m, issues = check_match(raw, RESUME, SKILLS)
        self.assertEqual(m["bullets"], [])
        self.assertIn("12", issues[0])

    def test_bullet_with_unknown_source_dropped(self):
        raw = match(bullets=[{"source": "Interned at Amazon", "rewritten": "Interned at Amazon"}])
        m, _ = check_match(raw, RESUME, SKILLS)
        self.assertEqual(m["bullets"], [])

    def test_quote_normalization(self):
        self.assertTrue(validate.appears_in("**Python**,  Java", "Skills: Python, Java"))


class TestEnvelope(unittest.TestCase):
    def test_structured_output_used(self):
        out, meta = llm.parse_envelope(json.dumps(
            {"is_error": False, "structured_output": {"a": 1}, "total_cost_usd": 0.01}))
        self.assertEqual(out, {"a": 1})
        self.assertEqual(meta["cost_usd"], 0.01)

    def test_falls_back_to_result_text(self):
        out, _ = llm.parse_envelope(json.dumps({"is_error": False, "result": '{"a": 2}'}))
        self.assertEqual(out, {"a": 2})

    def test_error_and_garbage_raise(self):
        with self.assertRaises(llm.LLMError):
            llm.parse_envelope(json.dumps({"is_error": True, "result": "rate limited"}))
        with self.assertRaises(llm.LLMError):
            llm.parse_envelope("not json")


if __name__ == "__main__":
    unittest.main()
