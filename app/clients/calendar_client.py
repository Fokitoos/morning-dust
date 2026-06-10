import httpx


class CalendarClient:
    """Fetches raw iCal (.ics) feeds. No API key — uses Google Calendar's
    private 'secret address in iCal format' URL, which is itself the
    credential. Keep those URLs in .env, never commit them."""

    def __init__(self, timeout_s: float = 8.0) -> None:
        self._timeout_s = timeout_s

    def fetch_ics(self, url: str) -> str:
        resp = httpx.get(url, timeout=self._timeout_s, follow_redirects=True)
        resp.raise_for_status()
        return resp.text