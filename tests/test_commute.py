from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.clients.commute_client import CommuteClient
from app.config import settings
from app.main import create_app
from app.services.commute_scheduler import _seconds_until_next
from app.services.commute_service import CommuteService, get_commute_service


class FakeCommuteClient(CommuteClient):
    def __init__(self, payload: dict | None = None, raise_exc: Exception | None = None) -> None:
        self._payload = payload
        self._raise = raise_exc
        self.calls = 0

    def fetch_route(self, origin_lat, origin_lon, dest_lat, dest_lon):
        self.calls += 1
        if self._raise:
            raise self._raise
        return self._payload or {}


def _tomtom_payload(live_s: int, typical_s: int, distance_m: int) -> dict:
    return {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": distance_m,
                    "travelTimeInSeconds": live_s,
                    "noTrafficTravelTimeInSeconds": typical_s,
                    "trafficDelayInSeconds": live_s - typical_s,
                }
            }
        ]
    }


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "commute_origin_lat", 52.02, raising=False)
    monkeypatch.setattr(settings, "commute_origin_lon", 5.07, raising=False)
    monkeypatch.setattr(settings, "commute_destination_lat", 52.37, raising=False)
    monkeypatch.setattr(settings, "commute_destination_lon", 4.90, raising=False)
    monkeypatch.setattr(settings, "tomtom_api_key", "test-key", raising=False)


@pytest.fixture
def fake_client() -> FakeCommuteClient:
    return FakeCommuteClient(payload=_tomtom_payload(2400, 1800, 35000))


@pytest.fixture
def service(fake_client: FakeCommuteClient) -> CommuteService:
    return CommuteService(client_factory=lambda: fake_client)


@pytest.fixture
def client(service: CommuteService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_commute_service] = lambda: service
    return TestClient(app)


def test_get_commute_returns_stale_before_first_refresh(client: TestClient) -> None:
    body = client.get("/api/commute").json()
    assert body["status"] == "stale"
    assert body["duration_minutes"] is None


def test_refresh_maps_tomtom_summary(client: TestClient, fake_client: FakeCommuteClient) -> None:
    body = client.post("/api/commute/refresh").json()
    assert body["status"] == "ok"
    assert body["duration_minutes"] == 40
    assert body["typical_duration_minutes"] == 30
    assert body["traffic_delay_minutes"] == 10
    assert body["distance_km"] == 35.0
    assert fake_client.calls == 1


def test_get_uses_cache(client: TestClient, fake_client: FakeCommuteClient) -> None:
    client.post("/api/commute/refresh")
    client.get("/api/commute")
    assert fake_client.calls == 1


def test_refresh_error_keeps_previous_data(client: TestClient) -> None:
    ok = client.post("/api/commute/refresh").json()
    assert ok["status"] == "ok"

    # swap the factory to fail
    failing = FakeCommuteClient(raise_exc=RuntimeError("boom"))
    app = client.app
    failing_service = CommuteService(client_factory=lambda: failing)
    failing_service._last = app.dependency_overrides[get_commute_service]()._last  # type: ignore[attr-defined]
    app.dependency_overrides[get_commute_service] = lambda: failing_service

    err = client.post("/api/commute/refresh").json()
    assert err["status"] == "error"
    assert err["duration_minutes"] == 40  # previous value retained


def test_no_api_key_short_circuits(monkeypatch, fake_client: FakeCommuteClient) -> None:
    monkeypatch.setattr(settings, "tomtom_api_key", None, raising=False)
    service = CommuteService(client_factory=lambda: fake_client)
    app = create_app()
    app.dependency_overrides[get_commute_service] = lambda: service
    with TestClient(app) as c:
        body = c.post("/api/commute/refresh").json()
    assert body["status"] == "no_api_key"
    assert fake_client.calls == 0


def test_coords_unset_short_circuits(monkeypatch, fake_client: FakeCommuteClient) -> None:
    monkeypatch.setattr(settings, "commute_origin_lat", None, raising=False)
    service = CommuteService(client_factory=lambda: fake_client)
    app = create_app()
    app.dependency_overrides[get_commute_service] = lambda: service
    with TestClient(app) as c:
        body = c.post("/api/commute/refresh").json()
    assert body["status"] == "not_configured"
    assert fake_client.calls == 0


def test_seconds_until_next_future_today() -> None:
    now = datetime(2026, 5, 25, 6, 30, 0)
    assert _seconds_until_next(7, now=now) == 30 * 60


def test_seconds_until_next_wraps_to_tomorrow() -> None:
    now = datetime(2026, 5, 25, 8, 0, 0)
    assert _seconds_until_next(7, now=now) == 23 * 3600
