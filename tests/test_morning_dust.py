import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "morning-dust.db"))
    monkeypatch.setattr(settings, "import_json_todos", False)
    monkeypatch.setattr(settings, "calendar_ics_urls", [])
    db.reset_for_tests()
    with TestClient(create_app()) as c:
        yield c
    db.reset_for_tests()


def test_todo_round_trip(client):
    created = client.post("/api/todos", json={"text": "Water the plants", "due": "2026-07-26"})
    assert created.status_code == 201
    todo_id = created.json()["id"]

    assert client.get("/api/todos").json()["items"][0]["text"] == "Water the plants"

    patched = client.patch(f"/api/todos/{todo_id}", json={"done": True})
    assert patched.json()["done"] is True

    assert client.delete(f"/api/todos/{todo_id}").status_code == 204
    assert client.get("/api/todos").json()["items"] == []


def test_todo_requires_text(client):
    assert client.post("/api/todos", json={"text": "   "}).status_code == 422


def test_local_events_are_writable_and_feed_events_are_not(client):
    created = client.post(
        "/api/calendar/events", json={"title": "Yoga class", "date": "2026-07-26", "time": "18:30"}
    )
    assert created.status_code == 201
    event = created.json()
    assert event["id"].startswith("local:")
    assert event["source"] == "local"

    listed = client.get("/api/calendar/events", params={"start": "2026-07-20", "end": "2026-08-02"})
    assert listed.json()["status"] == "local_only"
    assert [e["title"] for e in listed.json()["events"]] == ["Yoga class"]

    # Outside the window.
    assert client.get(
        "/api/calendar/events", params={"start": "2026-09-01", "end": "2026-09-30"}
    ).json()["events"] == []

    assert client.delete("/api/calendar/events/ics:abc123").status_code == 409
    assert client.delete(f"/api/calendar/events/{event['id']}").status_code == 204


def test_bulk_import_skips_duplicates(client):
    payload = {
        "events": [
            {"title": "Pediatrician", "date": "2026-07-28", "time": "10:00"},
            {"title": "Pediatrician", "date": "2026-07-28", "time": "10:00"},
        ]
    }
    first = client.post("/api/calendar/events/bulk", json=payload).json()
    assert (first["imported"], first["skipped"]) == (1, 1)

    again = client.post("/api/calendar/events/bulk", json=payload).json()
    assert again["imported"] == 0


def test_recipe_round_trip(client):
    created = client.post(
        "/api/recipes",
        json={
            "title": "Weeknight lemon pasta",
            "tags": ["dinner", "quick"],
            "ingredients": ["200 g spaghetti", "1 lemon"],
            "steps": ["Boil", "Toss"],
            "notes": "Double the zest.",
        },
    ).json()
    assert created["tags"] == ["dinner", "quick"]

    replaced = client.put(
        f"/api/recipes/{created['id']}",
        json={"title": "Lemon pasta", "ingredients": ["200 g spaghetti"], "steps": ["Boil"]},
    ).json()
    assert replaced["title"] == "Lemon pasta"
    assert replaced["tags"] == []

    assert client.delete(f"/api/recipes/{created['id']}").status_code == 204
    assert client.put("/api/recipes/999", json={"title": "Nope"}).status_code == 404


def test_notes_track_update_time(client):
    note = client.post("/api/notes", json={"text": "Move the rosemary"}).json()
    patched = client.patch(f"/api/notes/{note['id']}", json={"text": "Move the rosemary today"}).json()
    assert patched["text"] == "Move the rosemary today"
    assert patched["updated"] >= note["updated"]


def test_weights_are_sorted_and_range_checked(client):
    client.post("/api/weights", json={"date": "2026-07-20", "grams": 3450})
    client.post("/api/weights", json={"date": "2026-07-14", "grams": 3380})
    dates = [w["date"] for w in client.get("/api/weights").json()["items"]]
    assert dates == ["2026-07-14", "2026-07-20"]

    assert client.post("/api/weights", json={"date": "2026-07-21", "grams": 12}).status_code == 422
