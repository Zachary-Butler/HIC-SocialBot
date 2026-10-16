import unittest

from socialbot.news.draft.verify import numbers_in, quotes_in, verify

SOURCE = """Anthropic's Sep 10 threat report says its newer models are "no longer comfortably below" the
level where they could help someone build a biological weapon. The company says it disrupted five
cases of misuse. Kroger will cut 3,000 corporate jobs over three years. About 1 in 6 voters chose
speeding up; 58% said the government should act, a poll of 2,019 adults found in 2026."""


class VerifyTests(unittest.TestCase):
    def test_quotes_and_numbers_found(self):
        draft = ('Its models are **"no longer comfortably below"** the bioweapons line, the report says. '
                 'Kroger will cut **3000** jobs; 58% of voters agree.')
        res = verify(draft, [SOURCE])
        self.assertTrue(res.ok, res.summary())
        self.assertEqual(res.quotes_found, ['no longer comfortably below'])
        self.assertIn("3000", res.numbers_found)

    def test_paraphrase_in_quotes_fails(self):
        res = verify('The report says models are "not safely below" the line.', [SOURCE])
        self.assertEqual(res.quotes_missing, ["not safely below"])
        self.assertFalse(res.ok)

    def test_invented_number_fails_and_years_are_ignored(self):
        res = verify("Kroger will cut 4,000 jobs in 2026.", [SOURCE])
        self.assertEqual(res.numbers_missing, ["4,000"])
        self.assertNotIn("2026", res.numbers_missing + res.numbers_found)

    def test_curly_quotes_and_dollar_amounts(self):
        src = "Disney is the lead bidder at $20 million, the filing says: “the children’s data stays protected.”"
        res = verify("Disney bid **$20 million**. The filing says “the children’s data stays protected.”", [src])
        self.assertTrue(res.ok, res.summary())

    def test_extractors(self):
        self.assertEqual(quotes_in('He said "this is long enough" and "no".'), ["this is long enough"])
        self.assertEqual(numbers_in("about 1 in 6, $20 million, 10% within 2026"), ["1", "6", "$20 million", "10%"])
