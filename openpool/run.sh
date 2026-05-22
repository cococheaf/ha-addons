#!/usr/bin/with-contenv bash
set -euo pipefail

echo "[openpool] Starting OpenPool web app on port 8099"
exec python3 /app/server.py
