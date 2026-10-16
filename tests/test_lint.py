import unittest
from datetime import date

from socialbot.news.draft.lint import lint

BEFORE, AFTER = date(2026, 10, 16), date(2026, 11, 4)


class LintTests(unittest.TestCase):
    def test_structured_officials_flagged_only_before_election(self):
        w = lint("h", "The state's top lawyer said the company is hurting kids.", [], officials_named=["Brenna Bird"], today=BEFORE)
        self.assertEqual(len(w), 1)
        self.assertIn("Brenna Bird", w[0])
        self.assertEqual(lint("h", "same body", [], officials_named=["Brenna Bird"], today=AFTER), [])

    def test_body_regex_backstop_and_titlecase_headline_ignored(self):
        body = "Iowa Attorney General Brenna Bird said the company is hurting kids."
        w = lint("NYC's Comptroller Urges Anthropic To Pause", body, [], today=BEFORE)
        self.assertEqual(len(w), 1)                      # the headline's title case is not a name
        self.assertIn("Brenna Bird", w[0])
        self.assertEqual(lint("h", "Iowa's attorney general said the company is hurting kids.", [], today=BEFORE), [])

    def test_party_label_flagged(self):
        w = lint("h", "Sen. Amy Klobuchar (D-MN) and a Republican colleague wrote the bill.", [], today=AFTER)
        self.assertEqual(len(w), 2)

    def test_deceased_minor_uses_people_named(self):
        w = lint("h", "The teen's parents sued the company.", ["deceased_minor"], people_named=["Maria Garcia"], today=AFTER)
        self.assertEqual(len(w), 1)
        self.assertIn("Maria Garcia", w[0])
        self.assertEqual(lint("h", "The teen's parents sued the company.", ["deceased_minor"], people_named=[], today=AFTER), [])

    def test_cta_on_story_slide_flagged(self):
        w = lint("h", "Safety shouldn't wait. Present an AI Reality Check on Nov 14.", [], today=AFTER)
        self.assertEqual(len(w), 1)
        self.assertIn("closing slide", w[0])
