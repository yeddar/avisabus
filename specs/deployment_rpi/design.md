# Despliegue en Raspberry Pi — design

> Feature: `deployment_rpi` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RNF-06, RNF-07, RNF-11, RNF-13, RNF-14 · Casos de uso: — (operación) · Depende de: project_scaffold

## 1. Resumen

```
Mac (Apple Silicon)                              Raspberry Pi (arm64)
deploy/ship.sh ─ docker compose build ─┐         ┌─ NPM (existente): TLS, Proxy Host → web:80, WS on
                                       ├─ ssh ──▶│   └─(red NPM_NETWORK)─▶ web: nginx + build React
               docker save | docker load         │          └─(red interna)─▶ backend: uvicorn :8000
               rsync compose.yaml, nginx/        │                              └─ volumen /data (SQLite)
                                                 └─ deploy/smoke.sh https://<dominio>
```

## 2. Ficheros

| Fichero | Contenido |
|---|---|
| `backend/Dockerfile` | Multietapa: `python:3.12-slim` + `uv sync --frozen --no-dev`; usuario `avisabus` (uid 10001); copia `tests/fixtures/sae_recordings/stop_508_peak` a `/app/replay/stop_508_peak`; `CMD uvicorn avisabus.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*' --no-server-header` |
| `frontend/Dockerfile` | Multietapa: `node:22-alpine` (`npm ci`, `npm run build`) → `nginx:1.27-alpine` con `deploy/nginx/web.conf` |
| `.dockerignore` (raíz, `backend/`, `frontend/`) | Sin `node_modules`, `.venv`, `data/`, `.env*`, `e2e-captures/`, `test-results/` |
| `deploy/compose.yaml` | Servicios, redes, volumen, `platform: linux/arm64`, `env_file: .env.prod` |
| `deploy/nginx/web.conf` | SPA, *proxy* de `/api/` y `/ws/`, IP real, cabeceras, caché, `gzip` |
| `deploy/.env.prod.example` | Plantilla de producción |
| `deploy/ship.env.example` | `RPI_HOST`, `RPI_DIR`, `PUBLIC_URL` |
| `deploy/ship.sh` | Construir, copiar, levantar, comprobar; `--rollback <versión>` |
| `deploy/gtfs-update.sh` | Renovación del GTFS |
| `deploy/smoke.sh` | Comprobaciones tras el despliegue (`curl`) |
| `deploy/README.md` | Guía de operación (AC-16) |
| `init.sh` | Nuevo subcomando `verify-deploy` |
| `backend/src/avisabus/config.py` | Validación de producción (AC-07) |
| `backend/src/avisabus/adapters/inbound/http/access_log.py`, `logging.py` | Máscara de IP y de consulta en todas las rutas (AC-09) |
| `backend/src/avisabus/adapters/inbound/http/routes/health.py` | `gtfs` y `status` (AC-10) |
| `backend/src/avisabus/background/gtfs_tasks.py` | Aviso diario de caducidad (AC-11) |
| `frontend/vite.config.ts` | `workbox.globPatterns` con `woff2` (AC-15) |

`--forwarded-allow-ips '*'` es seguro porque el `backend` solo es accesible desde `web` por la red
interna (AC-03), y `web` reescribe `X-Forwarded-For` con un único valor (AC-05).

## 3. `deploy/compose.yaml` (esqueleto)

```yaml
name: avisabus
services:
  backend:
    image: avisabus-backend:${AVISABUS_VERSION:-latest}
    build: { context: ../backend, platforms: [linux/arm64] }
    platform: linux/arm64
    env_file: .env.prod
    volumes: [ "./data:/data" ]
    networks: [ internal ]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status == 200 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    logging: { driver: json-file, options: { max-size: 10m, max-file: "3" } }
  web:
    image: avisabus-web:${AVISABUS_VERSION:-latest}
    build: { context: .., dockerfile: frontend/Dockerfile, platforms: [linux/arm64] }
    platform: linux/arm64
    depends_on: { backend: { condition: service_healthy } }
    networks: [ internal, npm ]
    restart: unless-stopped
    logging: { driver: json-file, options: { max-size: 10m, max-file: "3" } }
networks:
  internal: {}
  npm: { external: true, name: ${NPM_NETWORK:-npm_default} }
```

## 4. `deploy/nginx/web.conf` (puntos clave)

```nginx
real_ip_header    X-Forwarded-For;
real_ip_recursive off;                      # la última dirección: la que añade NPM (AC-05)
set_real_ip_from  10.0.0.0/8;  set_real_ip_from 172.16.0.0/12;  set_real_ip_from 192.168.0.0/16;

map $http_upgrade $connection_upgrade { default upgrade; '' close; }

location /api/ { proxy_pass http://backend:8000; proxy_set_header X-Forwarded-For $remote_addr;
                 proxy_set_header X-Forwarded-Proto https; proxy_set_header Host $host; }
location /ws/  { proxy_pass http://backend:8000; proxy_http_version 1.1;
                 proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection $connection_upgrade;
                 proxy_set_header X-Forwarded-For $remote_addr; proxy_read_timeout 3600s; proxy_send_timeout 3600s; }
location ~* \.(?:js|css|woff2|png|svg|webp|ico)$ { expires 1y; add_header Cache-Control "public, immutable"; … }
location = /index.html | /sw.js | /manifest.webmanifest { add_header Cache-Control "no-cache"; … }
location / { try_files $uri /index.html; }
access_log off;                             # el log útil es el del backend (sin IP, AC-09)
```

Las cabeceras de seguridad (AC-06) se repiten en cada `location` con `add_header` (nginx no las
hereda si el bloque define otras) o con un `include` común.

## 5. Configuración de producción (`deploy/.env.prod.example`, extracto)

```
AVISABUS_ENV=prod
AVISABUS_LOG_LEVEL=INFO
AVISABUS_DATABASE_URL=sqlite:////data/avisabus.sqlite
AVISABUS_PUBLIC_BASE_URL=https://<tu-dominio>
AVISABUS_STOP_TOKEN_SECRET=<obligatorio; python3 -c "import secrets; print(secrets.token_urlsafe(48))">
AVISABUS_SAE_CONTACT=<obligatorio con la fuente http; contacto que verá EMT en el User-Agent>
AVISABUS_ARRIVALS_SOURCE=http          # replay para no consultar a EMT (sin reconstruir)
AVISABUS_SAE_REPLAY_DIR=/app/replay/stop_508_peak
AVISABUS_DIRECTION_OVERRIDES_FILE=     # vacío; si se usa, ruta absoluta en /data
```

Validación (AC-07) en `Settings` (validador de modelo, solo con `env=prod`); se suma a la ya
existente del secreto.

## 6. Logs de acceso (AC-09)

`access_log.py` hoy enmascara la IP solo en `/driver`. Se generaliza a todas las rutas en el
filtro de `uvicorn.access`: el primer argumento (dirección del cliente) pasa a `"-"` y la ruta se
registra sin la cadena de consulta. Las conexiones WebSocket se registran igual.

## 7. GTFS (AC-10, AC-11)

```json
GET /api/v1/health
{"status": "ok", "version": "1.4.0",
 "gtfs": {"feed_version": "…", "feed_end_date": "2026-11-22", "days_left": 11}}
```

`days_left` = `feed_end_date − hoy` en Europe/Madrid (con el `Clock`). `GtfsExpiryWatcher.tick()`
(una vez al arrancar y cada 24 h, `run_periodic`) registra el evento si procede.

`deploy/gtfs-update.sh <zip>` (se ejecuta en el Mac):

```
scp <zip> $RPI_HOST:$RPI_DIR/data/gtfs/incoming.zip
ssh $RPI_HOST "cd $RPI_DIR && docker compose run --rm backend avisabus gtfs import /data/gtfs/incoming.zip \
  && docker compose run --rm backend python -c 'import sqlite3; sqlite3.connect(\"/data/avisabus.sqlite\").execute(\"VACUUM\")' \
  && docker compose restart backend"
```

(Forma exacta del `VACUUM`: decisión local, p. ej. un subcomando `avisabus db vacuum`.)

## 8. `init.sh verify-deploy`

Requiere Docker en el Mac; no forma parte de `./init.sh verify`.

1. `docker compose -f deploy/compose.yaml config -q` (con un `.env.prod` de prueba generado al vuelo).
2. `docker compose -f deploy/compose.yaml build`.
3. Inspección: `backend` con `User` ≠ root, sin `EXPOSE` publicado, arquitectura `arm64`, existe
   `/app/replay/stop_508_peak/session.json`; `web` contiene `index.html`.
4. `docker run --rm avisabus-web nginx -t`.

## 9. Estrategia de test

| AC | Test |
|---|---|
| AC-01–AC-04 | `./init.sh verify-deploy` (gate) |
| AC-07 | `tests/unit/test_config_prod.py` |
| AC-08 | `tests/unit/test_env_example.py` (amplía: también `deploy/.env.prod.example`) |
| AC-09 | `tests/integration/test_access_log_privacy.py` (uvicorn real en *loopback*, como el test de `driver_session.AC-15`) |
| AC-10 | `tests/integration/test_health.py` (amplía) |
| AC-11 | `tests/unit/test_gtfs_expiry_watcher.py` (`FakeClock`) |
| AC-15 | `src/__tests__/pwa-manifest.test.ts` (amplía) + `e2e/offline-font.spec.ts` |
| AC-05, AC-06, AC-12–AC-14, AC-16 | Manual en CP-6 sobre la Raspberry + revisión |

## 10. Decisiones locales permitidas

- Versiones exactas de las imágenes base (manteniendo Python 3.12 y Node LTS).
- Forma del `VACUUM` y estructura interna de los scripts.

## 11. Preguntas abiertas

Ninguna.
