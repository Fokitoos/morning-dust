# Wiring morning-dust into morning-dust

morning-dust is the new dashboard UI. It talks to this FastAPI app over JSON; the Pi's
SQLite file is the single source of truth, and every screen (kiosk, phone,
laptop) sees the same data. The browser keeps a copy in `localStorage` purely
as a fallback: when the API is unreachable morning-dust shows the last known data with
an "Offline — saved copy" badge, and replays writes made in the meantime once
the server answers again.

## What to copy where

Copy these into the repo, replacing where noted:

| From this project | To in `morning-dust` | Note |
| --- | --- | --- |
| `backend/app/db.py` | `app/db.py` | new — SQLite connection + schema |
| `backend/app/schemas/morning_dust.py` | `app/schemas/morning_dust.py` | new |
| `backend/app/services/morning_dust_service.py` | `app/services/morning_dust_service.py` | new |
| `backend/app/routers/morning_dust.py` | `app/routers/morning_dust.py` | new |
| `backend/app/services/calendar_service.py` | `app/services/calendar_service.py` | **replaces** — adds `get_range()` |
| `backend/app/config.py` | `app/config.py` | **replaces** — adds two `morning_dust_*` settings |
| `backend/app/main.py` | `app/main.py` | **replaces** — `init_db()` + new routers |
| `backend/app/static/index.html` | `app/static/index.html` | **replaces** — the whole morning-dust UI, one file |
| `backend/tests/test_morning_dust.py` | `tests/test_morning_dust.py` | new |

Then:

```bash
uv run pytest          # existing suites still pass; adds test_morning_dust.py
uv run python main.py  # http://localhost:8000
```

No new dependencies — `sqlite3` is in the standard library.

The old `app/static/app.js`, `pager.js`, `todo.js` and `styles.css` are no
longer referenced by `index.html`. Leave them in place until you're happy with
morning-dust, then delete them. `/api/todo/{list_name}` (the JSON-file lists) is
still mounted so nothing else breaks, and `GET /api/calendar` keeps its old
shape.

## Endpoints morning-dust uses

Existing, unchanged:

- `GET /api/weather` → `location`, `temperature_c`, min/max, `condition`
- `GET /api/commute`, `POST /api/commute/refresh` → the Today commute card

New:

| Method | Path | Body / query | Returns |
| --- | --- | --- | --- |
| GET | `/api/todos` | — | `{items: [{id, text, done, due}]}` |
| POST | `/api/todos` | `{text, due?, done?}` | the created todo |
| PATCH | `/api/todos/{id}` | any of `text`, `done`, `due` | the updated todo |
| DELETE | `/api/todos/{id}` | — | 204 |
| GET | `/api/calendar/events` | `?start=YYYY-MM-DD&end=YYYY-MM-DD` | `{events, status}` — local **and** feed events, merged and sorted |
| POST | `/api/calendar/events` | `{title, date, time?, location?}` | the created local event |
| POST | `/api/calendar/events/bulk` | `{events: [...]}` | `{imported, skipped}` — used by .ics import |
| PATCH | `/api/calendar/events/{id}` | partial event | the updated event |
| DELETE | `/api/calendar/events/{id}` | — | 204, or 409 for a feed event |
| GET/POST | `/api/recipes` | `{title, tags[], servings, time, photo, ingredients[], steps[], notes}` | recipes |
| PUT/DELETE | `/api/recipes/{id}` | full recipe | the recipe / 204 |
| GET/POST | `/api/notes` | `{text}` | `{items: [{id, text, updated}]}` |
| PATCH/DELETE | `/api/notes/{id}` | `{text}` | the note / 204 |
| GET/POST | `/api/weights` | `{date, grams}` | `{items: [{id, date, grams}]}` |
| DELETE | `/api/weights/{id}` | — | 204 |

Calendar ids are namespaced: `local:12` for rows in SQLite (editable),
`ics:<hash>` for feed events (read-only, and morning-dust renders them in sage with
no delete button). `status` is `ok`, `local_only` (no feeds configured),
`partial` or `error` — morning-dust shows a one-line note under the week for
anything but `ok`.

## Storage

One SQLite file, `data/morning-dust.db` by default
(`MORNING_DUST_DB_PATH` to move it), WAL mode, tables created on
startup. Tables: `todos`, `local_events`, `recipes`, `notes`, `weights`.

On first start, any existing `data/todos-groceries.json` /
`data/todos-tasks.json` items are merged into the single `todos` table (once —
skipped as soon as the table has rows). Set
`MORNING_DUST_IMPORT_JSON_TODOS=false` to skip it entirely.

Recipe photos are stored as `data:` URLs in the `photo` column. morning-dust
downscales to 900px / JPEG q80 before upload, so a photo is ~100-200 KB. Fine
for a personal book of a few hundred recipes; if it ever bothers you, switch
`photo` to a filename and write the bytes into `app/static/photos/`.

Back it up like any file: `sqlite3 data/morning-dust.db ".backup data/morning-dust.bak"`.

## Running it

- **Kiosk**: nothing to change. `/` serves morning-dust, the Chromium autostart
  script still points at port 8000.
- **Phone / laptop on the LAN**: `http://<pi-hostname>.local:8000`. The app
  already binds `0.0.0.0` and allows all CORS origins.
- **Serving the UI from somewhere else** (e.g. opening the file directly): set
  the `apiBase` tweak in morning-dust to `http://<pi>:8000`. Empty means
  same-origin, which is what you want when the Pi serves it.
- **Polling**: morning-dust re-reads everything every 5 minutes (`pollMinutes`
  tweak) and after every write.

## Rebuilding the UI file

`app/static/index.html` is compiled from `morning-dust.dc.html` in the design
project — edit there and re-export; don't hand-edit the compiled file. It is
fully self-contained apart from React, which loads from unpkg on first paint;
if the Pi may be offline at boot, confirm it once with DevTools → Network →
Offline, and if it fails, vendor the two React UMD files into
`app/static/vendor/` and point the two `<script src>` tags at them.

## Not wired to the server

Nothing. Weather, commute, calendar, to-dos, recipes, notes and the weight log
all read and write through the API; `localStorage` is only the offline cache.
