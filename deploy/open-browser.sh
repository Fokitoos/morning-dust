#!/usr/bin/env bash
# Open the dashboard in a normal Chromium window at login (not kiosk).
# Launched by the desktop session's autostart — see README.
set -u

URL="http://localhost:8000"

# Pick whichever Chromium binary this image ships.
if command -v chromium-browser >/dev/null 2>&1; then
    BIN=chromium-browser
elif command -v chromium >/dev/null 2>&1; then
    BIN=chromium
else
    echo "open-browser: no chromium binary found" >&2
    exit 1
fi

# Wait for the FastAPI service to answer so we don't open on a "can't connect"
# page during a slow boot.
for _ in $(seq 1 60); do
    if curl -sf -o /dev/null "$URL"; then
        break
    fi
    sleep 1
done

exec "$BIN" --start-maximized "$URL"