import unittest

from socialbot.news.cluster import cluster
from socialbot.news.rank import on_ramp_hits, rank
from tests.helpers import NOW, item, make_config


class RankTests(unittest.TestCase):
    def setUp(self):
        self.cfg = make_config()

    def test_corroborated_tier1_outranks_single_unlisted(self):
        items = [
            item("https://reuters.com/a", "Senators move on AI risk after researcher warning", "Reuters", tier="1", hours_old=20),
            item("https://nbcnews.com/a", "Senators from both parties move on AI risk after researcher's warning", "NBC News", tier="1", hours_old=18),
            item("https://randomblog.example/p", "My thoughts on gardening robots", "Random Blog", hours_old=2),
        ]
        stories = rank(cluster(items, [], self.cfg, NOW), self.cfg, NOW)
        self.assertEqual(stories[0].lead.outlet_name, "Reuters")
        self.assertGreater(stories[0].score, stories[-1].score)
        self.assertEqual(stories[0].score_parts["outlets"], 2)

    def test_on_ramp_hits_from_keywords(self):
        st = cluster([item("https://reuters.com/a", "Forty state AGs demand child protections in Character.AI sale",
                           "Reuters", tier="1")], [], self.cfg, NOW)[0]
        self.assertIn("child_safety", on_ramp_hits(st, self.cfg))
        gardening = cluster([item("https://reuters.com/b", "Gardening tips for autumn", "Reuters", tier="1")], [], self.cfg, NOW)[0]
        self.assertEqual(on_ramp_hits(gardening, self.cfg), [])

    def test_recency_decays(self):
        fresh = rank(cluster([item("https://reuters.com/a", "Fresh story about AI", "Reuters", tier="1", hours_old=1)], [], self.cfg, NOW), self.cfg, NOW)[0]
        stale = rank(cluster([item("https://reuters.com/b", "Stale story about AI", "Reuters", tier="1", hours_old=140)], [], self.cfg, NOW), self.cfg, NOW)[0]
        self.assertGreater(fresh.score_parts["recency"], stale.score_parts["recency"])
