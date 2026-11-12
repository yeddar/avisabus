# Revisión: deployment_rpi
Ciclo: 1 · Fecha: 2026-11-12 · Agente: reviewer
Spec: `specs/deployment_rpi/` v1.0 (APPROVED) · Rama: `feat/deployment_rpi` (diff `origin/feat/passenger_map_view-v1.3...HEAD`, commits `b5f372e..c50f7b3`)

## Veredicto: CHANGES_REQUESTED

El código, las imágenes, `compose.yaml`, `nginx` y los scripts cumplen los AC-01 a AC-15. Lo he
comprobado con los tests, con `verify-deploy` y con mutantes, y he simulado una Raspberry en local.
La guía `deploy/README.md` (AC-16) tiene dos fallos bloqueantes: seguida al pie de la letra, el
primer despliegue termina en error (B-1), y la restauración de la copia de la base de datos no
funciona por permisos (B-2). Los dos se corrigen solo en la guía (o en `ship.sh`), sin tocar la spec.

## Matriz AC → evidencia

| AC | Test(s) / evidencia | Resultado | Nota |
|---|---|---|---|
| AC-01 | `./init.sh verify-deploy`: build `linux/arm64` y `_check_tags` (versión = `latest`) | OK | Gate. Etiquetas `c50f7b3` y `latest` con el mismo ID |
| AC-02 | `verify-deploy` `_check_backend_image` + inspección manual | OK | Usuario `avisabus` (uid 10001), sin `ExposedPorts`, `arm64`, CMD sin `--workers` con `--proxy-headers`, sin pytest/ruff/mypy/hypothesis, `/app/replay/stop_508_peak/session.json`, `VOLUME /data`, `.venv` de root (solo lectura). Mutantes detectados: sin `USER`, `--workers 2`, sin la grabación, con dependencias de desarrollo |
| AC-03 | `verify-deploy` `compose config -q` + `_check_compose` | OK | Mutantes detectados: `ports` en backend, `restart: always`, `max-file: 5`, `service_started`, `web` sin red NPM (este último con *traceback*, ver N-8) |
| AC-04 | `nginx -t` (gate) + `smoke.sh` en la pila local | OK (manual de 1 h pendiente de CP-6) | `/` y `/driver` sirven `index.html`; `/no-such-file.js` da 404; `/ws/passenger` da 101; `proxy_read/send_timeout 3600s`. Mutante con error de sintaxis: `nginx -t` falla |
| AC-05 | Revisión de `web.conf` + `smoke.sh --ip-limit` en local, con un nginx en la red NPM que hace de NPM (`$proxy_add_x_forwarded_for`) | OK (manual pendiente de CP-6) | 429 al 6.º intento con `X-Forwarded-For` distintos. Mutante `real_ip_recursive on`: `smoke` falla («ningún 429 en 12 intentos»). El backend lee `request.client.host` (`routes/alerts.py:205`, `routes/driver.py:256`). Ver N-3 |
| AC-06 | `smoke.sh` en la pila local | OK (manual pendiente de CP-6) | Cuatro cabeceras en `/` y `/api/…`; `no-cache` en `/`, `/index.html`, `/sw.js` y `/manifest.webmanifest`; caché inmutable de 1 año y `gzip` en `/assets/*.js`. Mutante sin HSTS: `smoke` falla |
| AC-07 | `backend/tests/unit/test_config_prod.py` (Settings y CLI) + `verify-deploy` `_check_prod_refuses` | OK | Cubre contacto vacío o con espacios, fuente por defecto o `http`, `replay` sin contacto, URL http/HTTP/sin esquema/sin host/vacía, mensaje sin el secreto, dev/test exentos y CLI. Mutante (validador desactivado): `verify-deploy` falla |
| AC-08 | `backend/tests/unit/test_env_example.py` | OK | Mismo conjunto de variables que `Settings.model_fields`, valores de producción, rutas absolutas, `deploy/.env.prod` ignorado por git |
| AC-09 | `backend/tests/integration/test_access_log_privacy.py` (uvicorn real en *loopback*), `test_driver_api.py`, `test_driver_demand.py` | OK | En la pila local, 0 apariciones de IP, `?t=` o `X-Forwarded-For` en el log del backend; `web` con `access_log off`. Ver N-1 y N-2 (otros logs) |
| AC-10 | `backend/tests/integration/test_health.py`, `test_main_gtfs.py` | OK | Con feed, sin feed (`null`), caducado (`degraded`, 200), límites de día en Europe/Madrid. En local, tras importar: `{"status":"ok",…,"days_left":10}` |
| AC-11 | `backend/tests/unit/test_gtfs_expiry_watcher.py` (`FakeClock` y `sleep` falso), `test_main_gtfs.py` | OK | Avisa al arrancar y luego cada día, con el umbral de la configuración, `feed_expired`, un fallo que no para la tarea y la cancelación |
| AC-12 | Revisión de `gtfs-update.sh:30-55` + simulación local | OK (manual pendiente de CP-6) | Zip válido: importa, `VACUUM` y reinicia; `/health` ok. Zip roto: código 1, sin reinicio (`StartedAt` igual) y el feed activo no cambia |
| AC-13 | Revisión de `ship.sh` + simulación local | OK (manual pendiente de CP-6) | Sin `.env.prod`: error claro. Primer despliegue y segundo (`7c6c303`) con «versión anterior» y `--rollback c50f7b3` en verde. `--rollback deadbee`: error. Solo se sincronizan `compose.yaml` y `nginx/` (traza de los *shims*). Las imágenes anteriores se conservan |
| AC-14 | Revisión de `smoke.sh` + ejecución local | OK (manual pendiente de CP-6) | Todas las comprobaciones de AC-14. Con mutantes, código 1 y el motivo de cada fallo |
| AC-15 | `frontend/src/__tests__/pwa-manifest.test.ts`, `frontend/e2e/offline-font.spec.ts` | OK | Hay 4 `woff2` en el build; no hay `runtimeCaching`; `/api` y `/ws` en `navigateFallbackDenylist`. El e2e pasa en los 3 perfiles |
| AC-16 | Revisión de `deploy/README.md` | **FALLA** | Cubre todos los apartados que pide el AC, pero tiene los fallos B-1 y B-2 |

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre): **verde**, código 0.
  - Backend: format · lint · types · architecture OK; 1969 passed, 9 deselected; cobertura total del informe 99 %.
  - Frontend: format · lint · types OK; 677 passed, 2 skipped; build + bundle 5 passed; e2e + a11y 135 passed, 12 skipped, sin *flaky* en esta ejecución.
  - Harness: `feature_list.json` y trazabilidad AC→test OK.
- `./init.sh verify-deploy`: **verde** en los 8 pasos (imágenes `c50f7b3`, desde la caché).
- **Mutantes de `verify-deploy`** (en un `git clone` dentro del scratchpad), los tres juegos con código 1:
  - A: sin `USER`, sin `COPY` de la grabación, `--workers 2`, `ports` en backend y error de sintaxis en `web.conf`. Fallan los pasos AC-03, AC-02 (tres motivos) y `nginx -t`.
  - B: `uv sync` con dependencias de desarrollo, validador de prod desactivado y `web` sin red NPM. Fallan AC-02, AC-07 y AC-03.
  - C: `max-file 5`, `restart: always` en web y `service_started`. AC-03 falla con 4 motivos.
- **Raspberry simulada**: la VM de Colima hace de Raspberry, con `ssh`/`scp`/`rsync` sustituidos por *shims* que actúan en la VM. `RPI_DIR=/tmp/avisabus-review` (en la VM), fuente `replay`, sin contacto con EMT ni SSH real. Delante, un sustituto de NPM: un nginx en la red `avisabus-review-npm`, publicado solo en `127.0.0.1:18080`.
  - `ship.sh` (sin y con `.env.prod`), `--rollback` (versión válida e inexistente), `gtfs-update.sh` (zip válido y roto), `smoke.sh` y `smoke.sh --ip-limit`. Además, mutantes de `smoke` en caliente (`real_ip_recursive on` y sin HSTS): `smoke` los detecta.
- `bash -n` (bash 3.2 de macOS) de `deploy/*.sh` e `init.sh`: OK. `shellcheck` no está instalado.
- Limpieza:
  - Contenedores, red `avisabus_internal`, red `avisabus-review-npm`, proxy, `/tmp/avisabus-review` de la VM, etiquetas `c50f7b3`, `7c6c303` y `7c6c303-dirty`, e imágenes huérfanas de los mutantes: todo borrado.
  - `latest` vuelve a las imágenes `360f342`, como antes de la revisión.
  - No he podido borrar un árbol de directorios vacío que creó en la VM de Colima mi prueba de montaje: `/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-…/scratchpad/clone/deploy`. El borrado necesita permiso; es inocuo.
  - La caché de build de Docker no se ha tocado.

## Hallazgos

### Bloqueantes

- **B-1 — `deploy/README.md:85-118` (AC-16): el orden de los pasos hace fallar el primer despliegue.**
  - En §3.2, `deploy/ship.sh` termina ejecutando `smoke.sh "$PUBLIC_URL"` (`ship.sh:83`).
  - Pero el *Proxy Host* de NPM no se crea hasta §3.3. Hasta entonces, el dominio no llega a `web`, `smoke` falla y `ship.sh` sale con código 1 (`set -e`).
  - La guía no avisa de esto: dice que solo `degraded` es «aviso, no error».
  - Quien siga la guía sin conocimiento previo creerá que el despliegue ha fallado.
  - Corrección: crear el *Proxy Host* antes de `ship.sh` (NPM admite el destino `web` aunque el contenedor aún no exista; dará 502 hasta que exista), o avisar en §3.2 de que el primer `smoke` falla y qué hacer después.
- **B-2 — `deploy/README.md:237-239` (y `:202-204`) (AC-16), consecuencia de `ship.sh:79-81`: la restauración no funciona.**
  - `ship.sh` hace `chown 10001:10001` de `data/` (no recursivo).
  - `avisabus.sqlite`, `-wal` y `-shm` son del uid 10001, en un directorio en el que el usuario de SSH no puede escribir.
  - En la Raspberry simulada: `cp bk.sqlite data/avisabus.sqlite` y `rm data/avisabus.sqlite-wal` dan *Permission denied*. La copia (`cp data/avisabus.sqlite …`) sí funciona.
  - La guía remite a esta restauración desde la vuelta a una versión anterior (§7).
  - Corrección: hacer la restauración con `sudo`, o con `docker compose run --rm --no-deps --user 0 --entrypoint sh backend -c '…'`, y dejar el fichero con propietario 10001.

### No bloqueantes

- **N-1 — `deploy/nginx/web.conf` (sin `error_log`): el error log de `web` guarda la IP y el token.**
  - Se hereda `error_log … notice` del `nginx.conf` de la imagen base.
  - Comprobado parando el backend:
    `[error] … backend could not be resolved …, client: 172.19.0.1, server: _, request: "GET /api/v1/stops/508?t=TOKENMARKER789 HTTP/1.1"`.
  - Ocurre en cada reinicio del backend: en cada `gtfs-update.sh`, en cada `ship.sh` y en cada caída.
  - AC-09 solo habla del log de acceso, así que no lo incumple. Aun así, choca con RNF-06.
  - **Decisión de la persona** (el implementer ya lo propuso): `error_log /dev/stderr crit;` (o `emerg`), o aceptarlo.
- **N-2 — Problema de spec (alcance de AC-09), para la persona en CP-6: el log de acceso del propio NPM.**
  - NPM registra en su log de acceso de cada *Proxy Host* la IP y la URL completa, con el `?t=` de `/p/…` y de `/api/v1/stops/…`.
  - Queda fuera de nuestros contenedores, y la spec no dice nada. La guía tampoco lo menciona.
  - Si se quiere cumplir el espíritu de AC-09/RNF-06, bastaría con añadir a la guía `access_log off;` en la pestaña *Advanced* del *Proxy Host*.
- **N-3 — `deploy/README.md:108-110`, `smoke.sh:117-131`: AC-05 depende de cómo ve NPM a los clientes (riesgo para CP-6).**
  - `web` confía en lo que añade NPM. Si recuerdo bien la configuración de NPM, este acepta `X-Real-IP` de clientes con dirección privada.
  - Si NPM viera a los clientes de Internet con una dirección privada (por ejemplo, clientes IPv6 que entran por `docker-proxy`), todos compartirían límite por IP y podrían falsearlo con `X-Real-IP`.
  - En CP-6 conviene repetir `--ip-limit` también con `-H 'X-Real-IP: …'` y comprobar que NPM registra IP públicas.
- **N-4 — `deploy/.env.prod.example:24` y `:34`: dos marcadores pasan la validación de AC-07.**
  - `https://<tu-dominio>` y `<obligatorio con la fuente http>` no están vacíos, así que AC-07 los acepta.
  - Si se olvidan, el servicio arranca, los QR salen con una URL base inválida y el marcador va en el User-Agent hacia EMT.
  - AC-07 se cumple al pie de la letra. Sugerencia: dejarlos vacíos con el comentario, o rechazar valores con `<`.
- **N-5 — `deploy/ship.sh:82-86`: la versión anterior solo se muestra si todo va bien.**
  - Si `start` o `smoke` fallan, `ship.sh` sale sin mostrarla, y es justo cuando hace falta para `--rollback`.
  - Sugerencia: mostrarla antes de arrancar, o en el mensaje de error.
- **N-6 — `deploy/README.md:60-69`: dónde se ejecuta cada comando.**
  - El título de §3.1 dice «(en la Raspberry)», pero `ssh … mkdir` y `scp` se ejecutan en el Mac.
  - Conviene separar los dos bloques y decir dónde va cada uno.
- **N-7 — `deploy/README.md:105`: la opción HSTS de NPM.**
  - Conviene indicar que no se active «HSTS» en la pestaña SSL de NPM: `web` ya envía HSTS de 6 meses, y NPM añadiría una segunda cabecera con otro `max-age`.
- **N-8 — `init.sh:641`: el error de `_check_compose` sin red NPM.**
  - Si `web` no tiene la red `npm`, `compose config` la elimina y la comprobación falla con `KeyError: 'npm'` (un *traceback*) en lugar de un motivo.
  - El paso falla igualmente; es solo cosmético.
- **N-9 — `smoke.sh:49-65`: la versión que muestra `smoke`.**
  - La «versión» de `/api/v1/health` es la del paquete (`0.1.0`), no la etiqueta de la imagen.
  - `smoke` no puede confirmar que está en servicio la versión recién desplegada. AC-14 se cumple; solo es una observación.

### Decisiones locales de `progress/impl_deployment_rpi.md`, contrastadas con la spec

| Decisión | Juicio |
|---|---|
| Tests de otras features modificados por AC-07 (contacto/https en 4 tests de `Settings` en prod) y AC-09 (`test_driver_api.py`, `test_driver_demand.py`) | **Conforme.** AC-07 hace obligatorias esas variables en prod. AC-09 dice expresamente que generaliza el filtro de `/driver`, así que «las demás rutas conservan la IP» ya contradecía la spec. Los tests cambiados citan `deployment_rpi.AC-09`. Las aserciones propias de `driver_session.AC-15` se mantienen |
| `gtfs: null` (el objeto entero) sin feed | **Compatible.** «(`null` sin feed)» admite esa lectura, y el ejemplo de design §7 la apoya. Que `create_app` sin `gtfs` informe `degraded` es coherente. La persona puede confirmarlo, pero no bloquea |
| Caché de nginx distinta del patrón de design §4 | **Cumple AC-06 mejor que el esqueleto**: el patrón por extensión haría inmutables durante 1 año ficheros sin *hash* (`registerSW.js`, iconos). Pero design §10 no la incluye entre las decisiones locales permitidas. **Para la persona:** ratificarla y actualizar design §4 en la próxima versión de la spec. No bloquea |
| `resolver 127.0.0.11` + `proxy_pass` con variable | **Conforme.** No contradice el design. Evita depender de la IP del backend al recrearlo y que `nginx -t` lo necesite. La URI y la consulta llegan intactas (comprobado con `smoke`) |
| Permisos de `data/` (`chown 10001` no recursivo) | **Funciona** en el despliegue y en `gtfs-update.sh` (comprobado), pero provoca B-2 |
| `AVISABUS_ENV_FILE` (`env_file` con `path`/`required`, por defecto `.env.prod`) | **Conforme.** Con el valor por defecto se comporta como design §3. Necesita Compose ≥ 2.24, y la guía lo dice |
| Otras (HSTS sin `includeSubDomains`, `ENV AVISABUS_ENV=prod` en la imagen, `VACUUM` que si falla avisa y reinicia, `degraded` como aviso en `smoke`) | Dentro de lo que permiten los AC y design §10 |

### Resto de la lista de comprobación (docs/verification.md §4)

- **Arquitectura:** `lint-imports` OK. Ni el vigilante ni `/health` usan `datetime.now()`; toman la fecha del `Clock`. Los puertos se cablean en `main.py`.
- **Tests:** sin red (el test de AC-09 usa solo `allow_hosts(127.0.0.1)`) y sin *sleeps* reales. No son tautológicos: los mutantes los hacen fallar.
- **Privacidad y seguridad:**
  - Ningún secreto en imágenes ni en el repositorio. Las plantillas solo tienen marcadores, y `.dockerignore` excluye `**/.env*`.
  - `deploy/.env.prod` y `deploy/ship.env` están en `.gitignore`. `ship.sh` nunca copia `.env.prod`.
  - El backend corre sin root, sin puertos publicados y solo en la red interna.
- **Frontend:** no hay textos nuevos de interfaz; axe en verde.
- **Convenciones:** Conventional Commits con ámbito `deployment_rpi`.
- **Alcance:** todos los cambios están dentro de la feature. `openapi.json` y `schema.d.ts` se regeneraron por el cambio de `/health`. `feature_list.json`, `progress/current.md` y `history.md` están en commits del orquestador. No hay cambios en `docs/` ni en `specs/`.
