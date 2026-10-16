"""HTTP clients for everything we fetch.

- `client()` identifies us honestly; use it for feeds and APIs.
- `browser_client()` sends ordinary browser headers; use it to read article pages, many of which
  return a 401/403 to anything that doesn't look like a browser. We only read pages we are about
  to link to, once, and cache the text.

Note: this is the `httpx` package for our own fetching. The Anthropic SDK (1.x) is built on
`httpx2`; never hand it an object from here."""

import httpx

USER_AGENT = ("HIC-SocialBot/0.1 (news monitoring for Humans in Control; "
              "+https://humansincontrol.org; comms@humansincontrol.org)")
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0.0.0 Safari/537.36")


def client(timeout: float = 20.0) -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                        timeout=timeout, follow_redirects=True)


def browser_client(timeout: float = 25.0) -> httpx.Client:
    return httpx.Client(headers={
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }, timeout=timeout, follow_redirects=True, http2=False)
