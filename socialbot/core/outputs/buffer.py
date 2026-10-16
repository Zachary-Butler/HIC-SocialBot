"""Buffer's GraphQL API (https://api.buffer.com), used for exactly two things: listing channels
and creating posts. Creating a post requires a recorded human Approval; there is no code path
that publishes on a schedule.

Publish modes (config `buffer.publish_mode`):
  - will_approves: the post is created with needsApproval=true, so it lands in Buffer's Approvals
    tab for Will. Buffer treats it as a draft until he approves it there.
  - zach_approves: the post goes straight to the queue / next slot / now / a custom time, per the
    approval's action. Will gets the Zulip ping and can edit or pull it in Buffer before the slot.
"""

import os

import httpx

from ..approval import ACTIONS, Approval

ENDPOINT = "https://api.buffer.com"
SHARE_MODE = {"queue": "addToQueue", "next": "shareNext", "now": "shareNow", "schedule": "customScheduled"}
SOURCE = "hic-socialbot"

CHANNELS_QUERY = """
query GetChannels($input: ChannelsInput!) {
  channels(input: $input) { id name displayName service isQueuePaused }
}"""

CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status dueAt text channelId channelService } }
    ... on MutationError { message }
  }
}"""


class BufferError(Exception):
    pass


def image_asset(url: str, alt_text: str, thumbnail_url: str | None = None) -> dict:
    asset = {"image": {"url": url, "metadata": {"altText": alt_text}}}
    if thumbnail_url:
        asset["image"]["thumbnailUrl"] = thumbnail_url
    return asset


def document_asset(url: str, title: str, thumbnail_url: str) -> dict:
    """LinkedIn carousel = a PDF document post."""
    return {"document": {"url": url, "title": title, "thumbnailUrl": thumbnail_url}}


def instagram_metadata(first_comment: str | None = None, ai_generated: bool = False) -> dict:
    md = {"type": "post", "shouldShareToFeed": True, "isAiGenerated": ai_generated}
    if first_comment:
        md["firstComment"] = first_comment
    return {"instagram": md}


def facebook_metadata(first_comment: str | None = None) -> dict:
    md = {"type": "post"}
    if first_comment:
        md["firstComment"] = first_comment
    return {"facebook": md}


def linkedin_metadata(first_comment: str | None = None) -> dict:
    return {"linkedin": {"firstComment": first_comment}} if first_comment else {"linkedin": {}}


class Buffer:
    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None, endpoint: str = ENDPOINT):
        self.api_key = api_key or os.getenv("BUFFER_API_KEY") or ""
        self.endpoint = endpoint
        self.http = http or httpx.Client(timeout=30.0)

    def gql(self, query: str, variables: dict) -> dict:
        if not self.api_key:
            raise BufferError("BUFFER_API_KEY is missing from .env (create one at publish.buffer.com/settings/api)")
        try:
            r = self.http.post(self.endpoint, json={"query": query, "variables": variables},
                               headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        except httpx.HTTPError as e:
            raise BufferError(f"Couldn't reach Buffer: {type(e).__name__}")
        if r.status_code == 429:
            raise BufferError(f"Buffer rate limit hit; retry after {r.headers.get('Retry-After', '?')}s")
        if r.status_code == 401:
            raise BufferError("Buffer rejected the API key (401)")
        if r.status_code >= 400:
            raise BufferError(f"Buffer API error {r.status_code}: {r.text[:200]}")
        body = r.json()
        if body.get("errors"):
            raise BufferError("Buffer GraphQL error: " + "; ".join(e.get("message", "?") for e in body["errors"]))
        return body.get("data") or {}

    def channels(self, organization_id: str) -> list[dict]:
        return self.gql(CHANNELS_QUERY, {"input": {"organizationId": organization_id}}).get("channels") or []

    def create_post(self, approval: Approval, *, channel_id: str, text: str, assets: list[dict] | None = None,
                    metadata: dict | None = None, needs_approval: bool = False, due_at: str | None = None,
                    tag_ids: list[str] | None = None) -> dict:
        """The only way a post gets to Buffer. `approval` must be a recorded human decision."""
        if not isinstance(approval, Approval) or not approval.valid():
            raise BufferError("Refusing to create a Buffer post without a recorded human approval")
        action = approval.action
        if action not in ACTIONS:
            raise BufferError(f"Unknown approval action {action!r}")
        if action == "schedule" and not due_at:
            raise BufferError("A scheduled post needs due_at (ISO 8601 with timezone)")
        post_input = {
            "channelId": channel_id,
            "text": text,
            "mode": SHARE_MODE[action],
            "schedulingType": "automatic",
            "needsApproval": bool(needs_approval),
            "assets": list(assets or []),
            "aiAssisted": True,
            "source": SOURCE,
        }
        if action == "schedule":
            post_input["dueAt"] = due_at
        if metadata:
            post_input["metadata"] = metadata
        if tag_ids:
            post_input["tagIds"] = list(tag_ids)
        result = self.gql(CREATE_POST, {"input": post_input}).get("createPost") or {}
        if result.get("__typename") == "MutationError" or "post" not in result:
            raise BufferError(f"Buffer refused the post: {result.get('message', 'no post returned')}")
        return result["post"]
