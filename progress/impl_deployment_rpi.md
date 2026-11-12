# Implementación: deployment_rpi
Spec: specs/deployment_rpi/ (v1.0, APPROVED, PR #60) · Ciclo de revisión: 0 · Rama: `feat/deployment_rpi`
(apilada sobre `feat/passenger_map_view-v1.3`, PR #65). Exploración: no necesaria (`tasks.md`).

## Estado
T-01 a T-08 terminadas. `CI=1 ./init.sh verify --e2e` y `./init.sh verify-deploy` en verde (ver
"Verificación"). Quedan para el CP-6, en la Raspberry, las verificaciones manuales de AC-04 (1 h
de WebSocket), AC-05, AC-06, AC-12, AC-13, AC-14 y AC-16: no se ha ejecutado nada contra la
Raspberry ni por SSH.

## Tareas
- [x] T-01 — Validación de producción en `Settings` y `deploy/.env.prod.example` (commit ad92ef5)
- [x] T-02 — Máscara de IP y de consulta en todos los logs de acceso (commit e059d0d)
- [x] T-03 — Estado del GTFS en `/health` y `GtfsExpiryWatcher` (commit 4227348)
- [x] T-04 — Precarga de `woff2` en el *service worker* y prueba sin conexión (commit d065d9c)
- [x] T-05 — Dockerfiles, `.dockerignore`, `compose.yaml`, `nginx/web.conf`, `init.sh verify-deploy` (commit 6f4d47b)
- [x] T-06 — `ship.sh` (con `--rollback`), `gtfs-update.sh`, `smoke.sh`, `ship.env.example` (commit 46a8009)
- [x] T-07 — Guía `deploy/README.md` y enlace en `README.md` (commit 28b2821)
- [x] T-08 — Verificación completa (corrección de `verify-deploy`: commit 360f342)

## Matriz AC → evidencia
| AC | Evidencia |
|---|---|
| AC-01 | `verify-deploy`: build `linux/arm64`, etiquetas `<git describe>` y `latest` (misma imagen) |
| AC-02 | `verify-deploy`: usuario ≠ root (`avisabus`, uid 10001), sin `ExposedPorts`, `arm64`, `CMD` uvicorn sin `--workers` y con `--proxy-headers`, sin `pytest/ruff/mypy/hypothesis/import_linter`, `/app/replay/stop_508_peak/session.json`; volumen `/data` |
| AC-03 | `verify-deploy`: `compose config -q` y comprobación del JSON (restart, logs 10m×3, redes, sin `ports`, healthcheck, `depends_on: service_healthy`, red NPM externa); contraprueba con una copia alterada: falla |
| AC-04 | `verify-deploy`: `nginx -t`; `smoke.sh` local: `/` y `/driver` (fallback), `/no-such-file.js` → 404, `/ws/passenger` → 101 |
| AC-05 | Local, con un nginx que hace de NPM: `smoke.sh --ip-limit` → 429 a los 6 intentos con `X-Forwarded-For` distintos; contraprueba contra `web` sin NPM: falla (por eso `web` no publica puertos) |
| AC-06 | `smoke.sh` local: las cuatro cabeceras en `/` y `/api/…`, `no-cache` en `/`, `/index.html`, `/sw.js`, `/manifest.webmanifest`, inmutable 1 año y `gzip` en `/assets/*.js` |
| AC-07 | `tests/unit/test_config_prod.py` (Settings y CLI) + `verify-deploy` (la imagen no arranca sin contacto ni https y no muestra el secreto) |
| AC-08 | `tests/unit/test_env_example.py` (todas las variables de `Settings`, valores de producción, `deploy/.env.prod` ignorado) |
| AC-09 | `tests/integration/test_access_log_privacy.py` (uvicorn real en *loopback* con `--proxy-headers`: `/health`, `/stops/508?t=`, `/arrivals?t=`, `/alerts`, `/alerts/mine`, `/p/508?t=`, `/ws/passenger?probe=`); en la pila local, ningún log del backend con IP ni consulta |
| AC-10 | `tests/integration/test_health.py`, `tests/integration/test_main_gtfs.py` |
| AC-11 | `tests/unit/test_gtfs_expiry_watcher.py` (`FakeClock`, `sleep` falso), `tests/integration/test_main_gtfs.py` |
| AC-12 | `gtfs-update.sh` probado en local con *shims* de `ssh`/`scp`/`rsync` (sin SSH): zip válido → importa, `VACUUM`, reinicia, `/health` ok; zip roto → código 1, sin reinicio, versión activa igual. Manual en CP-6 |
| AC-13 | `ship.sh` probado igual: construye, `docker load`, sincroniza, fija la versión, arranca sano y `smoke.sh` en verde; `--rollback d065d9c` en verde; `--rollback` a una versión ausente → error. Manual en CP-6 |
| AC-14 | `smoke.sh` contra la pila local (ver AC-04/AC-06), código 1 y motivo si algo falla (comprobado con el 400 inicial del handshake y la contraprueba de AC-05) |
| AC-15 | `src/__tests__/pwa-manifest.test.ts` + `e2e/offline-font.spec.ts` (3 perfiles; rojo en los 3 sin el cambio) |
| AC-16 | `deploy/README.md` (revisión + CP-6) |

## Decisiones locales
- **T-01:** un contacto solo con espacios cuenta como vacío; la URL pública debe ser `https://`
  con *host* (sin distinguir mayúsculas en el esquema); un único `ConfigurationError` nombra todas
  las variables incorrectas, sin valores. El validador nuevo va después del del secreto, así que
  los tests de `stop_tokens_qr.AC-04` siguen viendo su mensaje. Consecuencia de AC-07: se añadió el
  contacto y/o la URL `https://` a cuatro tests que creaban `Settings` en `prod`
  (`test_settings.py`, `test_settings_env_file.py`, `test_settings_stop_token.py`,
  `test_sae_compose.py`), y en `.env.example` se indica que esas dos variables son obligatorias en
  `prod`. `test_env_example.py` no existía (la comprobación de `.env.example` está en
  `test_settings.py`): se crea nuevo para la plantilla de producción.
- **T-02:** los filtros pasan a `ClientAddressFilter` (`uvicorn.access`) y `SocketAddressFilter`
  (líneas `WebSocket` de `uvicorn.error`), instalados siempre en `create_app` (idempotente);
  sustituyen a los de `/driver`. `logging.py` no cambia. Se adaptan los tests que afirmaban que
  las demás rutas conservaban la IP (`test_driver_api.py`, `test_driver_demand.py`), que ahora
  citan `deployment_rpi.AC-09`. El test real usa `enable_socket` + `allow_hosts(["127.0.0.1"])`
  y espera el arranque con un `asyncio.Event` (sin `sleep`); se excluyen de las aserciones los
  logs de los clientes del propio test (`httpx`, `websockets`).
- **T-03:** sin feed, `gtfs` es `null` (el objeto entero), lectura de "(`null` sin feed)".
  `create_app` recibe `gtfs: GtfsStatus | None` (red + reloj); sin él, `/health` informa de que
  no hay feed (`degraded`): el test de `project_scaffold.AC-10` pasa a usar una app con
  `gtfs_mini`. `gtfs.feed_expired` lleva `days_left` (negativo), `days_ago` y `end_date` (como el
  evento de la CLI); sin feed, el vigilante no registra nada. `days_left` se calcula en la ruta y
  en el vigilante con `Europe/Madrid` (adaptadores y `background` no pueden importarse entre sí).
  Cableado en `main.py` (necesario aunque `tasks.md` no lo liste) y test `test_main_gtfs.py`. Se
  regeneran `frontend/src/shared/api/openapi.json` y `schema.d.ts` (`npm run gen:api`).
- **T-04:** `globPatterns: ['**/*.{js,css,html,woff2}']` (sin los `woff`, que no usan los
  navegadores soportados). El e2e comprueba además que los `woff2` están en Cache Storage, porque
  en WebKit la recarga sin conexión pasaba sin el cambio (caché en memoria).
- **T-05:** imágenes base `python:3.12-slim`, `ghcr.io/astral-sh/uv:0.13.6`, `node:22-alpine`,
  `nginx:1.27-alpine`. `ENV AVISABUS_ENV=prod` en la imagen del backend (sin configuración, no
  arranca). Ruta del `env_file` configurable (`AVISABUS_ENV_FILE`, por defecto `.env.prod`,
  obligatorio) para construir y validar sin un `.env.prod` real; `build.tags` para `latest`.
  nginx: `resolver 127.0.0.11` y `proxy_pass` con variable (el backend puede recrearse con otra IP
  y `nginx -t` no necesita el backend); caché inmutable solo para `/assets/` y `workbox-*.js`
  (llevan *hash*), y `no-cache` + 404 para los demás ficheros con extensión (iconos,
  `registerSW.js`), en lugar del patrón por extensión de design §4, que haría inmutables ficheros
  sin *hash*; cabeceras en `nginx/security-headers.conf` incluido en cada `location`; HSTS sin
  `includeSubDomains`. `nginx/` no se monta en el contenedor (como en el esqueleto): va en la
  imagen y la copia de la Raspberry es de referencia.
- **T-06:** la versión en uso se fija en `<RPI_DIR>/.env` (`AVISABUS_VERSION`, `NPM_NETWORK`),
  que lee `docker compose`; `ship.sh` hace `chown 10001` de `data/` (no recursivo: `data/gtfs`
  sigue siendo del usuario de SSH para que `scp` pueda copiar el zip); `docker save --platform
  linux/arm64`. `VACUUM` con un script por la entrada estándar que usa
  `Settings().database_url`; si falla, aviso y se reinicia igualmente (el feed ya está
  importado). `smoke.sh`: `degraded` es un aviso, no un fallo (primer despliegue sin GTFS);
  `--ip-limit` es opcional porque bloquea la IP de quien lo ejecuta para el acceso de
  conductores durante 15 min.

## Observaciones (no bloqueantes)
- **Log de errores de nginx:** `access_log off` en `web`, pero el `error_log` de nginx (nivel
  `error`) incluye `client: <IP>` cuando falla el *upstream*. AC-09 habla del log de acceso; si la
  persona quiere evitarlo también ahí, bastaría `error_log /dev/stderr crit;` (perdiendo esos
  errores). Propuesta para el CP-6.
- **Logs TRACE de uvicorn:** `"%s:%d - HTTP connection made"` lleva la dirección, pero solo con
  nivel TRACE (por debajo de DEBUG), que no se usa.
- **`shellcheck`** no está instalado: los scripts se comprobaron con `bash -n` y ejecutándolos en
  local (bash 3.2 de macOS) con *shims* de `ssh`/`scp`/`rsync`.
- Para el sustituto de NPM se descargó `nginx:1.27-alpine` con `docker run` (la misma imagen
  base del build); se borró al terminar.
- e2e: `passenger_map_view.AC-09` (iphone, teclado del mapa) falló una vez y pasó en el reintento
  (*flaky*, ajeno a esta feature).

## Bloqueos
Ninguno.

## Verificación
`CI=1 ./init.sh verify --e2e` (2026-11-12, puerto 4173 libre), salida resumida:
```
OK backend: format · lint · types · architecture (2 contracts kept)
OK backend: tests — 1969 passed, 9 deselected; cobertura domain+application 99.66 %
OK frontend: format · lint · types
OK frontend: tests — 68 ficheros, 677 passed, 2 skipped
OK frontend: build + bundle — 5 passed
OK frontend: e2e + a11y — 134 passed, 12 skipped, 1 flaky (passenger_map_view.AC-09 iphone, pasa al reintentar)
OK harness: feature_list.json · trazabilidad AC→test
OK verify: todo en verde
```
`./init.sh verify-deploy` (imágenes `360f342`):
```
OK deploy: compose config · compose (AC-03) · build linux/arm64 (AC-01)
OK deploy: etiquetas versión y latest (AC-01) · imagen backend (AC-02)
OK deploy: configuración prod incompleta no arranca (AC-07) · imagen web (AC-04) · nginx -t (AC-04)
OK verify-deploy: todo en verde (código de salida 0)
```
Pila local de prueba (`compose up` con red `npm` creada a mano, fuente `replay`, sin peticiones a
EMT): `smoke.sh` en verde; contenedores, redes, volúmenes y directorio de prueba borrados al
terminar.
