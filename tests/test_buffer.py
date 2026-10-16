import json
import unittest

import httpx

from socialbot.core.approval import Approval
from socialbot.core.outputs.buffer import Buffer, BufferError, image_asset, instagram_metadata

APPROVED = Approval(id=7, kind="roundup", target_id="rd_1", approver="zach", action="queue", at="2026-10-16T20:00:00+00:00")
NOT_RECORDED = Approval(id=0, kind="roundup", target_id="rd_1", approver="zach", action="queue", at="")


class FakeBuffer:
    """Mock transport for api.buffer.com: records requests, returns canned GraphQL bodies."""

    def __init__(self, response: dict | None = None, status: int = 200, headers: dict | None = None):
        self.requests: list[dict] = []
        self.response = response if response is not None else {
            "data": {"createPost": {"__typename": "PostActionSuccess",
                                    "post": {"id": "p1", "status": "buffer", "dueAt": None, "text": "t",
                                             "channelId": "c1", "channelService": "instagram"}}}}
        self.status, self.headers = status, headers or {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append({"headers": dict(request.headers), "body": json.loads(request.content)})
        return httpx.Response(self.status, json=self.response, headers=self.headers)

    def client(self) -> Buffer:
        return Buffer(api_key="key123", http=httpx.Client(transport=httpx.MockTransport(self.handler)))


class BufferTests(unittest.TestCase):
    def test_no_post_without_recorded_approval(self):
        fake = FakeBuffer()
        for bad in (None, NOT_RECORDED, "zach said yes"):
            with self.assertRaises(BufferError):
                fake.client().create_post(bad, channel_id="c1", text="t")
        self.assertEqual(fake.requests, [])                      # nothing left the building

    def test_queue_post_shape(self):
        fake = FakeBuffer()
        post = fake.client().create_post(APPROVED, channel_id="c1", text="Hello",
                                         assets=[image_asset("https://cdn/x.png", "alt")],
                                         metadata=instagram_metadata(first_comment="Sources: ..."))
        self.assertEqual(post["id"], "p1")
        req = fake.requests[0]
        self.assertEqual(req["headers"]["authorization"], "Bearer key123")
        inp = req["body"]["variables"]["input"]
        self.assertEqual(inp["mode"], "addToQueue")
        self.assertEqual(inp["schedulingType"], "automatic")
        self.assertFalse(inp["needsApproval"])
        self.assertTrue(inp["aiAssisted"])
        self.assertEqual(inp["assets"][0]["image"]["metadata"]["altText"], "alt")
        self.assertEqual(inp["metadata"]["instagram"]["type"], "post")
        self.assertFalse(inp["metadata"]["instagram"]["isAiGenerated"])
        self.assertIn("mutation CreatePost", req["body"]["query"])

    def test_will_approves_mode_sets_needs_approval(self):
        fake = FakeBuffer()
        fake.client().create_post(APPROVED, channel_id="c1", text="t", needs_approval=True)
        self.assertTrue(fake.requests[0]["body"]["variables"]["input"]["needsApproval"])

    def test_actions_map_to_share_modes(self):
        for action, mode in (("now", "shareNow"), ("next", "shareNext")):
            fake = FakeBuffer()
            a = Approval(id=1, kind="alert", target_id="s", approver="zach", action=action, at="x")
            fake.client().create_post(a, channel_id="c1", text="t")
            self.assertEqual(fake.requests[0]["body"]["variables"]["input"]["mode"], mode)
        sched = Approval(id=1, kind="alert", target_id="s", approver="zach", action="schedule", at="x")
        with self.assertRaises(BufferError):
            FakeBuffer().client().create_post(sched, channel_id="c1", text="t")        # no due_at
        fake = FakeBuffer()
        fake.client().create_post(sched, channel_id="c1", text="t", due_at="2026-10-19T16:00:00+00:00")
        inp = fake.requests[0]["body"]["variables"]["input"]
        self.assertEqual((inp["mode"], inp["dueAt"]), ("customScheduled", "2026-10-19T16:00:00+00:00"))

    def test_errors_surface(self):
        with self.assertRaises(BufferError) as cm:
            FakeBuffer({"data": {"createPost": {"__typename": "MutationError", "message": "Channel is locked"}}}).client() \
                .create_post(APPROVED, channel_id="c1", text="t")
        self.assertIn("Channel is locked", str(cm.exception))
        with self.assertRaises(BufferError) as cm:
            FakeBuffer({}, status=429, headers={"Retry-After": "42"}).client().create_post(APPROVED, channel_id="c1", text="t")
        self.assertIn("42", str(cm.exception))
        with self.assertRaises(BufferError):
            Buffer(api_key="").create_post(APPROVED, channel_id="c1", text="t")

    def test_channels_query(self):
        fake = FakeBuffer({"data": {"channels": [{"id": "c1", "name": "hic", "service": "instagram"}]}})
        self.assertEqual(fake.client().channels("org1")[0]["service"], "instagram")
        self.assertEqual(fake.requests[0]["body"]["variables"], {"input": {"organizationId": "org1"}})
