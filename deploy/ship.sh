#!/usr/bin/env bash
# Deploys AvisaBus to the Raspberry Pi (deployment_rpi AC-13). Run it on the Mac, from anywhere.
#
#   deploy/ship.sh                       build, copy the images, sync compose.yaml and nginx/,
#                                        start the new version and run deploy/smoke.sh
#   deploy/ship.sh --rollback <version>  go back to a version already on the Raspberry Pi
#
# Configuration: deploy/ship.env (RPI_HOST, RPI_DIR, PUBLIC_URL, NPM_NETWORK); see
# deploy/ship.env.example. deploy/.env.prod is never copied: it lives only on the Raspberry Pi.
# Every version stays on the Raspberry Pi with its tag (the previous one is never removed).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
SHIP_ENV="${SHIP_ENV:-$HERE/ship.env}"
IMAGES=(avisabus-backend avisabus-web)

info() { printf '==> %s\n' "$*"; }
warn() { printf 'AVISO %s\n' "$*" >&2; }
die()  { printf 'ERROR %s\n' "$*" >&2; exit 1; }
usage() { sed -n '4,7p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

[[ -f "$SHIP_ENV" ]] || die "falta $SHIP_ENV (copia deploy/ship.env.example y rellénalo)"
# shellcheck source=/dev/null
source "$SHIP_ENV"
: "${RPI_HOST:?falta RPI_HOST en ship.env}" "${RPI_DIR:?falta RPI_DIR en ship.env}"
: "${PUBLIC_URL:?falta PUBLIC_URL en ship.env}"
NPM_NETWORK="${NPM_NETWORK:-npm_default}"
[[ "$RPI_DIR" == /* && "$RPI_DIR" != *[[:space:]\'\"]* ]] || die "RPI_DIR debe ser una ruta absoluta sin espacios ni comillas"

on_rpi() { ssh "$RPI_HOST" "cd '$RPI_DIR' && $*"; }

require_remote_config() {
  on_rpi "test -f .env.prod" \
    || die "falta $RPI_DIR/.env.prod en la Raspberry (créalo desde deploy/.env.prod.example; ver deploy/README.md)"
}

# The version in use is pinned in $RPI_DIR/.env, which `docker compose` reads by itself, so every
# later command there (restart, run, gtfs-update.sh) uses the same images.
pin_version() {
  on_rpi "printf 'AVISABUS_VERSION=%s\nNPM_NETWORK=%s\n' '$1' '$NPM_NETWORK' > .env"
}

current_version() { on_rpi "sed -n 's/^AVISABUS_VERSION=//p' .env 2>/dev/null" || true; }

start() {
  info "arrancando la versión $1"
  on_rpi "docker compose up -d --remove-orphans --wait --wait-timeout 180" \
    || die "el servicio no arranca sano; mira los logs: ssh $RPI_HOST 'cd $RPI_DIR && docker compose logs --tail 100'"
}

smoke() {
  info "comprobando $PUBLIC_URL"
  "$HERE/smoke.sh" "$PUBLIC_URL"
}

deploy() {
  local version previous
  version="$(git -C "$ROOT" describe --tags --always --dirty)"
  [[ "$version" != *-dirty ]] || warn "hay cambios sin commit: la versión será $version"

  info "construyendo $version (linux/arm64)"
  # The images do not read the production configuration: the template is enough to build.
  (cd "$HERE" && AVISABUS_ENV_FILE=.env.prod.example AVISABUS_VERSION="$version" \
    docker compose -f compose.yaml build)

  ssh "$RPI_HOST" "mkdir -p '$RPI_DIR/data/gtfs' '$RPI_DIR/nginx'"
  require_remote_config
  previous="$(current_version)"

  info "copiando las imágenes a $RPI_HOST"
  docker save --platform linux/arm64 "${IMAGES[@]/%/:$version}" | gzip | ssh "$RPI_HOST" "gunzip | docker load"

  info "sincronizando compose.yaml y nginx/ (nunca .env.prod)"
  rsync -a "$HERE/compose.yaml" "$RPI_HOST:$RPI_DIR/compose.yaml"
  rsync -a --delete "$HERE/nginx/" "$RPI_HOST:$RPI_DIR/nginx/"

  pin_version "$version"
  # The backend runs as uid 10001: data/ must be its own (data/gtfs stays the SSH user's, so
  # gtfs-update.sh can copy the zip there). Idempotent.
  on_rpi "docker compose run --rm --no-deps -T --user 0 --entrypoint chown backend 10001:10001 /data"
  start "$version"
  smoke
  if [[ -n "$previous" && "$previous" != "$version" ]]; then
    info "versión anterior: $previous (para volver: deploy/ship.sh --rollback $previous)"
  fi
  info "desplegada la versión $version"
}

rollback() {
  local version="$1" image
  require_remote_config
  for image in "${IMAGES[@]}"; do
    on_rpi "docker image inspect '$image:$version' >/dev/null 2>&1" \
      || die "la imagen $image:$version no está en la Raspberry (docker image ls avisabus-backend)"
  done
  info "volviendo de $(current_version) a $version"
  pin_version "$version"
  start "$version"
  smoke
  info "en servicio la versión $version"
}

case "${1:-}" in
  "") deploy ;;
  --rollback) [[ $# -eq 2 && -n "$2" ]] || usage; rollback "$2" ;;
  *) usage ;;
esac
