"""Data services for the morning-dust sections. Thin wrappers over SQLite — no
in-memory caching, so several browsers (kiosk + phone) always see the same
state."""

import json
import time
from datetime import date, timedelta

from fastapi import HTTPException

from app.db import db, init_db
from app.schemas.morning_dust import (
    AgendaEvent,
    AgendaResponse,
    EventBulk,
    EventBulkResult,
    EventNew,
    EventPatch,
    GroceriesAddResult,
    Note,
    NoteNew,
    Recipe,
    RecipeNew,
    Todo,
    TodoNew,
    TodoPatch,
    Weight,
    WeightNew,
)
from app.schemas.nutrition import NutritionInfo
from app.services.calendar_service import get_calendar_service


def _now_ms() -> int:
    return int(time.time() * 1000)


def _jl(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def _nutrition(raw: str) -> NutritionInfo | None:
    if not raw:
        return None
    try:
        return NutritionInfo.model_validate_json(raw)
    except ValueError:
        return None


# ---- todos ----

def _todo(r) -> Todo:
    return Todo(id=r["id"], text=r["text"], done=bool(r["done"]), due=r["due"],
                list=r["list"], source=r["source"])


_TODO_COLS = "id, text, done, due, list, source"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


class TodoStore:
    def list(self) -> list[Todo]:
        with db() as conn:
            rows = conn.execute(
                f"SELECT {_TODO_COLS} FROM todos ORDER BY done, "
                "CASE WHEN due = '' THEN 1 ELSE 0 END, due, sort, id"
            ).fetchall()
        return [_todo(r) for r in rows]

    def create(self, payload: TodoNew) -> Todo:
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Todo text is required")
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO todos (text, done, due, sort, list, source) VALUES (?, ?, ?, "
                "COALESCE((SELECT MAX(sort) + 1 FROM todos), 0), ?, ?)",
                (text, int(payload.done), payload.due, payload.list, payload.source.strip()),
            )
            new_id = int(cur.lastrowid)
        return Todo(id=new_id, text=text, done=payload.done, due=payload.due,
                    list=payload.list, source=payload.source.strip())

    def add_groceries(self, lines: list[str], source: str) -> GroceriesAddResult:
        """Append ingredient lines to the groceries list. A line that's already
        open on the list (same text, ignoring case/spacing) is skipped, so
        adding the same recipe twice doesn't double it up — while two
        different recipes both wanting olive oil still get two lines, each
        tagged with its recipe."""
        source = source.strip()
        added: list[Todo] = []
        skipped = 0
        with db() as conn:
            open_rows = conn.execute(
                "SELECT text FROM todos WHERE list = 'groceries' AND done = 0"
            ).fetchall()
            present = {_norm(r["text"]) for r in open_rows}
            for raw in lines:
                text = raw.strip()
                if not text:
                    continue
                if _norm(text) in present:
                    skipped += 1
                    continue
                cur = conn.execute(
                    "INSERT INTO todos (text, done, due, sort, list, source) VALUES (?, 0, '', "
                    "COALESCE((SELECT MAX(sort) + 1 FROM todos), 0), 'groceries', ?)",
                    (text, source),
                )
                present.add(_norm(text))
                added.append(Todo(id=int(cur.lastrowid), text=text, list="groceries", source=source))
        return GroceriesAddResult(added=added, skipped=skipped, source=source)

    def clear_done(self, list_name: str) -> int:
        with db() as conn:
            cur = conn.execute("DELETE FROM todos WHERE list = ? AND done = 1", (list_name,))
            return cur.rowcount

    def update(self, todo_id: int, payload: TodoPatch) -> Todo:
        sets, args = [], []
        if payload.text is not None:
            sets.append("text = ?")
            args.append(payload.text.strip())
        if payload.done is not None:
            sets.append("done = ?")
            args.append(int(payload.done))
        if payload.due is not None:
            sets.append("due = ?")
            args.append(payload.due)
        with db() as conn:
            if sets:
                conn.execute(f"UPDATE todos SET {', '.join(sets)} WHERE id = ?", (*args, todo_id))
            row = conn.execute(f"SELECT {_TODO_COLS} FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Todo not found")
        return _todo(row)

    def delete(self, todo_id: int) -> None:
        with db() as conn:
            cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Todo not found")


# ---- calendar (local events + merged agenda) ----

class AgendaStore:
    """Local events live in SQLite and are editable; ICS feed events are
    read-only and merged in on read."""

    def _row_to_event(self, row) -> AgendaEvent:
        return AgendaEvent(
            id=f"local:{row['id']}",
            title=row["title"],
            date=row["date"],
            time=row["time"],
            location=row["location"],
            source="local",
            editable=True,
        )

    def range(self, start: str, end: str) -> AgendaResponse:
        with db() as conn:
            rows = conn.execute(
                "SELECT id, title, date, time, location FROM local_events "
                "WHERE date >= ? AND date <= ? ORDER BY date, "
                "CASE WHEN time = '' THEN '00:00' ELSE time END",
                (start, end),
            ).fetchall()
        events = [self._row_to_event(r) for r in rows]

        feed = get_calendar_service().get_range(start, end)
        events.extend(feed.events)
        events.sort(key=lambda e: (e.date, e.time or "00:00", e.title))
        return AgendaResponse(events=events, status=feed.status)

    def upcoming(self, days: int = 7) -> AgendaResponse:
        today = date.today()
        return self.range(today.isoformat(), (today + timedelta(days=days)).isoformat())

    def create(self, payload: EventNew) -> AgendaEvent:
        title = payload.title.strip()
        if not title or not payload.date:
            raise HTTPException(status_code=422, detail="Title and date are required")
        with db() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO local_events (title, date, time, location) VALUES (?, ?, ?, ?)",
                (title, payload.date, payload.time, payload.location),
            )
            if cur.lastrowid and cur.rowcount:
                new_id = int(cur.lastrowid)
            else:  # identical event already there — return the existing one
                new_id = int(
                    conn.execute(
                        "SELECT id FROM local_events WHERE date = ? AND time = ? AND title = ?",
                        (payload.date, payload.time, title),
                    ).fetchone()["id"]
                )
        return AgendaEvent(
            id=f"local:{new_id}", title=title, date=payload.date,
            time=payload.time, location=payload.location, source="local",
        )

    def bulk(self, payload: EventBulk) -> EventBulkResult:
        imported = 0
        with db() as conn:
            for ev in payload.events:
                title = ev.title.strip()
                if not title or not ev.date:
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO local_events (title, date, time, location) VALUES (?, ?, ?, ?)",
                    (title, ev.date, ev.time, ev.location),
                )
                imported += cur.rowcount
        return EventBulkResult(imported=imported, skipped=len(payload.events) - imported)

    def _local_id(self, event_id: str) -> int:
        if not event_id.startswith("local:"):
            raise HTTPException(status_code=409, detail="Feed events are read-only")
        try:
            return int(event_id.split(":", 1)[1])
        except ValueError:
            raise HTTPException(status_code=422, detail="Bad event id") from None

    def update(self, event_id: str, payload: EventPatch) -> AgendaEvent:
        row_id = self._local_id(event_id)
        sets, args = [], []
        for field in ("title", "date", "time", "location"):
            value = getattr(payload, field)
            if value is not None:
                sets.append(f"{field} = ?")
                args.append(value.strip() if field == "title" else value)
        with db() as conn:
            if sets:
                conn.execute(f"UPDATE local_events SET {', '.join(sets)} WHERE id = ?", (*args, row_id))
            row = conn.execute(
                "SELECT id, title, date, time, location FROM local_events WHERE id = ?", (row_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return self._row_to_event(row)

    def delete(self, event_id: str) -> None:
        row_id = self._local_id(event_id)
        with db() as conn:
            cur = conn.execute("DELETE FROM local_events WHERE id = ?", (row_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Event not found")


# ---- recipes ----

class RecipeStore:
    def _row(self, r) -> Recipe:
        return Recipe(
            id=r["id"], title=r["title"], tags=_jl(r["tags"]), servings=r["servings"],
            time=r["time"], photo=r["photo"], ingredients=_jl(r["ingredients"]),
            steps=_jl(r["steps"]), notes=r["notes"], nutrition=_nutrition(r["nutrition"]),
            updated=r["updated"],
        )

    def list(self) -> list[Recipe]:
        with db() as conn:
            rows = conn.execute("SELECT * FROM recipes ORDER BY title COLLATE NOCASE").fetchall()
        return [self._row(r) for r in rows]

    def create(self, payload: RecipeNew) -> Recipe:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Recipe title is required")
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO recipes (title, tags, servings, time, photo, ingredients, steps, notes, updated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, json.dumps(payload.tags), payload.servings, payload.time, payload.photo,
                 json.dumps(payload.ingredients), json.dumps(payload.steps), payload.notes, _now_ms()),
            )
            new_id = int(cur.lastrowid)
        return self.get(new_id)

    def get(self, recipe_id: int) -> Recipe:
        with db() as conn:
            row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return self._row(row)

    def replace(self, recipe_id: int, payload: RecipeNew) -> Recipe:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Recipe title is required")
        # The nutrition column is deliberately left alone: an estimate costs
        # tokens, so it persists until the user asks for a re-estimate.
        with db() as conn:
            cur = conn.execute(
                "UPDATE recipes SET title = ?, tags = ?, servings = ?, time = ?, photo = ?, "
                "ingredients = ?, steps = ?, notes = ?, updated = ? WHERE id = ?",
                (title, json.dumps(payload.tags), payload.servings, payload.time, payload.photo,
                 json.dumps(payload.ingredients), json.dumps(payload.steps), payload.notes,
                 _now_ms(), recipe_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Recipe not found")
        return self.get(recipe_id)

    def set_nutrition(self, recipe_id: int, info: NutritionInfo) -> Recipe:
        with db() as conn:
            cur = conn.execute(
                "UPDATE recipes SET nutrition = ? WHERE id = ?",
                (info.model_dump_json(), recipe_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Recipe not found")
        return self.get(recipe_id)

    def delete(self, recipe_id: int) -> None:
        with db() as conn:
            cur = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Recipe not found")


# ---- notes ----

class NoteStore:
    def list(self) -> list[Note]:
        with db() as conn:
            rows = conn.execute("SELECT id, text, updated FROM notes ORDER BY updated DESC").fetchall()
        return [Note(id=r["id"], text=r["text"], updated=r["updated"]) for r in rows]

    def create(self, payload: NoteNew) -> Note:
        stamp = _now_ms()
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO notes (text, updated) VALUES (?, ?)", (payload.text, stamp)
            )
            new_id = int(cur.lastrowid)
        return Note(id=new_id, text=payload.text, updated=stamp)

    def update(self, note_id: int, text: str) -> Note:
        stamp = _now_ms()
        with db() as conn:
            cur = conn.execute(
                "UPDATE notes SET text = ?, updated = ? WHERE id = ?", (text, stamp, note_id)
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Note not found")
        return Note(id=note_id, text=text, updated=stamp)

    def delete(self, note_id: int) -> None:
        with db() as conn:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Note not found")


# ---- weights ----

class WeightStore:
    def list(self) -> list[Weight]:
        with db() as conn:
            rows = conn.execute(
                "SELECT id, date, grams, person FROM weights ORDER BY date"
            ).fetchall()
        return [
            Weight(id=r["id"], date=r["date"], grams=r["grams"], person=r["person"])
            for r in rows
        ]

    def create(self, payload: WeightNew) -> Weight:
        if not payload.date:
            raise HTTPException(status_code=422, detail="Date is required")
        if not 300 <= payload.grams <= 30000:
            raise HTTPException(status_code=422, detail="Weight must be between 300 and 30000 grams")
        person = payload.person.strip() or "ermis"
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO weights (date, grams, person) VALUES (?, ?, ?)",
                (payload.date, payload.grams, person),
            )
            new_id = int(cur.lastrowid)
        return Weight(id=new_id, date=payload.date, grams=payload.grams, person=person)

    def delete(self, weight_id: int) -> None:
        with db() as conn:
            cur = conn.execute("DELETE FROM weights WHERE id = ?", (weight_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Entry not found")


_todos = TodoStore()
_agenda = AgendaStore()
_recipes = RecipeStore()
_notes = NoteStore()
_weights = WeightStore()


def get_todo_store() -> TodoStore:
    init_db()
    return _todos


def get_agenda_store() -> AgendaStore:
    init_db()
    return _agenda


def get_recipe_store() -> RecipeStore:
    init_db()
    return _recipes


def get_note_store() -> NoteStore:
    init_db()
    return _notes


def get_weight_store() -> WeightStore:
    init_db()
    return _weights
