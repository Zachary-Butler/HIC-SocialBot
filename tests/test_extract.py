import unittest

from socialbot.news.extract import meta_tags, parse_article

HTML = """<!doctype html><html><head><title>Eight states sue OpenAI | Example News</title>
<meta property="og:title" content="Eight states sue OpenAI over ChatGPT harms">
<meta property="og:image" content="https://cdn.example.com/img/openai-suit.jpg">
<meta property="og:image:alt" content="The OpenAI logo on a phone screen. Photo: Example/Jane Doe">
<meta property="article:published_time" content="2026-10-14T18:02:00Z">
<meta name="author" content="Jane Doe">
<meta property="og:site_name" content="Example News">
</head><body><nav>Home · Tech · Politics</nav>
<article>
<h1>Eight states sue OpenAI over ChatGPT harms</h1>
<p>Eight US states sued OpenAI on Tuesday, alleging that ChatGPT violated consumer protection laws by harming children and deceiving adults about the product's safety, according to complaints filed in state courts.</p>
<p>"We will not wait for Washington to act," one attorney general said in a statement announcing the filing, which seeks civil penalties and changes to how the chatbot handles minors.</p>
<p>OpenAI said in a statement that it disagreed with the allegations and would respond in court. The company added that it had introduced new parental controls earlier this year and planned further safety changes before the end of the year.</p>
<p>The suits follow a wave of litigation against chatbot makers this year and come as several states weigh their own rules for AI companions marketed to teenagers, a category regulators say has grown quickly.</p>
</article><footer>© Example</footer></body></html>"""


class ExtractTests(unittest.TestCase):
    def test_parse_article_fields(self):
        art = parse_article(HTML, "https://example.com/news/openai-suit")
        self.assertTrue(art.ok, art.error)
        self.assertIn("Eight US states sued OpenAI", art.text)
        self.assertNotIn("Home · Tech", art.text)
        self.assertEqual(art.image_url, "https://cdn.example.com/img/openai-suit.jpg")
        self.assertIn("Jane Doe", art.image_credit)
        self.assertEqual(art.author, "Jane Doe")
        self.assertTrue(art.published_at.startswith("2026-10-14"))
        self.assertEqual(art.sitename, "Example News")

    def test_short_page_is_not_ok(self):
        art = parse_article("<html><body><p>Subscribe to read.</p></body></html>", "https://example.com/paywalled")
        self.assertFalse(art.ok)
        self.assertIn("chars", art.error)

    def test_meta_tags_both_attribute_orders(self):
        tags = meta_tags('<meta content="X" property="og:title"><meta name="author" content="Y">')
        self.assertEqual((tags["og:title"], tags["author"]), ("X", "Y"))
