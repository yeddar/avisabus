# Revisión: deployment_rpi
Ciclo: 2 · Fecha: 2026-11-12 · Agente: reviewer
Spec: `specs/deployment_rpi/` v1.0 (APPROVED) · Rama: `feat/deployment_rpi` (diff `origin/feat/passenger_map_view-v1.3...HEAD`, commits `b5f372e..71fbb9b`)

## Veredicto: APPROVED

Los dos bloqueantes del ciclo 1 están resueltos, y lo he comprobado en una Raspberry simulada:

- **B-1:** el *Proxy Host* de NPM ya se crea antes del primer `ship.sh`. Con ese orden, el primer
  envío termina con `smoke.sh` en verde.
- **B-2:** el procedimiento «Restaurar una copia» de la guía funciona copiado literalmente.

Desde el ciclo 1 solo ha cambiado `deploy/README.md` (commit `6da13ee`), además del progreso. El
código, las imágenes, `compose.yaml`, `nginx` y los scripts no han cambiado. Las evidencias de
AC-01 a AC-15 del ciclo 1 siguen valiendo, y las he revalidado con `verify`, `verify-deploy` y la
pila simulada. Los no bloqueantes N-1 a N-9 siguen abiertos para la persona (CP-6). Añado N-10 y
N-11, que tampoco bloquean.

## Matriz AC → evidencia

| AC | Test(s) / evidencia | Resultado | Nota |
|---|---|---|---|
| AC-01 | `./init.sh verify-deploy`: build `linux/arm64` y `_check_tags` | OK | Gate en verde con las imágenes `71fbb9b` (versión y `latest` con el mismo ID) |
| AC-02 | `verify-deploy` `_check_backend_image` | OK | Sin cambios desde el ciclo 1, en el que se comprobó con mutantes. En la pila simulada, `data/` y la base son del uid 10001 |
| AC-03 | `verify-deploy` `compose config -q` + `_check_compose` | OK | Gate en verde. `compose.yaml` sin cambios desde el ciclo 1 (mutantes detectados entonces) |
| AC-04 | `nginx -t` (gate) + `smoke.sh` en la pila simulada | OK (1 h de WebSocket pendiente de CP-6) | `/` y `/driver` sirven `index.html`; `/no-such-file.js` da 404; `/ws/passenger` da `101` |
| AC-05 | Revisión de `web.conf` (sin cambios) + ciclo 1 (`smoke.sh --ip-limit` y mutante `real_ip_recursive on`) | OK (manual pendiente de CP-6) | Ver N-3 |
| AC-06 | `smoke.sh` en la pila simulada | OK (manual pendiente de CP-6) | Las cuatro cabeceras en `/` y en `/api/…`; `no-cache` en `/`, `/index.html`, `/sw.js` y el manifiesto; caché inmutable de 1 año y `gzip` en `/assets/*.js` |
| AC-07 | `backend/tests/unit/test_config_prod.py` + `verify-deploy` `_check_prod_refuses` | OK | Tests y gate en verde |
| AC-08 | `backend/tests/unit/test_env_example.py` | OK | En verde. Ver N-4 |
| AC-09 | `backend/tests/integration/test_access_log_privacy.py`, `test_driver_api.py`, `test_driver_demand.py` | OK | En verde. Ver N-1 y N-2 |
| AC-10 | `backend/tests/integration/test_health.py`, `test_main_gtfs.py` | OK | En la pila simulada, tras importar `gtfs_mini`: `{"status":"ok",…,"gtfs":{"feed_version":"23-10-2026","feed_end_date":"2026-11-22","days_left":10}}` |
| AC-11 | `backend/tests/unit/test_gtfs_expiry_watcher.py` (`FakeClock`), `test_main_gtfs.py` | OK | En verde |
| AC-12 | Revisión de `gtfs-update.sh` (sin cambios) + importación en la pila simulada | OK (manual pendiente de CP-6) | Zip roto, sin reinicio: comprobado en el ciclo 1 |
| AC-13 | Revisión de `ship.sh` (sin cambios) + pasos de `ship.sh` (`chown`, `up --wait`) en la pila simulada | OK (manual pendiente de CP-6) | `--rollback` y la conservación de las imágenes se comprobaron en el ciclo 1. Ver N-5 |
| AC-14 | Revisión de `smoke.sh` + ejecución en la pila simulada | OK (manual pendiente de CP-6) | Todo en verde con la pila arriba. Si la URL no responde, sale con código ≠ 0 y el motivo. Ver N-10 |
| AC-15 | `frontend/src/__tests__/pwa-manifest.test.ts`, `frontend/e2e/offline-font.spec.ts` | OK | Unit y e2e en verde |
| AC-16 | Revisión de `deploy/README.md` + simulación de §3.2–§3.4 y §9 | OK (la persona la sigue en CP-6) | Cubre todos los apartados del AC. B-1 y B-2, resueltos (ver abajo). Ver N-6, N-7 y N-11 |

## Verificación ejecutada

- **`./init.sh verify-deploy`: verde** en los 8 pasos, con las imágenes `71fbb9b`:
  - compose config y compose (AC-03);
  - build `linux/arm64` y etiquetas (AC-01);
  - imagen backend (AC-02);
  - la configuración de prod incompleta no arranca (AC-07);
  - imagen web y `nginx -t` (AC-04).
- **`CI=1 ./init.sh verify --e2e`** (puerto 4173 libre): **verde**, código 0.
  - Backend: format, lint, types y architecture OK; 1969 passed, 9 deselected; cobertura 99,66 %.
  - Frontend: format, lint y types OK; 677 passed, 2 skipped; build + bundle, 5 passed.
  - e2e + a11y: 135 passed, 12 skipped, sin tests *flaky*.
  - Harness: `feature_list.json` y trazabilidad AC→test OK.
- **Raspberry simulada.** Un directorio de la VM de Colima, `/tmp/avisabus-rev2`, hace de
  Raspberry. El usuario de la VM (uid 501, grupo `docker`, sin root) hace de usuario de SSH, y los
  comandos de la guía se ejecutan allí con `docker compose`.
  - Se usan la fuente `replay` y la red `avisabus-rev2-npm`. No hay SSH real ni peticiones
    externas.
  - Se reproducen los pasos de `ship.sh`: `.env` con la versión, `chown` de `data/` y
    `up --wait`.
  - Se importa `gtfs_mini` como en `gtfs-update.sh`.
- **B-1, orden de §3.2 → §3.3.**
  - El sustituto de NPM es un nginx (la imagen `avisabus-web:71fbb9b` local, con su propia
    configuración, sin descargas). Está en la red de NPM y, como la plantilla de *Proxy Host* de
    NPM, lleva el destino en una variable (`set $server "web"`) y usa el *resolver* de Docker.
  - Se arranca **antes** de que exista `web`: arranca sin errores y responde
    `502 Bad Gateway`, como dice la guía.
  - Después: `docker compose up -d --wait` (lo que hace `ship.sh`) y `deploy/smoke.sh` desde el
    Mac contra el proxy. Resultado: **todo en verde**, código 0, con `/ws/passenger` → `101`.
  - Con el proxy caído, `smoke.sh` termina con código ≠ 0 y con el motivo (`FALLO /api/v1/health
    no responde 200`). Así se cumple lo que §3.3 promete: el servicio queda arrancado y se repite
    solo `smoke.sh`.
- **B-2, §9 copiado literalmente.**
  1. «Copia»: `stop`, `cp data/avisabus.sqlite avisabus-AAAAMMDD-HHMM.sqlite` como uid 501 (código
     0) y `start`.
  2. Creo un código de conductor posterior a la copia (`dc-i3dpn1`).
  3. Reproduzco el fallo: `cp "$COPIA" data/avisabus.sqlite` como uid 501 da
     `Permission denied`.
  4. Comando de «Restaurar una copia», copiado de la guía con `COPIA=…`: código 0.
     - `data/avisabus.sqlite` queda igual a la copia (`cmp`).
     - Propietario 10001:10001, permisos 644, sin `-wal` ni `-shm`.
     - Tras `start`, el backend queda `healthy` y `/health` responde `ok`.
     - `driver-codes list` dice «No hay códigos de conductor»: se ha restaurado la copia.
     - Se puede crear un código después (`dc-v8yn9g`), y el proceso del backend escribe en la base
       (WAL creado por el uid 10001).
  5. Alternativa con `sudo`, con el servicio parado: código 0, el mismo propietario y permisos,
     `healthy` y la base restaurada.
- **Alcance:** `git diff c50f7b3..HEAD` solo toca `deploy/README.md` (+52 −18) y el progreso del
  orquestador y del implementer.
- **Limpieza:**
  - Borrados: el proyecto compose, la red `avisabus_internal`, el proxy, la red
    `avisabus-rev2-npm`, el directorio de la VM y los scripts temporales de la VM.
  - Borradas también las etiquetas `71fbb9b` del gate. `latest` vuelve a las imágenes
    `6da13ee-dirty` (`7f8970e6acb5` y `7ca160b86c4d`), como antes de la revisión. No quedan
    imágenes huérfanas.
  - No he tocado `pg-booking`, `pg-inventory`, `rabbitmq`, `qr/`, `.env` ni la caché de build. No
    he creado `deploy/.env.prod` en el repositorio.

## Hallazgos

### Bloqueantes

Ninguno.

### Bloqueantes del ciclo 1: resueltos

- **B-1 — resuelto** (`deploy/README.md:85-124`).
  - §3.2 crea el *Proxy Host* antes del envío y avisa del `502` hasta el primer `ship.sh`.
  - §3.3 explica qué hacer si `smoke` falla al final de `ship.sh`. La guía acierta: `start`
    (`ship.sh:82`) va antes de `smoke` (`ship.sh:83`), así que el servicio ya está arrancado.
  - Lo he comprobado como se describe arriba.
- **B-2 — resuelto** (`deploy/README.md:246-274`).
  - El procedimiento principal (contenedor como root) y la alternativa con `sudo` funcionan, y
    dejan la base del uid 10001.
  - §7 (`:208-210`) remite al apartado correcto.

### No bloqueantes

Abiertos del ciclo 1, sin cambios. Los detalles están en la revisión del ciclo 1 (commit `c50f7b3`).

- **N-1 — `deploy/nginx/web.conf`: el error log de `web` guarda la IP y el token** cuando el
  backend no responde. Choca con RNF-06, aunque AC-09 solo habla del log de acceso.
  **Decisión de la persona:** `error_log /dev/stderr crit;` o aceptarlo.
- **N-2 — Problema de spec (alcance de AC-09), para CP-6: el log de acceso del propio NPM** guarda
  la IP y el `?t=`. Bastaría con añadir a la guía (§3.2) `access_log off;` en la pestaña
  *Advanced* del *Proxy Host*.
- **N-3 — `deploy/README.md:100-102`, `smoke.sh` `--ip-limit`: AC-05 depende de cómo ve NPM a los
  clientes.** En CP-6, repetir `--ip-limit` también con `-H 'X-Real-IP: …'` y comprobar que NPM
  registra IP públicas.
- **N-4 — `deploy/.env.prod.example:27` y `:36`:** los marcadores `https://<tu-dominio>` y
  `<obligatorio con la fuente http>` pasan la validación de AC-07.
- **N-5 — `deploy/ship.sh:84-86`:** la versión anterior solo se muestra si todo va bien, no
  cuando `start` o `smoke` fallan.
- **N-6 — `deploy/README.md:60-69`:** el título de §3.1 dice «(en la Raspberry)», pero
  `ssh … mkdir` y `scp` se ejecutan en el Mac.
- **N-7 — `deploy/README.md:97`:** conviene avisar de que no se active «HSTS» en la pestaña SSL
  de NPM, porque saldría una segunda cabecera HSTS.
- **N-8 — `init.sh` `_check_compose`:** sin la red `npm`, la comprobación falla con un
  `KeyError` en lugar de un motivo. Es cosmético.
- **N-9 — `smoke.sh:49-65`:** la «versión» de `/health` es la del paquete (`0.1.0`), no la
  etiqueta de la imagen.

Nuevos en el ciclo 2:

- **N-10 — `deploy/smoke.sh:68` (y siguientes `headers …`): si no hay conexión, `smoke` se para
  en la primera petición fallida.**
  - Lo que pasa: con la URL inaccesible (DNS o proxy aún no listos, el caso que menciona §3.3),
    `smoke` imprime `FALLO /api/v1/health no responde 200`. Después, `home="$(headers /)"` falla
    por `set -euo pipefail`, y el script termina con el código de `curl` (`7`), sin el resto de
    comprobaciones ni el resumen.
  - AC-14 se cumple: el código es distinto de 0 y se muestran el motivo y el error de `curl`.
  - Pero contradice el comentario de cabecera (`smoke.sh:10`: «prints each failure and exits
    with 1»).
  - Sugerencia: `headers` con `|| true`, o salir con 1 y un mensaje claro si `/api/v1/health` no
    conecta.
- **N-11 — `deploy/README.md:153-162` y `:208-210`: §7 da por hecho que hay una copia anterior a
  la actualización.**
  - §7 dice que, si la versión nueva cambió la estructura de la base de datos, se restaure la
    copia. Pero §4 (Actualizaciones) no recomienda hacer la copia de §9 antes de `ship.sh`.
  - Quien siga la guía en orden puede no tener una copia previa a la actualización.
  - Sugerencia: añadir en §4 «haz antes la copia de la sección 9 si la versión cambia la base de
    datos». AC-16 se cumple, porque los dos apartados existen.

### Decisiones locales contrastadas con la spec

Sin cambios respecto al ciclo 1, con este juicio:

- Tests de otras features adaptados a AC-07 y AC-09: conformes.
- `gtfs: null` sin feed: compatible.
- `resolver 127.0.0.11` + `proxy_pass` con variable: conforme.
- `AVISABUS_ENV_FILE`: conforme.
- Caché de nginx distinta del patrón de design §4: cumple AC-06 mejor que el patrón de design §4,
  pero **para la persona:** que la ratifique y se actualice design §4 en la próxima versión de la
  spec.
- `chown` no recursivo de `data/`: funciona, y la guía ya documenta la restauración que afectaba
  (B-2 resuelto).

### Resto de la lista de comprobación (docs/verification.md §4)

- **Arquitectura:** `lint-imports` OK (2 contratos). Sin cambios de código en este ciclo.
- **Tests:** sin red ni *sleeps* reales. Trazabilidad AC→test OK. Este ciclo no añade tests: el
  cambio es solo de documentación, y AC-16 se verifica por revisión y en CP-6.
- **Privacidad y seguridad:**
  - El procedimiento de restauración no expone secretos: `.env.prod` solo lo lee `env_file`, y el
    comando usa `--entrypoint sh` sin imprimir la configuración.
  - El montaje de la copia es de solo lectura (`:ro`).
  - Siguen abiertos N-1 y N-2.
- **Frontend:** no hay textos nuevos de interfaz; axe en verde.
- **Convenciones:** `6da13ee` sigue Conventional Commits con ámbito `deployment_rpi`. Los commits
  del orquestador son `chore(progress)`.
- **Alcance:** solo `deploy/README.md` y el progreso. Sin cambios en `docs/`, `specs/` ni en
  código ajeno a la feature.
