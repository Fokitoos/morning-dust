from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    # Real get_todo_service, but persistence redirected to a temp dir.
    monkeypatch.setattr(settings, "todo_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "todo_lists", ["groceries", "tasks"], raising=False)
    return TestClient(create_app())


def test_list_todos_empty(client: TestClient) -> None:
    resp = client.get("/api/todo/groceries")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


def test_create_then_list(client: TestClient) -> None:
    resp = client.post("/api/todo/groceries", json={"title": "buy milk"})
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] == 1
    assert created["title"] == "buy milk"
    assert created["done"] is False

    listed = client.get("/api/todo/groceries").json()["items"]
    assert listed == [created]


def test_toggle_done(client: TestClient) -> None:
    created = client.post("/api/todo/groceries", json={"title": "x"}).json()
    resp = client.patch(f"/api/todo/groceries/{created['id']}", json={"done": True})
    assert resp.status_code == 200
    assert resp.json()["done"] is True


def test_delete(client: TestClient) -> None:
    created = client.post("/api/todo/groceries", json={"title": "x"}).json()
    resp = client.delete(f"/api/todo/groceries/{created['id']}")
    assert resp.status_code == 204
    assert client.get("/api/todo/groceries").json() == {"items": []}


def test_update_missing_returns_404(client: TestClient) -> None:
    assert client.patch("/api/todo/groceries/999", json={"done": True}).status_code == 404


def test_delete_missing_returns_404(client: TestClient) -> None:
    assert client.delete("/api/todo/groceries/999").status_code == 404


def test_ids_are_sequential(client: TestClient) -> None:
    a = client.post("/api/todo/groceries", json={"title": "a"}).json()
    b = client.post("/api/todo/groceries", json={"title": "b"}).json()
    assert (a["id"], b["id"]) == (1, 2)


def test_unknown_list_returns_404(client: TestClient) -> None:
    assert client.get("/api/todo/nope").status_code == 404
    assert client.post("/api/todo/nope", json={"title": "x"}).status_code == 404


def test_lists_are_independent(client: TestClient) -> None:
    client.post("/api/todo/groceries", json={"title": "milk"})
    assert client.get("/api/todo/tasks").json() == {"items": []}

    client.post("/api/todo/tasks", json={"title": "call plumber"})
    groceries = [i["title"] for i in client.get("/api/todo/groceries").json()["items"]]
    tasks = [i["title"] for i in client.get("/api/todo/tasks").json()["items"]]
    assert groceries == ["milk"]
    assert tasks == ["call plumber"]
