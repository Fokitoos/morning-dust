from fastapi.testclient import TestClient

from app.clients.weather_client import WeatherClient
from app.main import create_app
from app.services.weather_service import get_weather_client


class FakeWeatherClient(WeatherClient):
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def fetch_current(self, lat: float, lon: float) -> dict:
        return self._payload


def _client_with_payload(payload: dict) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_weather_client] = lambda: FakeWeatherClient(payload)
    return TestClient(app)


def test_get_weather_maps_open_meteo_response() -> None:
    payload = {
        "current": {"temperature_2m": 21.3, "weather_code": 2},
        "daily": {
            "time": ["2026-05-25"],
            "temperature_2m_max": [24.7],
            "temperature_2m_min": [14.2],
        },
    }
    client = _client_with_payload(payload)

    resp = client.get("/api/weather")

    assert resp.status_code == 200
    body = resp.json()
    assert body["temperature_c"] == 21.3
    assert body["temperature_max_c"] == 24.7
    assert body["temperature_min_c"] == 14.2
    assert body["condition"] == "partly cloudy"
    assert body["location"]


def test_get_weather_unknown_code_falls_back() -> None:
    payload = {"current": {"temperature_2m": 10.0, "weather_code": 1234}}
    client = _client_with_payload(payload)

    resp = client.get("/api/weather")

    assert resp.status_code == 200
    assert resp.json()["condition"] == "unknown"


def test_get_weather_missing_daily_returns_none() -> None:
    payload = {"current": {"temperature_2m": 18.0, "weather_code": 0}}
    client = _client_with_payload(payload)

    resp = client.get("/api/weather")

    body = resp.json()
    assert body["temperature_min_c"] is None
    assert body["temperature_max_c"] is None
