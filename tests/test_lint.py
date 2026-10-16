import unittest
from datetime import date

from socialbot.news.draft.lint import lint

BEFORE, AFTER = date(2026, 10, 16), date(2026, 11, 4)


class LintTests(unittest.TestCase):
    def test_named_official_flagged_only_before_election(self):
        body = "Iowa Attorney General Brenna Bird said the company is hurting kids. Sen. Ted Cruz agreed."
        w = lint("h", body, [], today=BEFORE)
        self.assertEqual(len(w), 2)
        self.assertIn("Brenna Bird", w[0])
        self.assertEqual(lint("h", body, [], today=AFTER), [])

    def test_role_only_passes(self):
        self.assertEqual(lint("h", "Iowa's attorney general said the company is hurting kids.", [], today=BEFORE), [])

    def test_party_label_flagged(self):
        w = lint("h", "Sen. Amy Klobuchar (D-MN) and a Republican colleague wrote the bill.", [], today=AFTER)
        self.assertEqual(len(w), 2)

    def test_deceased_minor_names(self):
        w = lint("h", "The teen's parents, Maria Garcia and Juan Garcia, sued Character AI in Los Angeles.", ["deceased_minor"], today=AFTER)
        self.assertEqual(len(w), 1)
        self.assertIn("Maria Garcia", w[0])
        self.assertNotIn("Los Angeles", w[0])
        self.assertEqual(lint("h", "The teen's parents sued the company.", ["deceased_minor"], today=AFTER), [])
