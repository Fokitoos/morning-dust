from fastapi.testclient import TestClient


def test_get_weather(client: TestClient) -> None:
    resp = client.get("/api/weather")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"location", "temperature_c", "condition"}
