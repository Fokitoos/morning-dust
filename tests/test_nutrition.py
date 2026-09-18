import pytest
from fastapi.testclient import TestClient

from app import db
from app.clients.nutrition_client import NutritionClient, NutritionClientError
from app.config import settings
from app.main import create_app
from app.schemas.nutrition import MicronutrientEstimate, NutritionEstimate
from app.services.nutrition_service import RDA, get_nutrition_client, to_nutrition_info

ESTIMATE = NutritionEstimate(
    calories_kcal=412.4, protein_g=9.26, carbs_g=48.1, fat_g=19.9, fiber_g=7.2,
    micronutrients=MicronutrientEstimate(
        iron_mg=4.5, vitamin_b12_ug=0, calcium_mg=250, zinc_mg=1.1, iodine_ug=15,
        vitamin_d_ug=0, omega3_ala_g=0.4, folate_ug=200, magnesium_mg=120, selenium_ug=5,
    ),
    assumptions="Assumed a medium onion.", confidence="medium",
)

RECIPE = {
    "title": "Spinach rice", "servings": "4", "time": "35 min",
    "ingredients": ["1 kg spinach", "1 cup rice", "1/2 cup olive oil"],
    "steps": ["Cook it."],
}


class FakeNutritionClient(NutritionClient):
    def __init__(self, estimate=ESTIMATE, error=None, configured=True):
        super().__init__(api_key="fake" if configured else None)
        self._estimate, self._error = estimate, error
        self.calls: list[tuple[str, int, list[str]]] = []

    def estimate(self, title, servings, ingredients):
        self.calls.append((title, servings, ingredients))
        if self._error:
            raise NutritionClientError(self._error)
        return self._estimate


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "morning-dust.db"))
    monkeypatch.setattr(settings, "import_json_todos", False)
    db.reset_for_tests()
    yield create_app()
    db.reset_for_tests()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_to_nutrition_info_computes_rda_percentages():
    info = to_nutrition_info(ESTIMATE, servings=4)
    assert info.calories_kcal == 412
    assert info.protein_g == 9.3
    by_key = {m.key: m for m in info.micronutrients}
    assert set(by_key) == set(RDA)
    assert by_key["iron_mg"].rda_pct == 25  # 4.5 / 18
    assert by_key["calcium_mg"].rda_pct == 25
    assert by_key["vitamin_b12_ug"].rda_pct == 0
    assert by_key["folate_ug"].unit == "µg"
    assert info.servings == 4 and info.rda_basis


def test_estimate_endpoint_stores_nutrition_on_the_recipe(app, client):
    fake = FakeNutritionClient()
    app.dependency_overrides[get_nutrition_client] = lambda: fake
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]

    resp = client.post(f"/api/recipes/{rid}/nutrition")

    assert resp.status_code == 200
    nut = resp.json()["nutrition"]
    assert nut["calories_kcal"] == 412
    assert nut["micronutrients"][0]["label"] == "Iron"
    assert fake.calls == [("Spinach rice", 4, RECIPE["ingredients"])]
    # persisted: shows up on the list too
    assert client.get("/api/recipes").json()["items"][0]["nutrition"]["fat_g"] == 19.9


def test_estimate_endpoint_without_api_key_is_503(app, client):
    app.dependency_overrides[get_nutrition_client] = lambda: FakeNutritionClient(configured=False)
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    resp = client.post(f"/api/recipes/{rid}/nutrition")
    assert resp.status_code == 503
    assert "MORNING_DUST_ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_estimate_endpoint_reports_model_failure(app, client):
    app.dependency_overrides[get_nutrition_client] = lambda: FakeNutritionClient(error="rate limited")
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    resp = client.post(f"/api/recipes/{rid}/nutrition")
    assert resp.status_code == 502
    assert "rate limited" in resp.json()["detail"]


def test_estimate_persists_across_edits_until_re_estimated(app, client):
    fake = FakeNutritionClient()
    app.dependency_overrides[get_nutrition_client] = lambda: fake
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    client.post(f"/api/recipes/{rid}/nutrition")

    edited = client.put(f"/api/recipes/{rid}", json={**RECIPE, "ingredients": ["2 kg spinach"]}).json()
    assert edited["nutrition"]["calories_kcal"] == 412
    assert client.get("/api/recipes").json()["items"][0]["nutrition"] is not None
    assert len(fake.calls) == 1  # opening/editing never re-runs the model


def test_scaled_endpoint(client):
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    resp = client.get(f"/api/recipes/{rid}/scaled", params={"servings": 6})
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_servings"] == 4 and body["factor"] == 1.5
    assert [i["text"] for i in body["ingredients"]] == ["1½ kg spinach", "1½ cup rice", "¾ cup olive oil"]


def test_scaled_endpoint_without_servings_is_422(client):
    rid = client.post("/api/recipes", json={**RECIPE, "servings": ""}).json()["id"]
    assert client.get(f"/api/recipes/{rid}/scaled", params={"servings": 2}).status_code == 422
