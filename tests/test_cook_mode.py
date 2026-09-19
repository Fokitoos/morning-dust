import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.main import create_app
from app.services.cook_mode_service import find_timers


@pytest.mark.parametrize("text,expected", [
    ("Simmer for 20 minutes, stirring.", [("20 min", 1200)]),
    ("Bake at 350°F for 35-40 minutes.", [("35 min – 40 min", 2400)]),
    ("Knead 8–10 min until smooth.", [("8 min – 10 min", 600)]),
    ("Boil 5 min, then 10 to 15 minutes more.", [("5 min", 300), ("10 min – 15 min", 900)]),
    ("Let it rest 1 hour 30 minutes.", [("1 h 30 min", 5400)]),
    ("Cook 1½ hours, then rest for half an hour.", [("1 h 30 min", 5400), ("30 min", 1800)]),
    ("Rest an hour.", [("1 h", 3600)]),
    ("Whisk for 30 seconds.", [("30 s", 30)]),
    ("Preheat the oven to 200 degrees for 10 mins", [("10 min", 600)]),
])
def test_find_timers_reads_durations(text, expected):
    assert [(t.label, t.seconds) for t in find_timers(text)] == expected


@pytest.mark.parametrize("text", [
    "Add 2 medium onions and 200 g rice.",
    "Fry for a couple of minutes.",
    "Season with 1 tsp salt and 5 ml oil.",
    "Divide into 4 balls of 250 g.",
])
def test_find_timers_ignores_non_durations(text):
    assert find_timers(text) == []


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "morning-dust.db"))
    monkeypatch.setattr(settings, "import_json_todos", False)
    db.reset_for_tests()
    with TestClient(create_app()) as c:
        yield c
    db.reset_for_tests()


def test_cook_endpoint_annotates_steps_and_scales_ingredients(client):
    rid = client.post("/api/recipes", json={
        "title": "Rice", "servings": "4", "ingredients": ["2 cups rice", "Salt"],
        "steps": ["Rinse the rice.", "Simmer for 20 minutes."],
    }).json()["id"]

    plain = client.get(f"/api/recipes/{rid}/cook").json()
    assert plain["servings"] == 4 and plain["ingredients"] == ["2 cups rice", "Salt"]
    assert plain["steps"][0]["timers"] == []
    assert plain["steps"][1]["timers"][0]["seconds"] == 1200
    assert plain["steps"][1]["timers"][0]["phrase"] == "20 minutes"

    scaled = client.get(f"/api/recipes/{rid}/cook", params={"servings": 2}).json()
    assert scaled["servings"] == 2 and scaled["ingredients"] == ["1 cups rice", "Salt"]
