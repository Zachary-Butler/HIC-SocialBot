"""URL hygiene shared by both lanes: canonical forms and outlet-domain matching."""

from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

import tldextract

# Offline: use the suffix list bundled with the package, never fetch it at runtime.
_extract = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ncid", "cmpid", "smid",
                      "partner", "ocid", "ito", "guccounter", "guce_referrer", "_hs", "mkt_tok", "taid")
_AGGREGATOR_HOSTS = {"news.google.com", "bing.com"}


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _host_of(url_or_host: str) -> str:
    return host(url_or_host) if "://" in url_or_host else url_or_host.lower().removeprefix("www.")


def registrable_domain(url_or_host: str) -> str:
    """'feeds.bbci.co.uk' -> 'bbc.co.uk'; 'https://www.nytimes.com/x' -> 'nytimes.com'."""
    h = _host_of(url_or_host)
    ext = _extract(h)
    return ext.top_domain_under_public_suffix or h   # unknown suffix (e.g. .example): keep the host


def canonical(url: str) -> str:
    """Strip tracking params, fragments, AMP suffixes and trailing slashes so the same article
    from two feeds compares equal."""
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme
    netloc = (parts.hostname or "").lower().removeprefix("www.")
    if parts.port and parts.port not in (80, 443):
        netloc += f":{parts.port}"
    path = parts.path or "/"
    for amp in ("/amp/", "/amp"):
        if path.endswith(amp) and len(path) > len(amp):
            path = path[: -len(amp)] + ("/" if amp.endswith("/") else "")
    path = path.rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(_TRACKING_PREFIXES)]
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def is_aggregator(url: str) -> bool:
    return host(url) in _AGGREGATOR_HOSTS


def unwrap_bing(url: str) -> str:
    """Bing News RSS links are apiclick.aspx redirects carrying the real URL in ?url=."""
    if host(url) == "bing.com":
        target = parse_qs(urlsplit(url).query).get("url")
        if target:
            return target[0]
    return url


def match_outlet(url_or_host: str, by_domain: dict) -> dict | None:
    """Exact host first (so 'importai.substack.com' beats 'substack.com'), then the registrable domain."""
    h = _host_of(url_or_host)
    if h in by_domain:
        return by_domain[h]
    return by_domain.get(registrable_domain(h))
