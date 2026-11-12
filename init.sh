#!/usr/bin/env bash
# AvisaBus harness entry point.
#   ./init.sh setup          Install backend and frontend dependencies
#   ./init.sh verify [--e2e] Run every quality gate (see docs/verification.md)
#   ./init.sh dev            Run backend (:8000) and frontend (:5173) for development
#   ./init.sh status         Show feature status from feature_list.json
#   ./init.sh verify-deploy  Build and inspect the production images (needs Docker; deploy/)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

c_ok=$'\033[32m'; c_err=$'\033[31m'; c_warn=$'\033[33m'; c_off=$'\033[0m'
info()  { printf '%s\n' "==> $*"; }
warn()  { printf '%s\n' "${c_warn}WARN${c_off} $*"; }
fail()  { printf '%s\n' "${c_err}FAIL${c_off} $*"; }
pass()  { printf '%s\n' "${c_ok}OK${c_off}   $*"; }

require() { command -v "$1" >/dev/null 2>&1 || { fail "'$1' no está instalado"; exit 1; }; }

FAILED=()
run_step() {  # run_step <label> <dir> <command...>
  local label="$1" dir="$2"; shift 2
  info "$label"
  if (cd "$dir" && "$@"); then pass "$label"; else fail "$label"; FAILED+=("$label"); fi
}

cmd_setup() {
  require python3
  if [[ -d "$BACKEND" ]]; then
    require uv
    info "backend: uv sync"; (cd "$BACKEND" && uv sync)
  else
    warn "backend/ no existe todavía (lo crea la feature project_scaffold)"
  fi
  if [[ -d "$FRONTEND" ]]; then
    require npm
    info "frontend: npm ci"; (cd "$FRONTEND" && npm ci)
  else
    warn "frontend/ no existe todavía (lo crea la feature project_scaffold)"
  fi
  mkdir -p "$ROOT/data/gtfs"
  [[ -f "$ROOT/.env" || ! -f "$ROOT/.env.example" ]] || { cp "$ROOT/.env.example" "$ROOT/.env"; info "creado .env desde .env.example"; }
}

cmd_verify() {
  local e2e=false
  [[ "${1:-}" == "--e2e" ]] && e2e=true

  if [[ -d "$BACKEND" ]]; then
    run_step "backend: format"       "$BACKEND" uv run ruff format --check .
    run_step "backend: lint"         "$BACKEND" uv run ruff check .
    run_step "backend: types"        "$BACKEND" uv run mypy
    run_step "backend: architecture" "$BACKEND" uv run lint-imports
    run_step "backend: tests"        "$BACKEND" uv run pytest
  else
    warn "backend/ no existe: se omiten sus comprobaciones"
  fi

  if [[ -d "$FRONTEND" ]]; then
    run_step "frontend: format" "$FRONTEND" npm run --silent format:check
    run_step "frontend: lint"   "$FRONTEND" npm run --silent lint
    run_step "frontend: types"  "$FRONTEND" npm run --silent typecheck
    run_step "frontend: tests"  "$FRONTEND" npm run --silent test
    # Build and, on that fresh dist/, the initial JS budget (never on an old build).
    run_step "frontend: build + bundle" "$FRONTEND" npm run --silent test:bundle
    if $e2e; then
      run_step "frontend: e2e + a11y" "$FRONTEND" npm run --silent e2e
    fi
  else
    warn "frontend/ no existe: se omiten sus comprobaciones"
  fi

  run_step "harness: feature_list.json" "$ROOT" python3 scripts/check_traceability.py --schema-only
  run_step "harness: trazabilidad AC→test" "$ROOT" python3 scripts/check_traceability.py

  echo
  if ((${#FAILED[@]})); then
    fail "verify: ${#FAILED[@]} paso(s) fallido(s): ${FAILED[*]}"
    exit 1
  fi
  pass "verify: todo en verde"
}

cmd_verify_deploy() {  # deployment_rpi design §8: not part of `verify` (it needs Docker)
  require docker
  require python3
  docker info >/dev/null 2>&1 || { fail "Docker no responde (¿está arrancado?)"; exit 1; }
  local deploy="$ROOT/deploy" tmp version
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  version="$(git -C "$ROOT" describe --tags --always --dirty)"
  # A throwaway production configuration, from the template, only to validate and build.
  sed -e "s|^AVISABUS_STOP_TOKEN_SECRET=.*|AVISABUS_STOP_TOKEN_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')|" \
      -e 's|^AVISABUS_SAE_CONTACT=.*|AVISABUS_SAE_CONTACT=verify-deploy@example.invalid|' \
      -e 's|^AVISABUS_PUBLIC_BASE_URL=.*|AVISABUS_PUBLIC_BASE_URL=https://avisabus.example.invalid|' \
      "$deploy/.env.prod.example" > "$tmp/.env.prod"
  export AVISABUS_ENV_FILE="$tmp/.env.prod" AVISABUS_VERSION="$version"
  info "versión de las imágenes: $version"

  run_step "deploy: compose config" "$deploy" docker compose -f compose.yaml config -q
  run_step "deploy: compose (AC-03)" "$deploy" _check_compose
  run_step "deploy: build linux/arm64 (AC-01)" "$deploy" docker compose -f compose.yaml build
  run_step "deploy: etiquetas versión y latest (AC-01)" "$deploy" _check_tags "$version"
  run_step "deploy: imagen backend (AC-02)" "$deploy" _check_backend_image "$version"
  run_step "deploy: configuración prod incompleta no arranca (AC-07)" "$deploy" _check_prod_refuses "$version"
  run_step "deploy: imagen web (AC-04)" "$deploy" _check_web_image "$version"
  run_step "deploy: nginx -t (AC-04)" "$deploy" docker run --rm "avisabus-web:$version" nginx -t -q

  echo
  if ((${#FAILED[@]})); then
    fail "verify-deploy: ${#FAILED[@]} paso(s) fallido(s): ${FAILED[*]}"
    exit 1
  fi
  pass "verify-deploy: todo en verde"
}

_check_compose() {
  docker compose -f compose.yaml config --format json | python3 -c '
import json, sys
c = json.load(sys.stdin)
s, errors = c["services"], []
def expect(cond, what):
    cond or errors.append(what)
for name in ("backend", "web"):
    svc = s[name]
    expect(svc.get("restart") == "unless-stopped", f"{name}: restart unless-stopped")
    expect(svc.get("platform") == "linux/arm64", f"{name}: platform linux/arm64")
    expect(not svc.get("ports"), f"{name}: no publica puertos en el anfitrión")
    log = svc.get("logging", {})
    expect(log.get("driver") == "json-file" and log.get("options") == {"max-size": "10m", "max-file": "3"},
           f"{name}: logs json-file 10m x 3")
expect(set(s["backend"]["networks"]) == {"internal"}, "backend: solo la red interna")
expect(set(s["web"]["networks"]) == {"internal", "npm"}, "web: red interna y red de NPM")
expect("/api/v1/health" in " ".join(s["backend"]["healthcheck"]["test"]), "backend: healthcheck de /api/v1/health")
expect(s["web"]["depends_on"]["backend"]["condition"] == "service_healthy", "web: depende de backend sano")
expect(any(v["target"] == "/data" for v in s["backend"]["volumes"]), "backend: volumen /data")
npm = c["networks"]["npm"]
expect(npm.get("external") is True and npm.get("name"), "red npm externa con nombre (NPM_NETWORK)")
for e in errors:
    print("  -", e)
sys.exit(1 if errors else 0)
'
}

_check_tags() {
  local version="$1" name ok=0
  for name in avisabus-backend avisabus-web; do
    if [[ "$(docker image inspect -f '{{.Id}}' "$name:$version")" != "$(docker image inspect -f '{{.Id}}' "$name:latest")" ]]; then
      echo "  - $name:$version y $name:latest no son la misma imagen"; ok=1
    fi
  done
  return $ok
}

_check_backend_image() {
  local image="avisabus-backend:$1" user arch exposed cmd
  user="$(docker image inspect -f '{{.Config.User}}' "$image")"
  arch="$(docker image inspect -f '{{.Os}}/{{.Architecture}}' "$image")"
  exposed="$(docker image inspect -f '{{json .Config.ExposedPorts}}' "$image")"
  cmd="$(docker image inspect -f '{{join .Config.Cmd " "}}' "$image")"
  local ok=0
  [[ -n "$user" && "$user" != "root" && "$user" != "0" ]] || { echo "  - usuario: '$user' (debe ser no privilegiado)"; ok=1; }
  [[ "$arch" == "linux/arm64" ]] || { echo "  - plataforma: $arch"; ok=1; }
  [[ "$exposed" == "null" || "$exposed" == "{}" ]] || { echo "  - puertos expuestos: $exposed"; ok=1; }
  [[ "$cmd" == "uvicorn avisabus.main:app "* && "$cmd" == *"--proxy-headers"* && "$cmd" != *"--workers"* ]] \
    || { echo "  - CMD: $cmd"; ok=1; }
  docker run --rm --entrypoint sh "$image" -c '
    test -f /app/replay/stop_508_peak/session.json || { echo "  - falta la grabación stop_508_peak"; exit 1; }
    test "$(id -u)" != 0 || { echo "  - se ejecuta como root"; exit 1; }
    python -c "
import importlib.util, sys
dev = [m for m in (\"pytest\", \"ruff\", \"mypy\", \"hypothesis\", \"import_linter\") if importlib.util.find_spec(m)]
dev and print(\"  - dependencias de desarrollo:\", dev)
sys.exit(1 if dev else 0)"' || ok=1
  return $ok
}

_check_prod_refuses() {  # the image runs in prod by default: without contact nor https it stops
  local image="avisabus-backend:$1" secret out
  secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  if out="$(docker run --rm -e AVISABUS_STOP_TOKEN_SECRET="$secret" "$image" avisabus gtfs info 2>&1)"; then
    echo "  - la CLI arrancó sin AVISABUS_SAE_CONTACT ni URL https"; return 1
  fi
  [[ "$out" == *AVISABUS_SAE_CONTACT* && "$out" == *AVISABUS_PUBLIC_BASE_URL* ]] \
    || { echo "  - el error no nombra las variables"; return 1; }
  [[ "$out" != *"$secret"* ]] || { echo "  - el error muestra el secreto"; return 1; }
}

_check_web_image() {
  local image="avisabus-web:$1" arch
  arch="$(docker image inspect -f '{{.Os}}/{{.Architecture}}' "$image")"
  [[ "$arch" == "linux/arm64" ]] || { echo "  - plataforma: $arch"; return 1; }
  docker run --rm --entrypoint sh "$image" -c '
    for f in index.html sw.js manifest.webmanifest; do
      test -f "/usr/share/nginx/html/$f" || { echo "  - falta $f"; exit 1; }
    done'
}

cmd_dev() {
  [[ -d "$BACKEND" && -d "$FRONTEND" ]] || { fail "faltan backend/ o frontend/ (feature project_scaffold)"; exit 1; }
  trap 'kill 0' EXIT INT TERM
  (cd "$BACKEND" && uv run uvicorn avisabus.main:app --reload --port 8000) &
  (cd "$FRONTEND" && npm run dev) &
  wait
}

cmd_status() {
  python3 - "$ROOT/feature_list.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
feats = {f["id"]: f for f in data["features"]}
print(f"{'#':>2}  {'feature':<22} {'blq':>3}  {'estado':<18} {'deps listas':<11} ciclos")
for f in sorted(data["features"], key=lambda f: f["order"]):
    ready = all(feats[d]["status"] == "done" for d in f["depends_on"])
    print(f"{f['order']:>2}  {f['id']:<22} {f['block']:>3}  {f['status']:<18} {'sí' if ready else 'no':<11} {f['review_cycles']}")
done = sum(f["status"] == "done" for f in data["features"])
print(f"\n{done}/{len(data['features'])} features terminadas")
PY
}

case "${1:-help}" in
  setup)  cmd_setup ;;
  verify) shift; cmd_verify "${1:-}" ;;
  dev)    cmd_dev ;;
  status) cmd_status ;;
  verify-deploy) cmd_verify_deploy ;;
  *)      sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
