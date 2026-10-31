#!/usr/bin/env bash
# AvisaBus harness entry point.
#   ./init.sh setup          Install backend and frontend dependencies
#   ./init.sh verify [--e2e] Run every quality gate (see docs/verification.md)
#   ./init.sh dev            Run backend (:8000) and frontend (:5173) for development
#   ./init.sh status         Show feature status from feature_list.json
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
    run_step "frontend: build"  "$FRONTEND" npm run --silent build
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
  *)      sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
