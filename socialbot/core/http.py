"""One HTTP client for everything we fetch. Identifies us honestly and never retries forever.

Note: this is the `httpx` package for our own fetching. The Anthropic SDK (1.x) is built on
`httpx2`; never hand it an object from here."""

import httpx

USER_AGENT = ("HIC-SocialBot/0.1 (news monitoring for Humans in Control; "
              "+https://humansincontrol.org; comms@humansincontrol.org)")


def client(timeout: float = 20.0) -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                        timeout=timeout, follow_redirects=True)
