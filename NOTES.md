# Morning Dust — Notes & Future Ideas

Running log of decisions, kiosk setup, and ideas to revisit. Nothing here is
required to run the app — see `README.md` for that.

## Chrome Kiosk Setup (Raspberry Pi)

Launch command for the touchscreen:

```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars --incognito \
    --disable-pinch --overscroll-history-navigation=0 \
    http://localhost:8000
```

Helpful companions:

- `unclutter -idle 0` — hide the mouse cursor.
- `xset s off -dpms` — disable screen blanking / DPMS.
- Autostart via `~/.config/lxsession/LXDE-pi/autostart` or a systemd user unit.
- For auto-boot of the FastAPI app: a `systemd` service that runs
  `uv run python main.py` from this repo.

Alternative to `--kiosk`: `--app=http://localhost:8000`. Chromeless but not
locked down — easier to exit during development, less hardened for production.

## Frontend Architecture

- Plain HTML/CSS/JS served by FastAPI's `StaticFiles` (no build step, no Node
  on the Pi).
- Polls `/api/weather` every 60s. Open-Meteo refreshes its `current` block
  every ~15 min, so faster polling is wasted.
- `.stale` CSS class is applied when a fetch fails — values dim, "offline"
  label is shown. Keeps the screen from looking frozen on a network blip.

## Ideas to Revisit

### Caching the weather response
Currently every `GET /api/weather` hits Open-Meteo live. With one client
(the Pi) refreshing every 60s, that's ~1.4k calls/day — under the free quota
but wasteful. A small in-process TTL cache (5–10 min) in `WeatherService`
would fix it. Worth doing once a second widget starts polling too.

### Server-Sent Events instead of polling
When several widgets are live, polling each from the client gets noisy. SSE
from FastAPI (`StreamingResponse` with `text/event-stream`) gives one-way
push updates with no extra deps. Fits a dashboard well.

### Clock + greeting widget
Pure client-side, no API needed. Classic magic-mirror element. Drop into the
empty cells of the 2x2 grid in `app/static/index.html`.

### Touch interactions
The 2x2 grid widgets could be tappable to expand. Keep gestures simple —
single tap only, no drag, no swipe — touchscreens behind glass are unreliable
for anything fancier.

### Frontend build pipeline — avoid for now
Tempting to reach for React/Vue/Svelte. Resist until the dashboard outgrows
what static HTML + a few hundred lines of JS can do. The Pi has limited CPU
and a build step is operational overhead you don't need yet.

## Known Quirks

- **Pyright false positive on `_index`**: the decorator-registered route
  handler in `app/main.py` is flagged as unused. Silence with
  `# pyright: ignore[reportUnusedFunction]` if it gets annoying.
- **Open-Meteo `current` block lags ~15 min**: see comment in
  `app/clients/weather_client.py`. Not a bug, just how the provider works.

## Commute Widget

Backed by **TomTom Routing API** (`api.tomtom.com/routing/1/calculateRoute`).
Returns live-traffic ETA plus the typical (no-traffic) duration so the UI
can show "40 min (+10)" with "usually 30 min" underneath.

- **Free tier: 2,500 requests/day.** With one daily scheduled refresh + a
  handful of manual presses, you're nowhere near the limit.
- **Requires a free API key** — sign up at developer.tomtom.com, no card
  required (verify on signup). Store it as `MORNING_DUST_TOMTOM_API_KEY`.
  Without it, the widget shows `no_api_key` and never calls out.

### Why not OSRM
We started on the public OSRM demo server but dropped it: OSRM is
free-flow only (no live traffic data), and the demo server is
rate-limited and not guaranteed to stay up. Self-hosting OSRM doesn't
solve the traffic problem either — it'd need a separately sourced
traffic feed, which is a real project. TomTom's free tier covers the
need without operational overhead.

### Other free traffic-aware alternatives (if TomTom ever doesn't fit)
- **HERE Routing** — 1k req/day free, key required.
- **Mapbox Directions** — 100k req/month free, key required, good if we
  also want a map.
- **Google Directions** — $200/mo credit but requires a card on file.

### Scheduling
- Refresh runs **once on app startup** and then **daily at the configured
  hour** (default 7:00 local time, `MORNING_DUST_COMMUTE_DAILY_REFRESH_HOUR`).
- Implementation: `app/services/commute_scheduler.py` — plain `asyncio`
  loop started from FastAPI's `lifespan`. No APScheduler dep.
- Single-worker design. If we ever run multiple uvicorn workers, each
  would run the loop. For a kiosk that's a non-issue.
- The frontend's `↻` button hits `POST /api/commute/refresh` for on-demand
  fetches. The widget also polls `GET /api/commute` every 5 min — that's a
  cheap read of the cached value, *not* a new OSRM call.

### Config
Set via env vars (or edit `app/config.py`). Until both origin and
destination coords are set, the service short-circuits and returns
`status: "not_configured"`.

```
MORNING_DUST_TOMTOM_API_KEY=<your key>
MORNING_DUST_COMMUTE_ORIGIN_LAT=...
MORNING_DUST_COMMUTE_ORIGIN_LON=...
MORNING_DUST_COMMUTE_DESTINATION_LAT=...
MORNING_DUST_COMMUTE_DESTINATION_LON=...
MORNING_DUST_COMMUTE_ORIGIN_NAME="Home"
MORNING_DUST_COMMUTE_DESTINATION_NAME="Office"
MORNING_DUST_COMMUTE_PROFILE=car          # car | bicycle | pedestrian | motorcycle | truck
MORNING_DUST_COMMUTE_DAILY_REFRESH_HOUR=7
MORNING_DUST_COMMUTE_TIMEOUT_S=10
```

### Behavior on errors
- `refresh()` failures (network, TomTom 5xx, bad key, parsing) keep the
  previously cached duration/distance/timestamp and flip `status` to
  `"error"`. The UI shows "(refresh failed)" next to the old value
  rather than blanking the widget.
- Before the first successful refresh, status is `"stale"` and duration
  shows `--`.
- If `MORNING_DUST_TOMTOM_API_KEY` is unset, the service short-circuits
  with `status: "no_api_key"` and never calls TomTom.

### Ideas to revisit
- **Persist the cache to disk** so a server restart doesn't lose the last
  fetch. Cheap (one JSON file under `data/`); only worth it once we're
  rebooting the Pi often enough to notice.
- **Live traffic** — only worth the cost (and key management on the Pi)
  if morning routing is dynamic enough to matter. For most fixed
  commutes, OSRM's static number is good enough as a "is it the usual?"
  reference.
- **Multiple routes** (e.g. car vs bike) — extend `CommuteService` to
  hold a dict keyed by profile.

## Calendar Widget

Read-only display of upcoming events, backed by **Google Calendar's private
iCal (.ics) feed** — no OAuth, no Google Cloud project. Same philosophy as
the Open-Meteo weather choice: a plain authenticated HTTPS GET.

### Getting the URL
Google Calendar → Settings → *your calendar* → **Integrate calendar** →
**Secret address in iCal format**. That URL *is* the credential — anyone
with it can read the calendar. Keep it in `.env`, never commit it. To revoke,
use "Reset" on that page (it issues a new URL).

- **Multiple calendars:** set several URLs, comma- or whitespace-separated.
  They're merged and sorted by start time.
- **Recurring events** (weekly standups etc.) are expanded into their
  individual upcoming occurrences via `recurring-ical-events` — a naive ICS
  parse would only show the first instance.
- All-day events are flagged (`all_day: true`) so the UI shows "all day"
  instead of a clock time. Already-finished events are dropped.

### Freshness caveat
Google caches the private ICS feed server-side; updates can lag from a few
minutes up to a couple of hours. Fine for a "what's on today" mirror; if you
need an event added from your phone to appear on the glass within seconds,
this is the wrong tool (use the OAuth Calendar API instead). The backend adds
a 5-min in-memory TTL cache on top, since sub-cache freshness is moot anyway.

### Behavior on errors
- A fetch/parse failure serves the **last good result** with `status: "error"`
  rather than blanking the widget. With no prior cache, returns empty + error.
- No URLs configured → `status: "not_configured"`.

### Config
```
MORNING_DUST_CALENDAR_ICS_URLS=https://calendar.google.com/calendar/ical/.../basic.ics
# multiple: comma- or whitespace-separated
MORNING_DUST_CALENDAR_DAYS_AHEAD=7
MORNING_DUST_CALENDAR_MAX_EVENTS=8
MORNING_DUST_CALENDAR_TIMEOUT_S=8
```

### Ideas to revisit
- **OAuth Calendar API** if real-time / two-way editing is ever needed — see
  trade-off note above. Bigger setup (token file on the Pi).
- **Per-calendar color dots** if merging several feeds and it gets hard to
  tell them apart.

## External Services Reference

| Purpose | Service | Key needed? | Notes |
|--|--|--|--|
| Weather | Open-Meteo | No | 10k calls/day free. |
| Commute | TomTom Routing | Yes (free) | 2,500 req/day; live traffic + typical time. |
| Calendar | Google private iCal | Secret URL | Read-only; no OAuth; merges multiple feeds. |
| Todo | Local JSON file | — | `data/todos.json`, gitignored. |