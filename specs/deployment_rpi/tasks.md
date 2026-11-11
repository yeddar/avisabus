# Despliegue en Raspberry Pi — tasks

> Feature: `deployment_rpi` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RNF-06, RNF-07, RNF-11, RNF-13, RNF-14 · Casos de uso: — (operación) · Depende de: project_scaffold

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Validación de producción en `Settings` y plantilla `deploy/.env.prod.example`.
  - AC: deployment_rpi.AC-07, AC-08
  - Ficheros: `backend/src/avisabus/config.py`, `deploy/.env.prod.example`, `.gitignore`, `backend/tests/unit/test_config_prod.py`, `backend/tests/unit/test_env_example.py`
  - Verificación: `cd backend && uv run pytest tests/unit/test_config_prod.py tests/unit/test_env_example.py`

- [ ] **T-02** — Máscara de IP y de consulta en todos los logs de acceso.
  - AC: deployment_rpi.AC-09
  - Ficheros: `backend/src/avisabus/adapters/inbound/http/access_log.py`, `backend/src/avisabus/logging.py`, `backend/tests/integration/test_access_log_privacy.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_access_log_privacy.py`

- [ ] **T-03** — Estado del GTFS en `/health` y `GtfsExpiryWatcher`.
  - AC: deployment_rpi.AC-10, AC-11
  - Ficheros: `backend/src/avisabus/adapters/inbound/http/routes/health.py`, `backend/src/avisabus/background/gtfs_tasks.py`, `backend/src/avisabus/adapters/inbound/http/{app,container}.py`, tests
  - Verificación: `cd backend && uv run pytest -k "health or gtfs_expiry"`

- [ ] **T-04** — Precarga de `woff2` en el *service worker* y prueba sin conexión.
  - AC: deployment_rpi.AC-15
  - Ficheros: `frontend/vite.config.ts`, `frontend/src/__tests__/pwa-manifest.test.ts`, `frontend/e2e/offline-font.spec.ts`
  - Verificación: `cd frontend && npm run test -- pwa-manifest && npm run e2e`

- [ ] **T-05** — `Dockerfile` de `backend` y `web`, `.dockerignore`, `deploy/compose.yaml`,
  `deploy/nginx/web.conf` e `init.sh verify-deploy`.
  - AC: deployment_rpi.AC-01, AC-02, AC-03, AC-04, AC-05, AC-06
  - Ficheros: `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore`, `deploy/compose.yaml`, `deploy/nginx/web.conf`, `init.sh`
  - Verificación: `./init.sh verify-deploy`

- [ ] **T-06** — `ship.sh` (con `--rollback`), `gtfs-update.sh`, `smoke.sh` y `ship.env.example`.
  - AC: deployment_rpi.AC-12, AC-13, AC-14
  - Ficheros: `deploy/{ship,gtfs-update,smoke}.sh`, `deploy/ship.env.example`, `.gitignore`
  - Verificación: `shellcheck deploy/*.sh` (si está instalado) y `deploy/smoke.sh http://localhost:<puerto>` contra `docker compose up` local con una red `npm` creada a mano

- [ ] **T-07** — Guía `deploy/README.md`.
  - AC: deployment_rpi.AC-16
  - Ficheros: `deploy/README.md`, `README.md` (enlace)
  - Verificación: revisión

- [ ] **T-08** — Verificación completa.
  - Verificación: `./init.sh verify --e2e` y `./init.sh verify-deploy`
