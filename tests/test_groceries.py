import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.main import create_app

RECIPE = {
    "title": "Spinach rice", "servings": "4",
    "ingredients": ["1 kg spinach", "1/2 cup olive oil", "Salt"],
    "steps": ["Cook."],
}
OTHER = {"title": "Lentil soup", "servings": "2", "ingredients": ["1/2 cup olive oil", "200 g lentils"]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "morning-dust.db"))
    monkeypatch.setattr(settings, "import_json_todos", False)
    db.reset_for_tests()
    with TestClient(create_app()) as c:
        yield c
    db.reset_for_tests()


def _groceries(client):
    return [t for t in client.get("/api/todos").json()["items"] if t["list"] == "groceries"]


def test_todos_default_to_the_todo_list(client):
    todo = client.post("/api/todos", json={"text": "Water the plants"}).json()
    assert todo["list"] == "todo" and todo["source"] == ""
    item = client.post("/api/todos", json={"text": "Oat milk", "list": "groceries"}).json()
    assert item["list"] == "groceries"
    assert _groceries(client) == [item]


def test_recipe_to_groceries_adds_every_ingredient_line(client):
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]

    resp = client.post(f"/api/recipes/{rid}/groceries")

    assert resp.status_code == 201
    body = resp.json()
    assert [t["text"] for t in body["added"]] == RECIPE["ingredients"]
    assert body["skipped"] == 0 and body["source"] == "Spinach rice"
    assert all(t["list"] == "groceries" and t["source"] == "Spinach rice" for t in body["added"])
    assert [t["text"] for t in _groceries(client)] == RECIPE["ingredients"]


def test_recipe_to_groceries_scales_to_the_requested_servings(client):
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    body = client.post(f"/api/recipes/{rid}/groceries", json={"servings": 6}).json()
    assert [t["text"] for t in body["added"]] == ["1½ kg spinach", "¾ cup olive oil", "Salt"]


def test_adding_the_same_recipe_twice_skips_open_duplicates(client):
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    client.post(f"/api/recipes/{rid}/groceries")

    again = client.post(f"/api/recipes/{rid}/groceries").json()

    assert again["added"] == [] and again["skipped"] == 3
    assert len(_groceries(client)) == 3


def test_multiple_recipes_stack_on_one_list_with_their_source(client):
    a = client.post("/api/recipes", json=RECIPE).json()["id"]
    b = client.post("/api/recipes", json=OTHER).json()["id"]
    client.post(f"/api/recipes/{a}/groceries")
    second = client.post(f"/api/recipes/{b}/groceries").json()

    # identical open line "1/2 cup olive oil" is skipped, the lentils are added
    assert [t["text"] for t in second["added"]] == ["200 g lentils"]
    assert second["skipped"] == 1
    items = _groceries(client)
    assert {t["source"] for t in items} == {"Spinach rice", "Lentil soup"}
    assert len(items) == 4


def test_bought_items_can_be_cleared_and_re_added(client):
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    added = client.post(f"/api/recipes/{rid}/groceries").json()["added"]
    client.patch(f"/api/todos/{added[0]['id']}", json={"done": True})

    cleared = client.post("/api/todos/clear-done", params={"list": "groceries"}).json()

    assert cleared["removed"] == 1
    assert len(_groceries(client)) == 2
    # a ticked-off (now cleared) line is no longer "open", so it comes back
    assert [t["text"] for t in client.post(f"/api/recipes/{rid}/groceries").json()["added"]] == ["1 kg spinach"]


def test_clear_done_leaves_the_todo_list_alone(client):
    tid = client.post("/api/todos", json={"text": "Call the dentist", "done": True}).json()["id"]
    assert client.post("/api/todos/clear-done", params={"list": "groceries"}).json()["removed"] == 0
    assert client.get("/api/todos").json()["items"][0]["id"] == tid


def test_recipe_without_ingredients_is_422(client):
    rid = client.post("/api/recipes", json={"title": "Empty"}).json()["id"]
    assert client.post(f"/api/recipes/{rid}/groceries").status_code == 422
