from fastapi.testclient import TestClient


def test_list_todos_empty(client: TestClient) -> None:
    resp = client.get("/api/todo")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


def test_create_todo(client: TestClient) -> None:
    payload = {"title": "buy milk"}
    resp = client.post("/api/todo", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "buy milk"
    assert body["done"] is False
