# Despliegue en Raspberry Pi — requirements

> Feature: `deployment_rpi` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RNF-06, RNF-07, RNF-11, RNF-13, RNF-14 · Casos de uso: — (operación) · Depende de: project_scaffold

## Contexto

AvisaBus se publica en la **Raspberry Pi** de la persona (SO de 64 bits, `arm64`), detrás del
**Nginx Proxy Manager (NPM)** que ya tiene allí, con un dominio propio y TLS de Let's Encrypt
gestionado por NPM (`docs/architecture.md` §3). Decisiones de la persona (2026-11-11):

- Las imágenes se **construyen en su Mac (Apple Silicon)**, que compila `arm64` de forma nativa,
  y se **llevan a la Raspberry por SSH** (`docker save | docker load`): la Raspberry no necesita
  el código ni compilar. Construir en GitHub Actions queda como mejora futura.
- La instancia publicada usa el **SAE real con poco volumen** (caché de 20 s, User-Agent
  identificado). Un interruptor de configuración permite pasar a la grabación (`replay`) sin
  reconstruir, por ejemplo si EMT lo pidiera (respuesta de EMT del 2026-11-11: no autoriza ni
  prohíbe; anuncia un SAE nuevo con datos públicos).
- El GTFS se **renueva a mano con un comando**; el sistema avisa cuando faltan 7 días para que
  caduque (el activo caduca el 2026-11-22).

También recoge lo que las features anteriores dejaron para el despliegue: IP real del cliente
tras los *proxies*, IP fuera de los logs de acceso, WebSockets, cabeceras compatibles con las
teselas de OpenStreetMap, precarga de la tipografía en la PWA y variables de producción.

HTTPS es obligatorio para la geolocalización de la tablet del conductor y para la PWA; tras esta
feature se podrá probar con una tablet real (pendiente del CP-6 del bloque 4).

## Alcance

- Imágenes `backend` y `web` (`linux/arm64`) y `deploy/compose.yaml`.
- Configuración de `nginx` del contenedor `web` (`deploy/nginx/web.conf`).
- Scripts `deploy/ship.sh`, `deploy/gtfs-update.sh` y `deploy/smoke.sh`.
- Plantilla `deploy/.env.prod.example` y validación de la configuración de producción.
- Estado del GTFS en `/health` y aviso periódico de caducidad.
- Máscara de la IP en todos los logs de acceso.
- Precarga de la tipografía en el *service worker*.
- Guía de operación `deploy/README.md`.

## Fuera de alcance

- Instalar Docker o NPM en la Raspberry, el DNS y el certificado (ya existen).
- Construir en GitHub Actions, imágenes `amd64` y copias de seguridad automáticas (mejoras
  futuras; la guía explica cómo copiar la base de datos con el servicio parado).
- Descarga automática del GTFS.
- Pruebas de carga y de rendimiento (`nfr_validation`).

## Criterios de aceptación

### Imágenes y composición

- **deployment_rpi.AC-01** — `docker compose -f deploy/compose.yaml build` DEBERÁ construir en un
  Mac Apple Silicon las imágenes `avisabus-backend` y `avisabus-web` para `linux/arm64`, etiquetadas
  con la versión (`git describe --tags --always --dirty`) y `latest`.
  *Verificación:* gate (`./init.sh verify-deploy`)
- **deployment_rpi.AC-02** — LA IMAGEN `backend` DEBERÁ ejecutar `uvicorn` con un único proceso
  (ADR-003) como usuario sin privilegios, sin dependencias de desarrollo, con `--proxy-headers`, y
  sin publicar puertos en el anfitrión; LA BASE DE DATOS DEBERÁ vivir en un volumen
  (`/data`) y la grabación `stop_508_peak` DEBERÁ ir dentro de la imagen para poder usar `replay`
  sin reconstruir.
  *Verificación:* gate (inspección de la imagen en `verify-deploy`) + revisión
- **deployment_rpi.AC-03** — `deploy/compose.yaml` DEBERÁ definir `web` y `backend` con
  `restart: unless-stopped`, rotación de logs (10 MB × 3), una red interna (`backend` solo en ella)
  y la red externa de NPM para `web` (nombre configurable, `NPM_NETWORK`), comprobación de salud
  del `backend` sobre `/api/v1/health` y `web` dependiente de ella. `docker compose config` DEBERÁ
  validar sin errores.
  *Verificación:* gate

### Proxy, cabeceras y WebSockets

- **deployment_rpi.AC-04** — EL CONTENEDOR `web` DEBERÁ servir el build del frontend con
  *fallback* a `index.html` para las rutas de la SPA (no para `/api`, `/ws` ni ficheros con
  extensión), y reenviar `/api/` y `/ws/` al `backend`; para `/ws/` DEBERÁ pasar `Upgrade` y
  `Connection` y mantener la conexión abierta al menos 1 h sin tráfico del cliente.
  *Verificación:* gate (`nginx -t` en `verify-deploy`) + manual (`smoke.sh` y prueba en CP-6)
- **deployment_rpi.AC-05** — EL CONTENEDOR `web` DEBERÁ fijar la IP del cliente a partir de la
  cabecera de NPM confiando solo en las redes privadas configuradas (`set_real_ip_from`, sin
  recursión: se toma la dirección que añade NPM, no la que envíe el cliente) y reenviarla al
  `backend` como única entrada de `X-Forwarded-For`, de modo que los límites por IP
  (`alert_create.AC-08`, `driver_session.AC-02`) vean la IP real y un cliente no pueda falsearla.
  *Verificación:* manual (`smoke.sh` con una cabecera `X-Forwarded-For` falsa: el límite por IP no
  cambia) + revisión
- **deployment_rpi.AC-06** — LAS RESPUESTAS de `web` DEBERÁN llevar `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` (nunca `no-referrer`: lo exige la
  política de teselas de OSM), `Permissions-Policy: geolocation=(self), camera=(), microphone=()`
  y `Strict-Transport-Security` de 6 meses; `index.html`, `sw.js` y el manifiesto con
  `Cache-Control: no-cache`, y los ficheros con *hash* con caché inmutable de 1 año; compresión
  `gzip` para texto.
  *Verificación:* manual (`smoke.sh` comprueba las cabeceras)

### Configuración de producción

- **deployment_rpi.AC-07** — CON `AVISABUS_ENV=prod`, LA API Y LA CLI NO DEBERÁN arrancar SI la
  fuente de llegadas es `http` y `AVISABUS_SAE_CONTACT` está vacío, ni SI `AVISABUS_PUBLIC_BASE_URL`
  no es `https://`; el mensaje DEBERÁ nombrar la variable (sin mostrar valores secretos).
  *Verificación:* unit
- **deployment_rpi.AC-08** — `deploy/.env.prod.example` DEBERÁ documentar todas las variables de
  producción (rutas absolutas dentro del contenedor, secreto obligatorio, contacto, URL pública,
  fuente `http` por defecto y cómo pasar a `replay`) y `deploy/.env.prod` DEBERÁ estar en
  `.gitignore`.
  *Verificación:* unit (todas las variables de `Settings` aparecen en la plantilla) + gate

### Privacidad de los logs

- **deployment_rpi.AC-09** — NINGUNA línea del log de acceso DEBERÁ contener la IP del cliente, en
  ninguna ruta (generaliza el filtro que hoy solo cubre `/driver`), y los parámetros de consulta
  de `/p/…` y de `/api/v1/stops/…` (token del QR) tampoco DEBERÁN aparecer en él.
  *Verificación:* integration (logs capturados de `/alerts`, `/ws/passenger`, `/stops/…?t=…` y
  `/health` con `uvicorn` real en *loopback*)

### GTFS

- **deployment_rpi.AC-10** — `GET /api/v1/health` DEBERÁ incluir `gtfs` con `feed_version`,
  `feed_end_date` y `days_left` de la versión activa (`null` sin feed), y `status` DEBERÁ ser
  `degraded` cuando `days_left < 0` o no hay feed, sin dejar de responder `200`.
  *Verificación:* integration
- **deployment_rpi.AC-11** — UNA TAREA de fondo DEBERÁ registrar `gtfs.feed_expiring` (con
  `days_left`) al arrancar y una vez al día MIENTRAS `days_left ≤ AVISABUS_GTFS_EXPIRY_WARNING_DAYS`,
  y `gtfs.feed_expired` cuando ya ha caducado.
  *Verificación:* unit (`FakeClock`)
- **deployment_rpi.AC-12** — `deploy/gtfs-update.sh <zip>` DEBERÁ copiar el zip a la Raspberry,
  importarlo con la CLI dentro del contenedor (`docker compose run --rm backend avisabus gtfs
  import`), compactar la base de datos (`VACUUM`) y reiniciar el `backend`; SI la importación
  falla, ENTONCES DEBERÁ terminar con error sin reiniciar (la versión activa no cambia).
  *Verificación:* manual (CP-6) + revisión

### Envío y comprobación

- **deployment_rpi.AC-13** — `deploy/ship.sh` DEBERÁ construir, copiar las imágenes a la
  Raspberry (`RPI_HOST` y `RPI_DIR` de `deploy/ship.env`, no versionado), sincronizar
  `deploy/compose.yaml` y `deploy/nginx/` (nunca `.env.prod`), levantar el servicio y ejecutar
  `smoke.sh`; DEBERÁ conservar en la Raspberry la imagen anterior con su etiqueta para poder
  volver a ella (`ship.sh --rollback <versión>`).
  *Verificación:* manual (CP-6) + revisión
- **deployment_rpi.AC-14** — `deploy/smoke.sh <url>` DEBERÁ comprobar: `/api/v1/health` con
  `status` y versión; la portada (`200`, `text/html`); una ruta de la SPA (`/driver`) servida por
  el *fallback*; las cabeceras de AC-06; el *handshake* de `/ws/passenger` (`101`); y terminar con
  código distinto de 0 y el motivo si algo falla.
  *Verificación:* manual (CP-6) + revisión

### PWA

- **deployment_rpi.AC-15** — EL SERVICE WORKER DEBERÁ precargar los `woff2` de la tipografía
  (`frontend_i18n` N-04) y NO DEBERÁ cachear teselas de OpenStreetMap ni respuestas de `/api` o
  `/ws`.
  *Verificación:* unit (`pwa-manifest.test.ts`: patrones de `workbox`) + e2e (sin conexión, la
  portada se muestra con Atkinson Hyperlegible)

### Documentación

- **deployment_rpi.AC-16** — `deploy/README.md` DEBERÁ explicar, paso a paso: requisitos en la
  Raspberry (Docker, NPM y su red), *Proxy Host* de NPM (destino `web:80`, *Websockets Support*,
  certificado), primer despliegue (crear `.env.prod`, generar el secreto, importar el GTFS, crear
  códigos de conductor y QR), actualizaciones, renovación del GTFS, paso a `replay` y vuelta,
  vuelta a una versión anterior, logs, y copia de la base de datos con el servicio parado.
  *Verificación:* revisión + manual (la persona sigue la guía en CP-6)

## Trazabilidad

| Requisito | AC |
|---|---|
| RNF-06 Privacidad | AC-09 |
| RNF-07 Seguridad | AC-02, AC-05, AC-06, AC-07, AC-08 |
| RNF-11 Despliegue con `docker compose` | AC-01, AC-02, AC-03, AC-04, AC-13, AC-14, AC-16 |
| RNF-13 Observabilidad | AC-09, AC-10, AC-11 |
| RNF-14 Licencias y terceros (OSM, EMT) | AC-06, AC-07, AC-15 |
| Operación del GTFS (caducidad) | AC-10, AC-11, AC-12 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-11 | Versión inicial aprobada (PR #60). | CP-1 de `deployment_rpi`. Aprobada por la persona. |
