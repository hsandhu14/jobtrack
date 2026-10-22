import unittest

from jobtrack.evaluate import score_one, score_salary, split_skills

GOLD = {"company": ["Scale", "Scale AI"], "role": "[Summer 2027] Software Engineer Intern",
        "work_mode": ["hybrid", None], "deadline": None, "salary": [100000, 120000],
        "skills": ["Python", "Go", "C++"], "skills_optional": ["React"]}


def pred(**over):
    p = {"company": "Scale AI", "role": "Software Engineer Intern (Summer 2027)", "work_mode": "hybrid",
         "deadline": None, "salary_min": 100000, "salary_max": 120000, "skills": ["Python", "Golang", "C++"]}
    p.update(over)
    return p


class TestScoring(unittest.TestCase):
    def test_perfect_prediction(self):
        s = score_one(pred(), GOLD)
        self.assertTrue(all(s["fields"].values()))
        self.assertEqual((s["tp"], s["fp"], s["fn"]), (3, 0, 0))

    def test_reordered_role_still_matches(self):
        self.assertTrue(score_one(pred(role="Software Engineer Intern"), GOLD)["fields"]["role"])
        self.assertFalse(score_one(pred(role="Data Engineer Intern"), GOLD)["fields"]["role"])

    def test_optional_skill_is_not_a_false_positive(self):
        s = score_one(pred(skills=["Python", "React"]), GOLD)
        self.assertEqual((s["tp"], s["fp"], s["fn"]), (1, 0, 2))

    def test_concept_counts_as_false_positive(self):
        s = score_one(pred(skills=["Python", "Go", "C++", "algorithms"]), GOLD)
        self.assertEqual(s["false_positives"], ["algorithms"])

    def test_slash_lists_split(self):
        self.assertEqual(split_skills(["C/C++", "JavaScript / TypeScript"]),
                         ["C", "C++", "JavaScript", "TypeScript"])

    def test_salary_tolerance_and_nulls(self):
        self.assertTrue(score_salary(None, None, None))
        self.assertFalse(score_salary(100000, None, None))
        self.assertFalse(score_salary(None, None, [1, 2]))
        self.assertTrue(score_salary(98500, 121000, [100000, 120000]))
        self.assertFalse(score_salary(90000, 120000, [100000, 120000]))

    def test_failed_call_scores_zero(self):
        s = score_one(None, GOLD)
        self.assertFalse(any(s["fields"].values()))
        self.assertEqual(s["fn"], 3)


if __name__ == "__main__":
    unittest.main()
