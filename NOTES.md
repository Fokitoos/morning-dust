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

## External Services Reference

| Purpose | Service | Key needed? | Notes |
|--|--|--|--|
| Weather | Open-Meteo | No | 10k calls/day free. |
| Commute (planned) | Google Maps Directions | Yes | Free tier limited. |
| Todo (planned) | TBD | — | Local storage? Todoist? Google Tasks? |