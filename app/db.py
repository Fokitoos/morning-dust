"""SQLite store for the morning-dust-backed sections (todos, local calendar events,
recipes, notes, weights).

One connection per request: FastAPI runs sync endpoints in a threadpool, and a
short-lived connection is simpler (and safe) compared to sharing one across
threads. WAL keeps concurrent reads from blocking on the odd write.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    text    TEXT    NOT NULL,
    done    INTEGER NOT NULL DEFAULT 0,
    due     TEXT    NOT NULL DEFAULT '',
    sort    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS local_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title    TEXT NOT NULL,
    date     TEXT NOT NULL,
    time     TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    UNIQUE (date, time, title)
);
CREATE INDEX IF NOT EXISTS local_events_date ON local_events (date);

CREATE TABLE IF NOT EXISTS recipes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    tags        TEXT    NOT NULL DEFAULT '[]',
    servings    TEXT    NOT NULL DEFAULT '',
    time        TEXT    NOT NULL DEFAULT '',
    photo       TEXT    NOT NULL DEFAULT '',
    ingredients TEXT    NOT NULL DEFAULT '[]',
    steps       TEXT    NOT NULL DEFAULT '[]',
    notes       TEXT    NOT NULL DEFAULT '',
    updated     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    text    TEXT    NOT NULL DEFAULT '',
    updated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weights (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date   TEXT    NOT NULL,
    grams  INTEGER NOT NULL,
    person TEXT    NOT NULL DEFAULT 'ermis'
);
CREATE INDEX IF NOT EXISTS weights_date ON weights (date);
"""

_init_lock = threading.Lock()
_initialized = False


def _db_path() -> Path:
    return Path(settings.db_path)


@contextmanager
def db():
    """Yield a connection, commit on clean exit, always close."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(force: bool = False) -> None:
    """Create tables (idempotent) and, once, lift any legacy JSON todo lists
    into the single merged todos table."""
    global _initialized
    with _init_lock:
        if _initialized and not force:
            return
        with db() as conn:
            conn.executescript(_SCHEMA)
            _migrate(conn)
            if settings.import_json_todos:
                _import_json_todos(conn)
        _initialized = True


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created before a column existed."""
    weight_cols = {row[1] for row in conn.execute("PRAGMA table_info(weights)")}
    if "person" not in weight_cols:
        conn.execute("ALTER TABLE weights ADD COLUMN person TEXT NOT NULL DEFAULT 'ermis'")


def reset_for_tests() -> None:
    global _initialized
    _initialized = False


def _import_json_todos(conn: sqlite3.Connection) -> None:
    """One-time merge of data/todos-*.json (the pre-morning-dust per-list files) into
    the single todos table. Skipped once todos holds anything."""
    if conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0] > 0:
        return
    todo_dir = Path(settings.todo_dir)
    if not todo_dir.exists():
        return
    rows: list[tuple[str, int, str, int]] = []
    for name in settings.todo_lists:
        path = todo_dir / f"todos-{name}.json"
        if not path.exists():
            continue
        try:
            items = json.loads(path.read_text() or "[]")
        except (OSError, json.JSONDecodeError):
            continue
        for item in items:
            title = (item.get("title") or "").strip()
            if title:
                rows.append((title, 1 if item.get("done") else 0, "", len(rows)))
    if rows:
        conn.executemany(
            "INSERT INTO todos (text, done, due, sort) VALUES (?, ?, ?, ?)", rows
        )
