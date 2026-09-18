"""morning-dust dashboard API: one merged todo list, writable calendar events on top
of the read-only ICS feeds, recipes, notes and the weight log."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas.morning_dust import (
    AgendaEvent,
    AgendaResponse,
    EventBulk,
    EventBulkResult,
    EventNew,
    EventPatch,
    GroceriesAddResult,
    Note,
    NoteList,
    NoteNew,
    NotePatch,
    Recipe,
    RecipeList,
    RecipeNew,
    Todo,
    TodoList,
    TodoNew,
    TodoListName,
    TodoPatch,
    Weight,
    WeightList,
    WeightNew,
)
from app.schemas.nutrition import ScaledRecipe
from app.schemas.recipe_import import RecipeImportRequest, RecipeImportResult
from app.services.morning_dust_service import (
    AgendaStore,
    NoteStore,
    RecipeStore,
    TodoStore,
    WeightStore,
    get_agenda_store,
    get_note_store,
    get_recipe_store,
    get_todo_store,
    get_weight_store,
)
from app.services.nutrition_service import NutritionService, get_nutrition_service
from app.services.recipe_import_service import RecipeImportService, get_recipe_import_service
from app.services.recipe_scale_service import parse_servings, scale_ingredients

todos = APIRouter()
events = APIRouter()
recipes = APIRouter()
notes = APIRouter()
weights = APIRouter()


# ---- todos ----

@todos.get("", response_model=TodoList)
def list_todos(store: TodoStore = Depends(get_todo_store)) -> TodoList:
    return TodoList(items=store.list())


@todos.post("", response_model=Todo, status_code=201)
def create_todo(payload: TodoNew, store: TodoStore = Depends(get_todo_store)) -> Todo:
    return store.create(payload)


@todos.patch("/{todo_id}", response_model=Todo)
def patch_todo(
    todo_id: int, payload: TodoPatch, store: TodoStore = Depends(get_todo_store)
) -> Todo:
    return store.update(todo_id, payload)


@todos.delete("/{todo_id}", status_code=204)
def delete_todo(todo_id: int, store: TodoStore = Depends(get_todo_store)) -> None:
    store.delete(todo_id)


class ClearDoneResult(BaseModel):
    removed: int


@todos.post("/clear-done", response_model=ClearDoneResult)
def clear_done_todos(
    list: TodoListName = Query(default="groceries"),
    store: TodoStore = Depends(get_todo_store),
) -> ClearDoneResult:
    """Remove every ticked item from a list — "clear bought" for groceries."""
    return ClearDoneResult(removed=store.clear_done(list))


# ---- calendar events ----

@events.get("", response_model=AgendaResponse)
def list_events(
    start: str | None = Query(default=None, description="YYYY-MM-DD, inclusive"),
    end: str | None = Query(default=None, description="YYYY-MM-DD, inclusive"),
    store: AgendaStore = Depends(get_agenda_store),
) -> AgendaResponse:
    if start is None or end is None:
        today = date.today()
        start = start or (today - timedelta(days=7)).isoformat()
        end = end or (today + timedelta(days=28)).isoformat()
    return store.range(start, end)


@events.post("", response_model=AgendaEvent, status_code=201)
def create_event(payload: EventNew, store: AgendaStore = Depends(get_agenda_store)) -> AgendaEvent:
    return store.create(payload)


@events.post("/bulk", response_model=EventBulkResult)
def bulk_events(payload: EventBulk, store: AgendaStore = Depends(get_agenda_store)) -> EventBulkResult:
    return store.bulk(payload)


@events.patch("/{event_id}", response_model=AgendaEvent)
def patch_event(
    event_id: str, payload: EventPatch, store: AgendaStore = Depends(get_agenda_store)
) -> AgendaEvent:
    return store.update(event_id, payload)


@events.delete("/{event_id}", status_code=204)
def delete_event(event_id: str, store: AgendaStore = Depends(get_agenda_store)) -> None:
    store.delete(event_id)


# ---- recipes ----

@recipes.get("", response_model=RecipeList)
def list_recipes(store: RecipeStore = Depends(get_recipe_store)) -> RecipeList:
    return RecipeList(items=store.list())


@recipes.post("", response_model=Recipe, status_code=201)
def create_recipe(payload: RecipeNew, store: RecipeStore = Depends(get_recipe_store)) -> Recipe:
    return store.create(payload)


@recipes.post("/import", response_model=RecipeImportResult, status_code=201)
def import_recipe(
    payload: RecipeImportRequest,
    service: RecipeImportService = Depends(get_recipe_import_service),
    store: RecipeStore = Depends(get_recipe_store),
) -> RecipeImportResult:
    """Scrape a recipe URL, or parse pasted recipe text, and save the result
    straight into the recipe book. The warnings name fields the parser
    couldn't confidently fill, so the user knows what to edit."""
    draft = service.import_recipe(payload)
    notes = draft.notes
    if draft.source_url:
        notes = (notes + "\n\n" if notes else "") + "Source: " + draft.source_url
    recipe = store.create(RecipeNew(
        title=draft.title, tags=draft.tags, servings=draft.servings, time=draft.time,
        photo=draft.photo, ingredients=draft.ingredients, steps=draft.steps, notes=notes,
    ))
    return RecipeImportResult(recipe=recipe, source_url=draft.source_url, warnings=draft.warnings)


@recipes.get("/{recipe_id}/scaled", response_model=ScaledRecipe)
def scaled_recipe(
    recipe_id: int,
    servings: int = Query(ge=1, le=100),
    store: RecipeStore = Depends(get_recipe_store),
) -> ScaledRecipe:
    """Ingredient lines rescaled from the recipe's own serving count."""
    recipe = store.get(recipe_id)
    base = parse_servings(recipe.servings)
    if base is None:
        raise HTTPException(status_code=422, detail="This recipe has no serving count to scale from")
    return scale_ingredients(recipe.ingredients, base, servings)


class GroceriesFromRecipe(BaseModel):
    servings: int | None = Field(default=None, ge=1, le=100)


@recipes.post("/{recipe_id}/groceries", response_model=GroceriesAddResult, status_code=201)
def recipe_to_groceries(
    recipe_id: int,
    payload: GroceriesFromRecipe | None = None,
    store: RecipeStore = Depends(get_recipe_store),
    todo_store: TodoStore = Depends(get_todo_store),
) -> GroceriesAddResult:
    """Put the recipe's ingredient lines on the groceries list, scaled to
    `servings` when given and the recipe has a serving count. Call it for
    several recipes to build one shopping list; each line remembers which
    recipe it came from."""
    recipe = store.get(recipe_id)
    lines = recipe.ingredients
    if payload and payload.servings:
        base = parse_servings(recipe.servings)
        if base and base != payload.servings:
            lines = [i.text for i in scale_ingredients(lines, base, payload.servings).ingredients]
    if not lines:
        raise HTTPException(status_code=422, detail="This recipe has no ingredients")
    return todo_store.add_groceries(lines, recipe.title)


@recipes.post("/{recipe_id}/nutrition", response_model=Recipe)
def estimate_nutrition(
    recipe_id: int,
    store: RecipeStore = Depends(get_recipe_store),
    service: NutritionService = Depends(get_nutrition_service),
) -> Recipe:
    """Estimate per-serving nutrition for the recipe and store it on it."""
    recipe = store.get(recipe_id)
    return store.set_nutrition(recipe_id, service.estimate_for(recipe))


@recipes.put("/{recipe_id}", response_model=Recipe)
def replace_recipe(
    recipe_id: int, payload: RecipeNew, store: RecipeStore = Depends(get_recipe_store)
) -> Recipe:
    return store.replace(recipe_id, payload)


@recipes.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, store: RecipeStore = Depends(get_recipe_store)) -> None:
    store.delete(recipe_id)


# ---- notes ----

@notes.get("", response_model=NoteList)
def list_notes(store: NoteStore = Depends(get_note_store)) -> NoteList:
    return NoteList(items=store.list())


@notes.post("", response_model=Note, status_code=201)
def create_note(payload: NoteNew, store: NoteStore = Depends(get_note_store)) -> Note:
    return store.create(payload)


@notes.patch("/{note_id}", response_model=Note)
def patch_note(note_id: int, payload: NotePatch, store: NoteStore = Depends(get_note_store)) -> Note:
    return store.update(note_id, payload.text)


@notes.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, store: NoteStore = Depends(get_note_store)) -> None:
    store.delete(note_id)


# ---- weights ----

@weights.get("", response_model=WeightList)
def list_weights(store: WeightStore = Depends(get_weight_store)) -> WeightList:
    return WeightList(items=store.list())


@weights.post("", response_model=Weight, status_code=201)
def create_weight(payload: WeightNew, store: WeightStore = Depends(get_weight_store)) -> Weight:
    return store.create(payload)


@weights.delete("/{weight_id}", status_code=204)
def delete_weight(weight_id: int, store: WeightStore = Depends(get_weight_store)) -> None:
    store.delete(weight_id)
