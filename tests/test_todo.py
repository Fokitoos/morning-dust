from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.todo_service import TodoService, get_todo_service


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app()
    service = TodoService(tmp_path / "todos.json")
    app.dependency_overrides[get_todo_service] = lambda: service
    return TestClient(app)


def test_list_todos_empty(client: TestClient) -> None:
    resp = client.get("/api/todo")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


def test_create_then_list(client: TestClient) -> None:
    resp = client.post("/api/todo", json={"title": "buy milk"})
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] == 1
    assert created["title"] == "buy milk"
    assert created["done"] is False

    listed = client.get("/api/todo").json()["items"]
    assert listed == [created]


def test_toggle_done(client: TestClient) -> None:
    created = client.post("/api/todo", json={"title": "x"}).json()
    resp = client.patch(f"/api/todo/{created['id']}", json={"done": True})
    assert resp.status_code == 200
    assert resp.json()["done"] is True


def test_delete(client: TestClient) -> None:
    created = client.post("/api/todo", json={"title": "x"}).json()
    resp = client.delete(f"/api/todo/{created['id']}")
    assert resp.status_code == 204
    assert client.get("/api/todo").json() == {"items": []}


def test_update_missing_returns_404(client: TestClient) -> None:
    assert client.patch("/api/todo/999", json={"done": True}).status_code == 404


def test_delete_missing_returns_404(client: TestClient) -> None:
    assert client.delete("/api/todo/999").status_code == 404


def test_ids_are_sequential(client: TestClient) -> None:
    a = client.post("/api/todo", json={"title": "a"}).json()
    b = client.post("/api/todo", json={"title": "b"}).json()
    assert (a["id"], b["id"]) == (1, 2)
