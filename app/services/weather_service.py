from fastapi import Depends

from app.clients.weather_client import WeatherClient
from app.config import settings
from app.schemas.weather import WeatherResponse

# WMO weather code → human label. https://open-meteo.com/en/docs
_WMO_CODES: dict[int, str] = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light rain showers",
    81: "rain showers",
    82: "violent rain showers",
    85: "light snow showers",
    86: "snow showers",
    95: "thunderstorm",
    96: "thunderstorm with light hail",
    99: "thunderstorm with hail",
}


def _describe(code: int) -> str:
    return _WMO_CODES.get(code, "unknown")


def _first(values: list | None) -> float | None:
    if not values:
        return None
    return float(values[0])


class WeatherService:
    def __init__(self, client: WeatherClient) -> None:
        self._client = client

    def get_current(self) -> WeatherResponse:
        data = self._client.fetch_current(settings.weather_lat, settings.weather_lon)
        current = data.get("current", {})
        daily = data.get("daily", {})
        return WeatherResponse(
            location=settings.weather_location_name,
            temperature_c=float(current.get("temperature_2m", 0.0)),
            temperature_min_c=_first(daily.get("temperature_2m_min")),
            temperature_max_c=_first(daily.get("temperature_2m_max")),
            condition=_describe(int(current.get("weather_code", -1))),
        )


def get_weather_client() -> WeatherClient:
    return WeatherClient(timeout_s=settings.weather_timeout_s)


def get_weather_service(
    client: WeatherClient = Depends(get_weather_client),
) -> WeatherService:
    return WeatherService(client)
