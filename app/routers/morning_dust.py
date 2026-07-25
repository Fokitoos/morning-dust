"""morning-dust dashboard API: one merged todo list, writable calendar events on top
of the read-only ICS feeds, recipes, notes and the weight log."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from app.schemas.morning_dust import (
    AgendaEvent,
    AgendaResponse,
    EventBulk,
    EventBulkResult,
    EventNew,
    EventPatch,
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
    TodoPatch,
    Weight,
    WeightList,
    WeightNew,
)
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
