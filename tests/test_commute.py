from fastapi.testclient import TestClient


def test_get_commute(client: TestClient) -> None:
    resp = client.get("/api/commute")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"origin", "destination", "duration_minutes", "traffic"}
