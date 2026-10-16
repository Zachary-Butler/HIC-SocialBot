import unittest

from socialbot.news.cluster import cluster, norm_title
from tests.helpers import NOW, item, make_config


class ClusterTests(unittest.TestCase):
    def setUp(self):
        self.cfg = make_config()

    def test_same_event_across_outlets_becomes_one_story(self):
        items = [
            item("https://reuters.com/a", "Forty state attorneys general demand child protections in Character.AI sale",
                 "Reuters", tier="1", hours_old=30),
            item("https://theverge.com/b", "40 state AGs demand child protections in Character.AI bankruptcy sale - The Verge",
                 "The Verge", tier="2", hours_old=28),
            item("https://nhpr.org/c", "NHPR launches investigative series on AI data centers in New England",
                 "NHPR", tier="4", hours_old=40),
        ]
        stories = cluster(items, [], self.cfg, NOW)
        self.assertEqual(len(stories), 2)
        big = next(s for s in stories if len(s.items) == 2)
        self.assertEqual(big.lead.outlet_name, "Reuters")       # tier 1 leads
        self.assertEqual(big.outlets, ["Reuters", "The Verge"])

    def test_same_canonical_url_is_one_item(self):
        items = [item("https://theverge.com/b?utm_source=rss", "Headline here", "The Verge", tier="2"),
                 item("https://www.theverge.com/b/", "Headline here", "The Verge", tier="2", kind="bing")]
        stories = cluster(items, [], self.cfg, NOW)
        self.assertEqual(len(stories), 1)
        self.assertEqual(len(stories[0].items), 1)

    def test_existing_story_keeps_its_id_and_gains_items(self):
        first = cluster([item("https://reuters.com/a", "Anthropic researcher resigns, says labs are gambling with our lives",
                              "Reuters", tier="1", hours_old=60)], [], self.cfg, NOW)
        sid = first[0].id
        later = cluster([item("https://nbcnews.com/x", "Anthropic researcher resigns and says AI labs are gambling with our lives",
                              "NBC News", tier="1", hours_old=20)], first, self.cfg, NOW)
        self.assertEqual(len(later), 1)
        self.assertEqual(later[0].id, sid)
        self.assertEqual(len(later[0].items), 2)

    def test_similar_titles_far_apart_in_time_stay_separate(self):
        a = item("https://reuters.com/a", "OpenAI releases new model", "Reuters", tier="1", hours_old=150)
        b = item("https://reuters.com/b", "OpenAI releases new model", "Reuters", tier="1", hours_old=2)
        self.assertEqual(len(cluster([a, b], [], self.cfg, NOW)), 2)

    def test_norm_title(self):
        self.assertEqual(norm_title("AI Agents Broke Out! - Reuters"), "ai agents broke out")
