import unittest

from jobtrack import logos


class TestLogos(unittest.TestCase):
    def test_known_company_with_suffix(self):
        self.assertEqual(logos.domain_for("Microsoft Corporation"), "microsoft.com")
        self.assertEqual(logos.domain_for("Stripe, Inc."), "stripe.com")

    def test_domain_from_employer_url(self):
        self.assertEqual(logos.domain_for("Acme", "https://careers.acme.io/jobs/123"), "acme.io")

    def test_job_board_url_ignored(self):
        self.assertIsNone(logos.domain_for("Acme", "https://boards.greenhouse.io/acme/jobs/1"))

    def test_unknown_company_without_url(self):
        self.assertIsNone(logos.domain_for("Northwind Labs"))

    def test_monogram_is_stable(self):
        self.assertEqual(logos.monogram("Northwind Labs"), logos.monogram("northwind labs"))
        self.assertEqual(logos.monogram("Northwind Labs")[0], "NL")


if __name__ == "__main__":
    unittest.main()
