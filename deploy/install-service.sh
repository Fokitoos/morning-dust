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

echo
sudo systemctl status "$UNIT" --no-pager || true
echo
echo "Done. Useful commands:"
echo "  sudo systemctl status morning-dust     # is it running?"
echo "  journalctl -u morning-dust -f          # live logs"
echo "  sudo systemctl restart morning-dust    # after a code change"