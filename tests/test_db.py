import unittest

from socialbot.core.db import DB
from tests.helpers import make_config


class ApprovalRecordTests(unittest.TestCase):
    def test_record_and_read_back(self):
        cfg = make_config()
        db = DB(cfg["paths"]["data_dir"] / "t.sqlite")
        a = db.record_approval("roundup", "rd_1", "zach", "queue", note="from CLI")
        self.assertTrue(a.valid())
        self.assertEqual(db.approvals_for("rd_1")[0].approver, "zach")
        with self.assertRaises(ValueError):
            db.record_approval("roundup", "rd_1", "zach", "publish-everything")
        with self.assertRaises(ValueError):
            db.record_approval("roundup", "rd_1", "", "queue")
        db.close()
