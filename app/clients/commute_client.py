import httpx

TOMTOM_BASE_URL = "https://api.tomtom.com/routing/1/calculateRoute"


class CommuteClient:
    """TomTom Routing API client. Requires a free API key.

    Returns live-traffic ETA plus the typical (no-traffic) duration so the
    UI can show the delta. Free tier is 2,500 requests/day — plenty for a
    daily-refresh dashboard.
    """

    def __init__(self, api_key: str, profile: str = "car", timeout_s: float = 10.0) -> None:
        self._api_key = api_key
        self._profile = profile
        self._timeout_s = timeout_s

    def fetch_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> dict:
        coords = f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}"
        url = f"{TOMTOM_BASE_URL}/{coords}/json"
        params = {
            "key": self._api_key,
            "traffic": "true",
            "travelMode": self._profile,
            "computeTravelTimeFor": "all",  # returns noTraffic + historic + live times
        }
        resp = httpx.get(url, params=params, timeout=self._timeout_s)
        resp.raise_for_status()
        return resp.json()
