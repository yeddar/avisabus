#!/usr/bin/env bash
# Renews the GTFS feed on the Raspberry Pi (deployment_rpi AC-12). Run it on the Mac.
#
#   deploy/gtfs-update.sh <zip>    e.g. deploy/gtfs-update.sh ~/Downloads/google_transit.zip
#
# Copies the zip to $RPI_DIR/data/gtfs/incoming.zip, imports it with the CLI inside the backend
# container, compacts the database (VACUUM) and restarts the backend. If the import fails, it
# stops with an error and does not restart: the active version does not change.
# Configuration: deploy/ship.env (RPI_HOST, RPI_DIR), as deploy/ship.sh.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHIP_ENV="${SHIP_ENV:-$HERE/ship.env}"

info() { printf '==> %s\n' "$*"; }
warn() { printf 'AVISO %s\n' "$*" >&2; }
die()  { printf 'ERROR %s\n' "$*" >&2; exit 1; }

[[ $# -eq 1 ]] || { sed -n '4,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
ZIP="$1"
[[ -f "$ZIP" ]] || die "no existe $ZIP"
[[ -f "$SHIP_ENV" ]] || die "falta $SHIP_ENV (copia deploy/ship.env.example y rellénalo)"
# shellcheck source=/dev/null
source "$SHIP_ENV"
: "${RPI_HOST:?falta RPI_HOST en ship.env}" "${RPI_DIR:?falta RPI_DIR en ship.env}"
[[ "$RPI_DIR" == /* && "$RPI_DIR" != *[[:space:]\'\"]* ]] || die "RPI_DIR debe ser una ruta absoluta sin espacios ni comillas"

on_rpi() { ssh "$RPI_HOST" "cd '$RPI_DIR' && $*"; }

info "copiando $ZIP a $RPI_HOST"
ssh "$RPI_HOST" "mkdir -p '$RPI_DIR/data/gtfs'"
scp -q "$ZIP" "$RPI_HOST:$RPI_DIR/data/gtfs/incoming.zip"

info "importando el feed"
on_rpi "docker compose run --rm -T backend avisabus gtfs import /data/gtfs/incoming.zip" \
  || die "la importación ha fallado: la versión activa no cambia y el backend no se reinicia"

info "compactando la base de datos (VACUUM)"
# The database is the one of AVISABUS_DATABASE_URL (sqlite:////data/avisabus.sqlite).
on_rpi "docker compose run --rm -T backend python -" <<'PY' || warn "VACUUM ha fallado (el feed ya está importado); se reinicia igualmente"
import sqlite3

from avisabus.config import Settings

path = Settings().database_url.removeprefix("sqlite:///")
connection = sqlite3.connect(path)
connection.execute("VACUUM")
connection.close()
print(f"VACUUM: {path}")
PY

info "reiniciando el backend"
on_rpi "docker compose restart backend"
on_rpi "docker compose ps backend"
info "feed renovado; compruébalo con: deploy/smoke.sh <url> (GTFS y días que quedan)"
