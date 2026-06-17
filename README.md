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