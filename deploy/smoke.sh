#!/usr/bin/env bash
# Checks a deployed AvisaBus from outside (deployment_rpi AC-14). Needs curl and python3.
#
#   deploy/smoke.sh <url>               e.g. deploy/smoke.sh https://avisabus.example
#   deploy/smoke.sh <url> --ip-limit    also checks that a fake X-Forwarded-For does not change
#                                       the limit per IP (AC-05). It makes failed driver logins
#                                       until the limit answers 429: YOUR address cannot log in
#                                       as a driver for AVISABUS_DRIVER_LOGIN_BLOCK_MIN minutes.
#
# Exits with 0 when every check passes; otherwise prints each failure and exits with 1.
set -euo pipefail

usage() { sed -n '4,9p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || usage
BASE="${1%/}"
IP_LIMIT=false
case "${2:-}" in
  "") ;;
  --ip-limit) IP_LIMIT=true ;;
  *) usage ;;
esac
command -v curl >/dev/null || { echo "smoke: falta curl" >&2; exit 2; }
command -v python3 >/dev/null || { echo "smoke: falta python3" >&2; exit 2; }

TIMEOUT=10
FAILURES=()
ok()   { printf 'OK    %s\n' "$*"; }
bad()  { printf 'FALLO %s\n' "$*"; FAILURES+=("$*"); }
warn() { printf 'AVISO %s\n' "$*"; }

# headers <path> [curl options…]: status line and headers (lowercase names) of a GET.
headers() {
  local path="$1"; shift
  curl -sS -o /dev/null -D - --max-time "$TIMEOUT" "$@" "$BASE$path" | tr -d '\r'
}
status_of() { head -n 1 <<<"$1" | awk '{print $2}'; }
# header_of <headers> <name>: value of the header (name in lowercase).
header_of() { awk -v name="$2" 'BEGIN { IGNORECASE = 1 } tolower($0) ~ "^" name ":" {
  sub(/^[^:]*:[ \t]*/, ""); print; exit }' <<<"$1"; }

# expect_header <label> <headers> <name> <expected value>
expect_header() {
  local value
  value="$(header_of "$2" "$3")"
  if [[ "$value" == "$4" ]]; then ok "$1: $3: $value"; else bad "$1: $3 es '$value' (se esperaba '$4')"; fi
}

# --- /api/v1/health: status and version ------------------------------------------------------------
if health="$(curl -sS --fail --max-time "$TIMEOUT" "$BASE/api/v1/health")"; then
  if summary="$(python3 -c '
import json, sys
body = json.loads(sys.argv[1])
status, version, gtfs = body["status"], body["version"], body.get("gtfs")
assert status in ("ok", "degraded") and version, body
feed = "sin feed GTFS" if gtfs is None else "GTFS {feed_version}, caduca el {feed_end_date} ({days_left} días)".format(**gtfs)
print(f"{status}|{version}|{feed}")' "$health" 2>/dev/null)"; then
    IFS='|' read -r status version feed <<<"$summary"
    ok "/api/v1/health: status $status, versión $version, $feed"
    [[ "$status" == "ok" ]] || warn "/api/v1/health: status degraded (sin feed GTFS o caducado: deploy/gtfs-update.sh)"
  else
    bad "/api/v1/health: respuesta sin status o versión: $health"
  fi
else
  bad "/api/v1/health no responde 200"
fi

# --- Home page and SPA fallback -----------------------------------------------------------------------
home="$(headers /)"
if [[ "$(status_of "$home")" == 200 && "$(header_of "$home" content-type)" == text/html* ]]; then
  ok "/: 200 text/html"
else
  bad "/: $(status_of "$home") $(header_of "$home" content-type) (se esperaba 200 text/html)"
fi
driver="$(headers /driver)"
if [[ "$(status_of "$driver")" == 200 && "$(header_of "$driver" content-type)" == text/html* ]]; then
  ok "/driver: 200 text/html (fallback de la SPA)"
else
  bad "/driver: $(status_of "$driver") (se esperaba 200 text/html del fallback de la SPA)"
fi
missing="$(headers /no-such-file.js)"
if [[ "$(status_of "$missing")" == 404 ]]; then
  ok "/no-such-file.js: 404 (sin fallback para ficheros)"
else
  bad "/no-such-file.js: $(status_of "$missing") (se esperaba 404, no el fallback)"
fi

# --- Headers (AC-06) ------------------------------------------------------------------------------------
for path in / /api/v1/health; do
  h="$(headers "$path")"
  expect_header "$path" "$h" x-content-type-options "nosniff"
  expect_header "$path" "$h" referrer-policy "strict-origin-when-cross-origin"
  expect_header "$path" "$h" permissions-policy "geolocation=(self), camera=(), microphone=()"
  expect_header "$path" "$h" strict-transport-security "max-age=15552000"
done
for path in / /index.html /sw.js /manifest.webmanifest; do
  expect_header "$path" "$(headers "$path")" cache-control "no-cache"
done
asset="$(curl -sS --max-time "$TIMEOUT" "$BASE/" | grep -oE '/assets/[^"]+\.js' | head -n 1 || true)"
if [[ -n "$asset" ]]; then
  h="$(headers "$asset" -H 'Accept-Encoding: gzip')"
  expect_header "$asset" "$h" cache-control "public, max-age=31536000, immutable"
  expect_header "$asset" "$h" content-encoding "gzip"
else
  bad "/: no enlaza ningún /assets/*.js"
fi

# --- WebSocket handshake ----------------------------------------------------------------------------------
ws="$(curl -sS -i -N --http1.1 --max-time 3 \
  -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13' \
  -H 'Sec-WebSocket-Key: c21va2UtYXZpc2FidXMtMQ==' "$BASE/ws/passenger" 2>/dev/null | tr -d '\r' || true)"
if [[ "$(status_of "$ws")" == 101 ]]; then
  ok "/ws/passenger: 101 Switching Protocols"
else
  bad "/ws/passenger: handshake $(status_of "$ws") (se esperaba 101)"
fi

# --- Limit per IP with a fake X-Forwarded-For (AC-05, optional) --------------------------------------------
if $IP_LIMIT; then
  limited=false
  for attempt in $(seq 1 12); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
      -H "X-Forwarded-For: 198.51.100.$attempt" -H 'Content-Type: application/json' \
      -d '{"code": "00000000"}' "$BASE/api/v1/driver/sessions")"
    if [[ "$code" == 429 ]]; then limited=true; break; fi
  done
  if $limited; then
    ok "límite por IP: 429 tras $attempt intentos con X-Forwarded-For distintos (no se falsea)"
  else
    bad "límite por IP: ningún 429 en 12 intentos con X-Forwarded-For distintos (¿se acepta la cabecera del cliente?)"
  fi
fi

echo
if ((${#FAILURES[@]})); then
  printf 'smoke: %d comprobación(es) fallida(s)\n' "${#FAILURES[@]}"
  exit 1
fi
echo "smoke: todo en verde ($BASE)"
