import unittest

from socialbot.core.urls import canonical, is_aggregator, match_outlet, registrable_domain, unwrap_bing
from tests.helpers import make_config


class UrlTests(unittest.TestCase):
    def test_canonical_strips_tracking_amp_and_www(self):
        a = canonical("https://www.theverge.com/ai/123/story?utm_source=rss&utm_medium=feed#top")
        b = canonical("http://theverge.com/ai/123/story/")
        c = canonical("https://theverge.com/ai/123/story/amp/")
        self.assertEqual(a, "https://theverge.com/ai/123/story")
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_canonical_keeps_meaningful_query(self):
        self.assertEqual(canonical("https://example.com/a?id=5&utm_campaign=x"), "https://example.com/a?id=5")

    def test_registrable_domain(self):
        self.assertEqual(registrable_domain("https://feeds.npr.org/1019/rss.xml"), "npr.org")
        self.assertEqual(registrable_domain("https://randomblog.example/x"), "randomblog.example")
        self.assertEqual(registrable_domain("www.nytimes.com"), "nytimes.com")

    def test_match_outlet_prefers_exact_host(self):
        by = make_config()["outlets"]["by_domain"]
        self.assertEqual(match_outlet("https://importai.substack.com/p/x", by)["name"], "Import AI")
        self.assertEqual(match_outlet("https://www.nytimes.com/2026/x.html", by)["tier"], "1")
        self.assertIsNone(match_outlet("https://randomblog.example/x", by))

    def test_bing_unwrap_and_aggregators(self):
        wrapped = ("https://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=T&url="
                   "https%3a%2f%2fwww.theverge.com%2fai%2f1&c=1&mkt=en-us")
        self.assertEqual(unwrap_bing(wrapped), "https://www.theverge.com/ai/1")
        self.assertTrue(is_aggregator("https://news.google.com/rss/articles/CBMi"))
        self.assertFalse(is_aggregator("https://www.theverge.com/ai/1"))
