# morning-dust

A magic-mirror–style dashboard for a Raspberry Pi touchscreen, written in
Python (FastAPI + vanilla HTML/CSS/JS). Shows weather, a clock, commute time,
a calendar, and swipeable Groceries / Tasks lists.

## Run it locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run python main.py
```

Then open http://localhost:8000. Configuration is read from a `.env` file in
the repo root (prefix `MORNING_DUST_`) — see `app/config.py` for every option.

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

Manage it:

```bash
sudo systemctl status morning-dust      # running?
journalctl -u morning-dust -f           # live logs
sudo systemctl restart morning-dust     # after a code change
sudo systemctl disable --now morning-dust   # stop + remove from boot
```

> If your username isn't `fokito` or the repo isn't at
> `/home/fokito/repos/morning-dust`, edit `User=`, `WorkingDirectory=`, and the
> `ExecStart=` uv path in `deploy/morning-dust.service` before installing.
> Find your uv path with `which uv`.

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