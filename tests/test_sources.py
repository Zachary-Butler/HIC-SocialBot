import unittest

from socialbot.news.sources.feeds import parse_bing, parse_google, parse_outlet_feed, strip_outlet_suffix
from tests.helpers import NOW, SINCE, make_config

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Guardian AI</title>
<item><title>Forty state attorneys general demand child protections in Character.AI sale</title>
<link>https://www.theguardian.com/technology/2026/oct/15/ags-character-ai?utm_source=rss</link>
<pubDate>Thu, 15 Oct 2026 09:00:00 GMT</pubDate>
<description><![CDATA[<p>The states say any buyer must protect <b>minors</b>.</p>]]></description></item>
<item><title>Old story</title><link>https://www.theguardian.com/technology/2026/sep/01/old</link>
<pubDate>Tue, 01 Sep 2026 09:00:00 GMT</pubDate></item>
<item><title>No link here</title></item>
</channel></rss>"""

GOOGLE = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>"AI" - Google News</title>
<item><title>Forty state AGs demand child protections in Character.AI bankruptcy sale - Reuters</title>
<link>https://news.google.com/rss/articles/CBMiabc?oc=5</link>
<pubDate>Wed, 14 Oct 2026 18:00:00 GMT</pubDate>
<description>&lt;ol&gt;&lt;li&gt;related links&lt;/li&gt;&lt;/ol&gt;</description>
<source url="https://www.reuters.com">Reuters</source></item>
<item><title>Local station covers data center fight - WXYZ 7 News Detroit</title>
<link>https://news.google.com/rss/articles/CBMidef?oc=5</link>
<pubDate>Wed, 14 Oct 2026 18:00:00 GMT</pubDate>
<source url="https://www.wxyz.com">WXYZ 7 News Detroit</source></item>
<item><title>Chatbot company collapses - Breitbart</title>
<link>https://news.google.com/rss/articles/CBMighi?oc=5</link>
<pubDate>Wed, 14 Oct 2026 18:00:00 GMT</pubDate>
<source url="https://www.breitbart.com">Breitbart</source></item>
</channel></rss>"""

BING = b"""<?xml version="1.0"?><rss xmlns:News="https://www.bing.com:443/news/search?q=AI&amp;format=rss" version="2.0">
<channel><title>AI - Bing News</title>
<item><title>Anthropic gives METR employee-level access to audit safety</title>
<link>https://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;aid=&amp;tid=T1&amp;url=https%3a%2f%2ftechcrunch.com%2f2026%2f10%2f15%2fmetr-anthropic%2f&amp;c=1&amp;mkt=en-us</link>
<description>Anthropic compared it to bank examiners.</description>
<pubDate>Thu, 15 Oct 2026 14:00:00 GMT</pubDate>
<News:Source>TechCrunch</News:Source></item>
</channel></rss>"""


class SourceParsingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = make_config()
        self.outlets = self.cfg["outlets"]

    def test_outlet_feed_filters_window_and_tiers(self):
        outlet = self.outlets["by_domain"]["theguardian.com"]
        items = parse_outlet_feed(RSS, "https://feed", self.outlets, outlet, NOW, SINCE)
        self.assertEqual([i.title for i in items], ["Forty state attorneys general demand child protections in Character.AI sale"])
        it = items[0]
        self.assertEqual((it.outlet_name, it.tier, it.source_kind), ("The Guardian", "1", "rss"))
        self.assertEqual(it.canonical_url, "https://theguardian.com/technology/2026/oct/15/ags-character-ai")
        self.assertEqual(it.summary, "The states say any buyer must protect minors.")
        self.assertEqual(it.published_at, "2026-10-15T09:00:00+00:00")

    def test_google_uses_source_tag_for_outlet_and_strips_suffix(self):
        items = parse_google(GOOGLE, "q", self.outlets, NOW, SINCE)
        self.assertEqual(len(items), 2)                       # the never_source item is dropped
        reuters, wxyz = items
        self.assertEqual(reuters.title, "Forty state AGs demand child protections in Character.AI bankruptcy sale")
        self.assertEqual((reuters.outlet_name, reuters.tier), ("Reuters", "1"))
        self.assertFalse(reuters.resolved)
        self.assertEqual((wxyz.outlet_name, wxyz.tier), ("WXYZ Detroit", "4"))

    def test_bing_unwraps_redirect_and_matches_outlet(self):
        items = parse_bing(BING, "q", self.outlets, NOW, SINCE)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it.url, "https://techcrunch.com/2026/10/15/metr-anthropic/")
        self.assertTrue(it.resolved)
        self.assertEqual((it.outlet_name, it.tier, it.source_kind), ("TechCrunch", "2", "bing"))

    def test_strip_outlet_suffix_keeps_real_dashes(self):
        self.assertEqual(strip_outlet_suffix("Headline - Reuters", "Reuters"), "Headline")
        self.assertEqual(strip_outlet_suffix("Headline | The New York Times"), "Headline")
        long_tail = "AI agents broke out - and they hacked a real company by themselves"
        self.assertEqual(strip_outlet_suffix(long_tail), long_tail)
