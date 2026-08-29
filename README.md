# morning-dust

A magic-mirror–style family dashboard for a Raspberry Pi touchscreen: a
FastAPI backend serving a single self-contained page, with six tabs.

- **Today** — the weight curve, what's on today, open to-dos, a recipe
  suggestion, recent notes, and the commute.
- **Calendar** — a week view merging read-only ICS feeds with events you add
  yourself. Imports `.ics` files.
- **To-dos** — one shared list with optional due dates.
- **Recipes** — a recipe book with photos, ingredients and steps, plus a
  pizza dough calculator (pizzas × rest window × yeast type → ingredients
  and method, sized for 12" Ooni-style bakes).
- **Notes** — a sticky-note board.
- **Ermis** — a weight logbook with a chart.

Weather and commute times are fetched from external APIs; everything else
lives in one SQLite file on the Pi, so the kiosk, your phone and a laptop all
see the same data. The browser keeps a `localStorage` copy purely as an
offline fallback.

The UI is one compiled `app/static/index.html` (React 18, loaded from unpkg).
See [INTEGRATION.md](INTEGRATION.md) for the API surface and how that file is
built.

## Run it locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run python main.py
```

Then open http://localhost:8000.

### Choosing a host and port

`main.py` is a [Typer](https://typer.tiangolo.com/) CLI. Run it with `--help`
to see everything:

```bash
uv run python main.py --help
```

| Option | Default | What it does |
| --- | --- | --- |
| `--host` | `0.0.0.0` | Interface to bind. `0.0.0.0` serves the whole LAN; `127.0.0.1` keeps it to this machine. |
| `--port`, `-p` | `8000` | Port to listen on. |
| `--reload` / `--no-reload` | `--no-reload` | Restart on code changes. Handy while developing. |

```bash
uv run python main.py --port 9000              # different port
uv run python main.py --host 127.0.0.1         # this machine only
uv run python main.py -p 9000 --reload         # dev server on 9000
```

### Configuration

Settings are read from a `.env` file in the repo root (prefix
`MORNING_DUST_`) — see `app/config.py` for every option. Host, port and reload
can be set there too:

```dotenv
MORNING_DUST_HOST=127.0.0.1
MORNING_DUST_PORT=9000
MORNING_DUST_DEBUG=true
```

Precedence is **command-line flag → environment / `.env` → built-in default**,
so the flags above override `.env` for a single run without editing anything.

> Changing the port has two knock-on effects: `deploy/open-browser.sh` waits on
> port 8000, and the systemd unit runs `main.py` with no flags. Update both if
> you want a different port on the Pi — see below.

---

## Deploy on a Raspberry Pi (Debian 12 / Bookworm)

Run the FastAPI app as a **systemd service** so it starts on boot, runs in the
background, and restarts on crash. The unit and installer live in `deploy/`.

```bash
cd ~/repos/morning-dust
bash deploy/install-service.sh
```

This copies `deploy/morning-dust.service` to `/etc/systemd/system/`, then
`enable --now` makes it start on boot and start immediately. The unit runs
`uv run python main.py` as your user, waits for the network, and restarts on
crash.

The app already binds `0.0.0.0:8000`, so it's reachable from any phone or
laptop on the same Wi-Fi as the Pi. The installer opens port 8000 in `ufw` if
it finds that firewall active, and prints the URLs to use — normally
`http://<pi-hostname>.local:8000`, or the printed LAN IP if `.local` mDNS
doesn't resolve on your phone.

Manage it:

```bash
sudo systemctl status morning-dust      # running?
journalctl -u morning-dust -f           # live logs
sudo systemctl restart morning-dust     # after a code change
sudo systemctl disable --now morning-dust   # stop + remove from boot
```

### Auto-update on start

Every start and restart runs `deploy/update.sh` first, which does a
`git pull --ff-only` of the current branch. So deploying is just:

```bash
git push                                # from your laptop
sudo systemctl restart morning-dust     # on the Pi
```

`uv run` re-syncs the venv from `uv.lock`, so a pull that changes dependencies
needs no extra step. The pull is deliberately timid — it skips when the working
tree is dirty or HEAD is detached, and a network or auth failure just logs and
starts the old code. Check what happened with `journalctl -u morning-dust | grep
update:`.

Because `origin` is an SSH remote, the Pi needs a **passphrase-less** key that
can read the repo (a GitHub deploy key is the tidy option) — there is no agent
or prompt available under systemd. Verify it before relying on this:

```bash
GIT_SSH_COMMAND='ssh -o BatchMode=yes' git -C ~/repos/morning-dust fetch origin
```

If that asks for anything or fails, the pull will silently no-op every boot.

> If your username isn't `fokito` or the repo isn't at
> `/home/fokito/repos/morning-dust`, edit `User=`, `WorkingDirectory=`, and the
> `ExecStart=` uv path in `deploy/morning-dust.service` before installing.
> Find your uv path with `which uv`.

To run the service on a different host or port, either add the flags to
`ExecStart=` in `deploy/morning-dust.service`:

```ini
ExecStart=/home/fokito/.local/bin/uv run python main.py --port 9000
```

…or set `MORNING_DUST_PORT` in the repo's `.env`, which the unit picks up
without editing it. Either way, also change `URL=` in `deploy/open-browser.sh`
so the browser opens the right address. Then
`sudo systemctl daemon-reload && sudo systemctl restart morning-dust`.

### Open Chromium to the dashboard on boot

This opens a normal Chromium window (not kiosk) at the app URL after login.
A graphical desktop must be running, so the Pi has to boot into the desktop
with autologin (a console/`tty` boot has no display for Chromium to use).

**1. Boot to the desktop, logged in automatically:**

```bash
sudo raspi-config nonint do_boot_behaviour B4   # Desktop Autologin
```

(Or interactively: `sudo raspi-config` → System Options → Boot / Auto Login →
*Desktop Autologin*.)

**2. Autostart the browser launcher.** `deploy/open-browser.sh` picks the right
Chromium binary, waits for the app to answer on port 8000, then opens it
maximized. Wire it into the desktop session's autostart:

```bash
mkdir -p ~/.config/autostart
cp deploy/morning-dust-browser.desktop ~/.config/autostart/
```

On the Bookworm default desktop (labwc), if the XDG autostart above doesn't
fire, add it to labwc's own autostart instead:

```bash
mkdir -p ~/.config/labwc
echo '/home/fokito/repos/morning-dust/deploy/open-browser.sh &' >> ~/.config/labwc/autostart
```

Reboot to test: `sudo reboot`. Chromium should open on the dashboard.