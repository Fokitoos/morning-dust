import pytest
from fastapi.testclient import TestClient

from app import db
from app.clients.recipe_scrape_client import RecipeFetchError, RecipeScrapeClient
from app.config import settings
from app.main import create_app
from app.schemas.recipe_import import RecipeImportRequest
from app.services.recipe_import_service import (
    RecipeImportService,
    _parse_free_text,
    strip_html,
)
from app.services.recipe_import_service import get_recipe_scrape_client

LD_JSON_PAGE = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Weeknight Lemon Pasta",
  "image": ["https://example.com/lemon-pasta.jpg"],
  "recipeYield": "4 servings",
  "totalTime": "PT25M",
  "recipeIngredient": ["200 g spaghetti", "1 lemon, zested and juiced", "50 g parmesan"],
  "recipeInstructions": [
    {"@type": "HowToStep", "text": "Boil the pasta until al dente."},
    {"@type": "HowToStep", "text": "Toss with lemon, butter and parmesan."}
  ],
  "keywords": "pasta, quick, weeknight",
  "description": "A fast, bright pasta for a busy evening."
}
</script>
</head><body>ignored body text</body></html>
"""

GRAPH_PAGE = """
<html><head>
<script type="application/ld+json">
{"@graph": [
  {"@type": "WebPage", "name": "not this one"},
  {"@type": ["Recipe"], "name": "Graph Wrapped Soup",
   "recipeIngredient": ["1 onion", "2 carrots"],
   "recipeInstructions": "Chop everything.\\nSimmer for 20 minutes."}
]}
</script>
</head><body></body></html>
"""

NO_STRUCTURED_DATA_PAGE = """
<html><body>
<h1>Grandma's Cookies</h1>
<p>Ingredients</p>
<ul><li>2 cups flour</li><li>1 cup sugar</li></ul>
<p>Instructions</p>
<ol><li>Mix everything.</li><li>Bake at 350F for 12 minutes.</li></ol>
</body></html>
"""

PASTED_TEXT = """Sheet Pan Chicken

Ingredients
- 4 chicken thighs
- 2 tbsp olive oil
- 1 tsp paprika

Instructions
1. Preheat oven to 425F.
2. Toss chicken with oil and paprika.
3. Roast 35 minutes.
"""


class FakeScrapeClient(RecipeScrapeClient):
    def __init__(self, html: str | None = None, error: str | None = None) -> None:
        self._html = html
        self._error = error

    def fetch_html(self, url: str) -> str:
        del url  # signature parity with RecipeScrapeClient; this fake ignores it
        if self._error:
            raise RecipeFetchError(self._error)
        return self._html or ""


# ---- unit tests: JSON-LD extraction ----

def test_import_recipe_from_ld_json():
    service = RecipeImportService(FakeScrapeClient(html=LD_JSON_PAGE))
    draft = service.import_recipe(RecipeImportRequest(url="https://example.com/pasta"))

    assert draft.title == "Weeknight Lemon Pasta"
    assert draft.servings == "4 servings"
    assert draft.time == "25 min"
    assert draft.photo == "https://example.com/lemon-pasta.jpg"
    assert draft.ingredients == ["200 g spaghetti", "1 lemon, zested and juiced", "50 g parmesan"]
    assert draft.steps == ["Boil the pasta until al dente.", "Toss with lemon, butter and parmesan."]
    assert set(draft.tags) >= {"pasta", "quick", "weeknight"}
    assert "bright pasta" in draft.notes
    assert draft.source_url == "https://example.com/pasta"
    assert draft.warnings == []


def test_import_recipe_lowercases_shouting_keywords():
    page = LD_JSON_PAGE.replace('"pasta, quick, weeknight"', '"30-MINUTE MEALS, Low Budget"')
    draft = RecipeImportService(FakeScrapeClient(html=page)).import_recipe(
        RecipeImportRequest(url="https://example.com/pasta")
    )
    assert draft.tags == ["30-minute meals", "Low Budget"]


def test_import_recipe_unwraps_at_graph_and_string_instructions():
    service = RecipeImportService(FakeScrapeClient(html=GRAPH_PAGE))
    draft = service.import_recipe(RecipeImportRequest(url="https://example.com/soup"))

    assert draft.title == "Graph Wrapped Soup"
    assert draft.ingredients == ["1 onion", "2 carrots"]
    assert draft.steps == ["Chop everything.", "Simmer for 20 minutes."]


def test_import_recipe_falls_back_to_text_heuristic_without_structured_data():
    service = RecipeImportService(FakeScrapeClient(html=NO_STRUCTURED_DATA_PAGE))
    draft = service.import_recipe(RecipeImportRequest(url="https://example.com/cookies"))

    assert draft.title == "Grandma's Cookies"
    assert draft.ingredients == ["2 cups flour", "1 cup sugar"]
    assert draft.steps == ["Mix everything.", "Bake at 350F for 12 minutes."]
    assert "no_structured_data" in draft.warnings


def test_import_recipe_raises_on_fetch_failure():
    service = RecipeImportService(FakeScrapeClient(error="timed out"))
    with pytest.raises(Exception):
        service.import_recipe(RecipeImportRequest(url="https://example.com/broken"))


def test_import_recipe_requires_url_or_text():
    service = RecipeImportService(FakeScrapeClient(html=""))
    with pytest.raises(Exception):
        service.import_recipe(RecipeImportRequest())


# ---- unit tests: pasted-text heuristic ----

def test_parse_free_text_pulls_title_ingredients_and_steps():
    draft = _parse_free_text(PASTED_TEXT)

    assert draft.title == "Sheet Pan Chicken"
    assert draft.ingredients == ["4 chicken thighs", "2 tbsp olive oil", "1 tsp paprika"]
    assert draft.steps == [
        "Preheat oven to 425F.",
        "Toss chicken with oil and paprika.",
        "Roast 35 minutes.",
    ]
    assert draft.warnings == []


def test_parse_free_text_flags_missing_sections():
    draft = _parse_free_text("Just a title\nsome rambling notes with no headers")
    assert "ingredients" in draft.warnings
    assert "steps" in draft.warnings


def test_strip_html_drops_tags_and_scripts():
    text = strip_html("<script>evil()</script><p>Hello <b>World</b></p>")
    assert "evil()" not in text
    assert "Hello" in text and "World" in text


# ---- router-level tests with the full app: the import is saved ----

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


def test_post_recipes_import_saves_the_scraped_recipe(app, client):
    app.dependency_overrides[get_recipe_scrape_client] = lambda: FakeScrapeClient(html=LD_JSON_PAGE)

    resp = client.post("/api/recipes/import", json={"url": "https://example.com/pasta"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["recipe"]["id"] > 0
    assert body["recipe"]["title"] == "Weeknight Lemon Pasta"
    assert body["recipe"]["ingredients"][0] == "200 g spaghetti"
    assert "Source: https://example.com/pasta" in body["recipe"]["notes"]
    assert body["warnings"] == []

    listed = client.get("/api/recipes").json()["items"]
    assert [r["title"] for r in listed] == ["Weeknight Lemon Pasta"]


def test_post_recipes_import_with_pasted_text(client):
    resp = client.post("/api/recipes/import", json={"text": PASTED_TEXT})

    assert resp.status_code == 201
    body = resp.json()
    assert body["recipe"]["title"] == "Sheet Pan Chicken"
    assert len(body["recipe"]["steps"]) == 3
    assert len(client.get("/api/recipes").json()["items"]) == 1


def test_post_recipes_import_requires_input(client):
    resp = client.post("/api/recipes/import", json={})
    assert resp.status_code == 422
    assert client.get("/api/recipes").json()["items"] == []


def test_post_recipes_import_reports_fetch_failure(app, client):
    app.dependency_overrides[get_recipe_scrape_client] = lambda: FakeScrapeClient(error="timed out")
    resp = client.post("/api/recipes/import", json={"url": "https://example.com/x"})
    assert resp.status_code == 502
    assert "timed out" in resp.json()["detail"]
