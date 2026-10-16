import unittest

from socialbot.core.llm import LLM, LLMError
from tests.fakes import FakeClaude
from tests.helpers import make_config

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}


class LLMTests(unittest.TestCase):
    def setUp(self):
        self.cfg = make_config()

    def test_structured_request_shape_and_cost(self):
        fake = FakeClaude({"ok": True}, input_tokens=10_000, output_tokens=1_000)
        llm = LLM(self.cfg, client=fake)
        out = llm.json_call("t", "claude-sonnet-5-5", "SYS", "USER", SCHEMA)
        self.assertEqual(out, {"ok": True})
        req = fake.requests[0]
        self.assertEqual(req["output_config"]["format"], {"type": "json_schema", "schema": SCHEMA})
        self.assertEqual(req["output_config"]["effort"], self.cfg["llm"]["effort"])
        self.assertEqual(req["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("thinking", req)                      # adaptive thinking is the model default
        # 10k in @ $2 + 1k out @ $10 per MTok
        self.assertAlmostEqual(llm.spent, 0.02 + 0.01, places=6)

    def test_cache_reads_priced_separately(self):
        fake = FakeClaude({"ok": True}, input_tokens=1_000, output_tokens=0, cache_read=10_000)
        llm = LLM(self.cfg, client=fake)
        llm.json_call("t", "claude-opus-5-5", "SYS", "USER", SCHEMA)
        self.assertAlmostEqual(llm.spent, 1_000 * 4 / 1e6 + 10_000 * 0.20 / 1e6, places=8)

    def test_reuse_replays_without_calling(self):
        fake = FakeClaude({"ok": True})
        LLM(self.cfg, client=fake).json_call("t", "claude-sonnet-5-5", "SYS", "USER", SCHEMA)
        again = LLM(self.cfg, reuse=True, client=None)        # no client: any call would crash
        self.assertEqual(again.json_call("t", "claude-sonnet-5-5", "SYS", "USER", SCHEMA), {"ok": True})
        self.assertTrue(again.calls[0].reused)
        self.assertEqual(again.spent, 0)
        with self.assertRaises(LLMError):
            again.json_call("t", "claude-sonnet-5-5", "SYS", "DIFFERENT", SCHEMA)

    def test_budget_stops_calls(self):
        self.cfg["llm"]["max_cost_per_run_usd"] = 0.001
        fake = FakeClaude({"ok": True}, input_tokens=1_000_000)
        llm = LLM(self.cfg, client=fake)
        llm.json_call("t", "claude-sonnet-5-5", "SYS", "A", SCHEMA)
        with self.assertRaises(LLMError):
            llm.json_call("t", "claude-sonnet-5-5", "SYS", "B", SCHEMA)
        self.assertEqual(len(fake.requests), 1)

    def test_refusal_retries_on_fallback_model_then_raises(self):
        self.cfg["llm"]["fallback_model"] = "claude-sonnet-5-5"
        fake = FakeClaude({"__stop__": "refusal", "ok": False}, {"ok": True})
        llm = LLM(self.cfg, client=fake)
        out = llm.json_call("t", "claude-opus-5-5", "SYS", "USER", SCHEMA)
        self.assertEqual(out, {"ok": True})
        self.assertEqual([r["model"] for r in fake.requests], ["claude-opus-5-5", "claude-sonnet-5-5"])
        self.assertEqual(llm.calls[-1].fell_back_from, "claude-opus-5-5")

        fake2 = FakeClaude({"__stop__": "refusal", "ok": False}, {"__stop__": "refusal", "ok": False})
        with self.assertRaises(LLMError):
            LLM(self.cfg, client=fake2).json_call("t", "claude-opus-5-5", "SYS", "USER", SCHEMA)

    def test_cut_off_answer_is_an_error(self):
        fake = FakeClaude({"ok": True}, stop_reason="max_tokens")
        with self.assertRaises(LLMError):
            LLM(self.cfg, client=fake).json_call("t", "claude-sonnet-5-5", "SYS", "USER", SCHEMA)
