import httpx

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherClient:
    """Open-Meteo client. No API key required."""

    def __init__(self, timeout_s: float = 5.0) -> None:
        self._timeout_s = timeout_s

    def fetch_current(self, lat: float, lon: float) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
            "forecast_days": 1,
            "timezone": "auto",
        }
        # NOTE! open metro updates their value every 15 minutes
        # a cache might be a good idea in the future
        resp = httpx.get(OPEN_METEO_URL, params=params, timeout=self._timeout_s)
        resp.raise_for_status()
        return resp.json()
