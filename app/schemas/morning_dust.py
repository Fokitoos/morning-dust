"""Schemas for the morning-dust dashboard API — the merged todo list, local calendar
events, recipes, notes and weight log."""

from pydantic import BaseModel, Field


# ---- todos (single merged list) ----

class Todo(BaseModel):
    id: int
    text: str
    done: bool = False
    due: str = ""  # "" or YYYY-MM-DD


class TodoNew(BaseModel):
    text: str
    done: bool = False
    due: str = ""


class TodoPatch(BaseModel):
    text: str | None = None
    done: bool | None = None
    due: str | None = None


class TodoList(BaseModel):
    items: list[Todo]


# ---- calendar: merged agenda + writable local events ----

class AgendaEvent(BaseModel):
    id: str  # "local:12" or "ics:<stable-hash>"
    title: str
    date: str  # YYYY-MM-DD
    time: str = ""  # "" = all day
    location: str = ""
    source: str = "local"  # local | ics
    editable: bool = True


class AgendaResponse(BaseModel):
    events: list[AgendaEvent]
    # ok | local_only (no feeds configured) | partial (a feed failed) | error
    status: str


class EventNew(BaseModel):
    title: str
    date: str
    time: str = ""
    location: str = ""


class EventPatch(BaseModel):
    title: str | None = None
    date: str | None = None
    time: str | None = None
    location: str | None = None


class EventBulk(BaseModel):
    events: list[EventNew]


class EventBulkResult(BaseModel):
    imported: int
    skipped: int


# ---- recipes ----

class Recipe(BaseModel):
    id: int
    title: str
    tags: list[str] = Field(default_factory=list)
    servings: str = ""
    time: str = ""
    photo: str = ""  # data: URL or /static path
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    notes: str = ""
    updated: int = 0


class RecipeNew(BaseModel):
    title: str
    tags: list[str] = Field(default_factory=list)
    servings: str = ""
    time: str = ""
    photo: str = ""
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    notes: str = ""


class RecipeList(BaseModel):
    items: list[Recipe]


# ---- notes ----

class Note(BaseModel):
    id: int
    text: str = ""
    updated: int = 0  # epoch ms


class NoteNew(BaseModel):
    text: str = ""


class NotePatch(BaseModel):
    text: str


class NoteList(BaseModel):
    items: list[Note]


# ---- weights ----

class Weight(BaseModel):
    id: int
    date: str
    grams: int


class WeightNew(BaseModel):
    date: str
    grams: int


class WeightList(BaseModel):
    items: list[Weight]
