#!/usr/bin/env bash
# Start the FastAPI backend standalone, smoke-test it, stop it.
#   bash api-smoke.sh [extra-route ...]     e.g. bash api-smoke.sh /python/info
# Env: RLGYM_SMOKE_PORT (default 8123). Log: $TMP/rlgym-run/api.log
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SERVER=$(cd "$HERE/../../../../rlgym-server" && pwd)
PY="$SERVER/.venv/Scripts/python.exe"; [ -x "$PY" ] || PY="$SERVER/.venv/bin/python"
PORT=${RLGYM_SMOKE_PORT:-8123}
TOKEN=smoke
OUT="${TMP:-/tmp}/rlgym-run"; mkdir -p "$OUT/data"
B="http://127.0.0.1:$PORT"

if curl -s -o /dev/null "$B/health"; then echo "port $PORT already in use - set RLGYM_SMOKE_PORT"; exit 1; fi

(cd "$SERVER" && RLGYM_GUI_PORT=$PORT RLGYM_GUI_TOKEN=$TOKEN RLGYM_GUI_DATA_DIR="$OUT/data" RLGYM_GUI_VERSION=smoke \
  exec "$PY" main.py > "$OUT/api.log" 2>&1) &
for _ in $(seq 1 40); do curl -sf -H "X-Api-Token: $TOKEN" "$B/health" >/dev/null && break; sleep 0.25; done

req() { printf '%-28s ' "$1"; shift; curl -s -w ' [%{http_code}]\n' "$@"; }
req "GET /health"            -H "X-Api-Token: $TOKEN" "$B/health"
req "GET /version"           -H "X-Api-Token: $TOKEN" "$B/version"
req "GET /health (no token)" "$B/health"
for r in "$@"; do req "GET $r" -H "X-Api-Token: $TOKEN" "$B$r"; done

printf '%-28s ' "openapi.json in sync"
curl -s -H "X-Api-Token: $TOKEN" "$B/openapi.json" | (cd "$SERVER" && "$PY" -c "
import json, sys
live = json.load(sys.stdin)['paths']; f = json.load(open('openapi.json'))['paths']
print('yes' if live == f else f'NO - live only: {sorted(set(live) - set(f))}, file only: {sorted(set(f) - set(live))}')")

# Stop: kill whatever listens on the port (the venv launcher on Windows spawns a child python).
if command -v powershell >/dev/null; then
  powershell -NoProfile -c "Get-NetTCPConnection -LocalPort $PORT -State Listen -EA SilentlyContinue | % { Stop-Process -Id \$_.OwningProcess -Force }"
else
  kill $(lsof -ti:"$PORT" -sTCP:LISTEN) 2>/dev/null
fi
wait 2>/dev/null
echo "--- api.log ($OUT/api.log)"; cat "$OUT/api.log"
