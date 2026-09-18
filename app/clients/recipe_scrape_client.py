"""Fetches a recipe page's raw HTML for the recipe importer.

Recipe sites vary wildly in how picky they are — a default httpx client
without a browser-ish user agent gets 403'd by more than a few of them — so
this sends a normal-looking header set. It also caps how much it will read,
since a hostile or misbehaving URL could otherwise stream forever.
"""

import httpx

MAX_BYTES = 3_000_000  # ~3 MB is plenty for a recipe page's HTML

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; morning-dust-recipe-importer/1.0; "
        "+https://github.com/)"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


class RecipeFetchError(Exception):
    """The URL couldn't be fetched or didn't look like an HTML page."""


class RecipeScrapeClient:
    """Thin httpx wrapper: URL in, HTML text out."""

    def __init__(self, timeout_s: float = 10.0) -> None:
        self._timeout_s = timeout_s

    def fetch_html(self, url: str) -> str:
        try:
            with httpx.stream(
                "GET", url, headers=_HEADERS, timeout=self._timeout_s, follow_redirects=True
            ) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "html" not in content_type and content_type:
                    raise RecipeFetchError(f"Not an HTML page ({content_type})")
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > MAX_BYTES:
                        break
                body = b"".join(chunks)
        except httpx.HTTPError as exc:
            raise RecipeFetchError(str(exc)) from exc
        return body.decode(resp.encoding or "utf-8", errors="replace")
