#!/usr/bin/env bash
# Install Morning Dust as a systemd service that starts on boot.
# Run from anywhere:  bash deploy/install-service.sh
set -euo pipefail

UNIT=morning-dust.service
SRC="$(cd "$(dirname "$0")" && pwd)/$UNIT"

echo "Installing $UNIT (requires sudo)…"
sudo cp "$SRC" "/etc/systemd/system/$UNIT"
sudo systemctl daemon-reload
sudo systemctl enable --now "$UNIT"

# The app itself already binds 0.0.0.0:8000 (see app/config.py), so it's
# reachable from the LAN as soon as nothing on the Pi blocks it. Raspberry Pi
# OS ships with no firewall by default, but if ufw is installed and enabled
# it silently drops the port — open it here so a phone on the same Wi-Fi can
# actually reach the dashboard. Skipped entirely when ufw isn't in play.
if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q "Status: active"; then
    echo
    echo "ufw is active — opening port 8000 for LAN access…"
    sudo ufw allow 8000/tcp comment "morning-dust dashboard"
fi

echo
sudo systemctl status "$UNIT" --no-pager || true

echo
HOST_NAME="$(hostname)"
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "Done. From your phone (same Wi-Fi as the Pi), open one of:"
echo "  http://${HOST_NAME}.local:8000"
[[ -n "$LAN_IP" ]] && echo "  http://${LAN_IP}:8000"
echo
echo "Useful commands:"
echo "  sudo systemctl status morning-dust     # is it running?"
echo "  journalctl -u morning-dust -f          # live logs"
echo "  sudo systemctl restart morning-dust    # after a code change"