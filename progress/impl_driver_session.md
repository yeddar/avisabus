# Implementación: driver_session
Spec: specs/driver_session/ (v1.2, APPROVED) · Ciclo de revisión: 2 (corrige F-01 de `progress/review_driver_session.md` y aplica T-08) · Agente: implementer · Fecha: 2026-11-09

## Tareas
- [x] T-01 Modelos, puertos, errores, `SqliteDriverSessionRepository` y consulta de turno abierto para `driver-codes list/revoke` (AC-14) (commit cd4d2e0)
- [x] T-02 `list_lines` y `departures` en la red; `ListDriverLines` y `ListDepartures` (AC-05, AC-06) (commit 26f7792)
- [x] T-03 `project_progress` y `upcoming_stops` (AC-09, AC-10) (commit 4a7326b)
- [x] T-04 Casos de uso de sesión, `CloseDriverSession`, `NoopDriverSessionListener` (AC-01, AC-02, AC-03, AC-07 – AC-12, AC-15) (commit aa956b5)
- [x] T-05 Endpoints `/driver`, autenticación por token, errores, configuración y composición (AC-01 – AC-08, AC-11, AC-12, AC-15) (commit a7b6a88)
- [x] T-06 `ReapDriverSessions` y su tarea de fondo (AC-13) (commit 04651ae)
- [x] T-07 Contrato del frontend regenerado (`npm run gen:api`) y verificación completa (commit f8466bf)

### Ciclo 2 (v1.1 y v1.2)
- [x] F-01 (bloqueante, AC-08): fechas fuera del calendario al pasar a UTC → `422` y no `500` (commit 8e0826d)
- [x] N-02 (opcional): dígitos no ASCII por HTTP con el *hasher* real (commit fbf8093)
- [x] T-08 (AC-09, AC-10): ventana `20 m/s × Δt + 50 m`, primera posición, `progress_recorded_at` (commit f34e3de, WIP) y metros reales con v1.2 (commit 587702a)

## Decisiones locales

`design.md` §7 permite dos: la caché de distancias de paradas y la estructura de `LineDirectionsView`
y `Departure`. El resto son detalles que la spec no fija; ninguno cambia el contrato y la persona o el
reviewer pueden pedir otra cosa sin rehacer nada más.

**Permitidas por el design**
- **Caché (`TripRoutes`):** por versión del feed, `shape_id` y patrón de paradas (`stop_id` y
  `stop_sequence`). Solo con `shape_id` serían incorrectas las variantes con otras paradas o numeración
  (`driver_demand` empareja por `stop_sequence`). Se vacía al cambiar de versión del feed.
- **`LineDirectionsView`:** `line`, `color`, `text_color`, `directions` (`DirectionHeadsign`).
- **`Departure`:** lo que da la red (`trip_id`, `service_date`, `departure_s`, `first_stop_name`,
  `headsign`). El caso de uso añade `departure_at` y `taken` en `DepartureOption`.

**Detalles que la spec no fija**
- **Código con formato incorrecto (AC-02):** se trata como inexistente: `401`, cuenta como fallo y
  `driver.login_failed`. Solo se admiten dígitos ASCII (`١٢٣…` haría fallar el *hash* con un 500). Un
  cuerpo sin `code` o con otro tipo es un `422` de validación.
- **Quinto fallo (AC-02):** responde `401`; el `429` empieza en el siguiente intento.
- **`LoginLimiter`:** `InMemoryRateLimiter` por sí solo no sirve: reabre el paso cuando el fallo más
  antiguo sale de la ventana, no 15 min después del último, y no se puede consultar sin registrar un
  intento. Por eso admite `max_failures − 1` fallos, y el que completa la cuenta fija el bloqueo hasta
  `ahora + 15 min`. Solo los fallos llaman a `acquire`, como pide el design. Consecuencia:
  `AVISABUS_DRIVER_LOGIN_MAX_FAILURES` tiene mínimo 2.
- **`recorded_at` futuro (AC-08):** `InvalidPositionError` (excepción de dominio nueva) → `422`
  `about:blank`, porque el design no da tipo. Una fecha sin zona se rechaza con `422` de validación.
- **Referencias de tiempo:** `STALE` y el *reaper* usan `last_position_at` (instante del servidor, no
  el reloj de la tablet). `STALE` si pasan más de 30 s; `IDLE` con 10 min o más.
- **Sin progreso (AC-10, AC-11):** sin posición proyectada, `upcoming` vacío y `finished=false`; no se
  puede calcular "por delante del progreso".
- **Viaje que ya no está en la red activa:** la posición se guarda, el progreso no cambia y no hay
  próximas paradas; el turno sigue funcionando.
- **`project_progress` (AC-09):** en un tramo recortado por la ventana se proyecta sobre la parte
  incluida; a igual distancia (al milímetro), gana el punto más temprano.
- **Motivo de cierre:** `REVOKED` gana a `IDLE`. Un código inexistente se trata como revocado.
- **`CloseDriverSession(session_id, reason)`:** el puerto no tiene búsqueda por id; el `started_at`
  para la duración se obtiene recorriendo `list_all` (pocos turnos abiertos).
- **Componentes no listados en el design:** `AuthenticateDriverSession` (lo usa `current_session`),
  `Sha256SessionTokenHasher` y `http/access_log.py` (ver abajo).
- **IP en el log de acceso (AC-15):** `uvicorn.access` escribe la IP del cliente. `create_app` instala
  un filtro que la sustituye por `-` solo en `/api/v1/driver` (se conserva el resto de la línea).
- **Tarea de fondo en `main.py`, no en `app.py` (T-06):** `.importlinter` declara `adapters` y
  `background` independientes, así que `app.py` no puede importar `background.driver_tasks`. Va en el
  `lifespan` de `main.py`, como las tareas de `alert_expiry`.

**Código de otras features tocado**
- `gtfs_import` (autorizado por T-02): `list_lines` y `departures` en `NetworkRepository`,
  `SqliteNetworkRepository` y `domain/models/network.py`.
- `driver_codes_cli`: `_no_open_session` sustituido por la consulta real (AC-14). Se amplía
  `test_cli_driver_codes.py`.
- `tests/integration/test_main_position.py` (`position_estimation`): la sonda listaba toda ruta que
  terminase en `/position` y ahora incluiría `/driver/sessions/current/position`; se excluye `/driver`.
  Sin esto el test falla por el endpoint nuevo.
- `main.py`, `http/app.py`, `http/errors.py`, `http/container.py`, `config.py` y `.env.example`: la
  composición y configuración que pide T-05.

## Bloqueos

Ninguno abierto. El CP-3 de T-08 se resolvió con la spec v1.2 (PR #51), apoyada en `position_estimation`
v1.4 (T-11):
- **P-02 (resuelto):** `shape_dist_traveled` no son metros (longitud del feed 1,66–4,25 veces la real).
  v1.2 mide el progreso, la ventana y los márgenes en metros reales.
- **P-03 (resuelto):** umbral de la prueba con trazados reales a σ 10 m fijado en 150 m.

### Resultado de la prueba con trazados reales (`test_upcoming_stops_real_shapes.py`)

94 trazados, 18 714 posiciones por nivel, 30 km/h, una posición cada 5 s, semilla 20261109, autobús y
error en metros reales, con `UpdateDriverPosition` y `TripRoutes` reales:

| Ruido | Máx. delante (m) | Máx. detrás (m) | Posiciones > 150 m |
|---|---|---|---|
| Sin ruido (control) | 0,0 | 41,7 | 0 |
| σ 3 m, correlado ρ 0,95 | 105,9 | 89,4 | 0 |
| σ 5 m, correlado | 95,7 | 127,4 | 0 |
| σ 5 m, independiente | 107,0 | 82,9 | 0 |
| σ 10 m, correlado (AC-09) | 97,5 | 66,9 | 0 |
| σ 10 m, independiente (AC-09) | 104,7 | 56,7 | 0 |

Antes del cambio, con las distancias del feed y la misma prueba: 6 de 6 fallidos, con 23 099 m por
delante y 8 709 m por detrás como máximos, y unas 17 500 posiciones fuera por nivel.

### Aviso para la persona: el cumplimiento depende de la semilla

AC-09 fija una semilla, y con la del test se cumple (la elegí antes de ver resultados, en el ciclo 2 de
v1.1). Repitiendo con las semillas 1 a 20 a σ 10 m (scratchpad, no forma parte de la suite):

| Ruido | Semillas con alguna posición > 150 m | Posiciones | Máx. delante / detrás (m) |
|---|---|---|---|
| Correlado ρ 0,95 | 5 de 20 | 28 | 130,8 / 422,2 |
| Independiente | 1 de 20 | 1 | 157,1 / 121,9 |

El test pasa, pero el umbral de 150 m no tiene margen frente a otras realizaciones del ruido. No he
diagnosticado el caso de 422 m por detrás. Conviene decidirlo al validar con `driver_gps_simulator`.

### Avisos para la persona del ciclo 0 (no bloquean)
- **Destinos de C2 y C3 (nota de `progress/current.md`).** La nota dice que el conductor vea todos los
  destinos del sentido y que "fuera de recorrido" use `shapes_for_direction`. Se ha seguido la spec, que
  es posterior (ADR-018): AC-05, el design §3 y `driver_ui.AC-02` piden un único `headsign` por sentido
  (el principal), y AC-09 mide contra el trazado **del viaje elegido**. Los dos destinos se ven por
  salida, porque AC-06 da el `headsign` de cada una (comprobado en C2 sentido 0 con el feed real: "Plaça
  d'Espanya - Ermita" y "Estació d'autobusos"). Efecto: si un conductor elige una salida del otro medio
  bucle del mismo sentido, verá `off_route`. `docs/use_cases.md` CU-08 4b sigue diciendo "trazado de la
  línea y sentido elegidos"; conviene alinearlo con AC-09 o, si se quiere la otra regla, cambiar la spec.
- **IP en el log de acceso fuera de `/driver`.** El filtro solo cubre esta feature. `alert_create` exige
  lo mismo ("NINGÚN log DEBERÁ incluir … la IP") y `./init.sh dev` arranca uvicorn con log de acceso, así
  que `/alerts` y el resto siguen escribiéndola. Propuesta: generalizar el filtro en
  `configure_logging` o usar `--no-access-log` en `deployment_rpi`.
- **Riesgo de AC-09 con GPS real.** Se aplica "segmento más cercano" al pie de la letra. En una calle
  recorrida a la ida y a la vuelta con trazados separados unos metros, la pasada de vuelta (hasta 3 km por
  delante) puede quedar más cerca por ruido del GPS, y el progreso no retrocede. Los tests cubren
  trazados idénticos. Conviene observarlo con `driver_gps_simulator` y en la demo del bloque.

## Decisiones locales del ciclo 2 (T-08)

- **Distancia devuelta en la primera posición:** `project_progress` devuelve la **mínima** al trazado
  aunque elija un tramo anterior dentro de los 30 m, porque AC-09 define "fuera de recorrido" por la
  distancia al trazado. Lo cubre `test_the_first_position_reports_the_real_distance_to_the_shape`.
- **`progress_recorded_at`:** se actualiza con toda posición aceptada sobre el recorrido, también si
  no avanza el progreso (design: "aceptada sobre el recorrido"). Fuera de ruta no cambia.
- **`elapsed_s` sin marca** (progreso sin `progress_recorded_at`): se trata como 0 (solo el margen).
- **ADR-011:** la tabla gana una columna sin migración. La BD de `data/` no tiene aún la tabla; una BD
  creada con la v1.0 fallaría al escribir hasta borrar la tabla (datos efímeros).
- **Paradas en metros (v1.2):** `TripRoutes` reutiliza `stop_distances` de `position_estimator` (antes
  `_stop_distances`, renombrada: cambio mínimo en código de `position_estimation`), que comprueba que
  exista `shape_dist_traveled` y aplica el `max` acumulado. Evita duplicar esa lógica.
- **El test real usa `TripRoutes`** con una red mínima, de modo que fallaría si la producción volviera a
  las unidades del feed. Los niveles σ 3 y σ 5 usan el mismo umbral de 150 m, aunque AC-09 solo lo fije
  para σ 10.
- **F-01:** `OverflowError` de `astimezone` → `InvalidPositionError` (`422`, igual que AC-08).

## Verificación

Ciclo 2 (v1.2) · `CI=1 ./init.sh verify --e2e` (puerto 4173 libre), salida 0, "verify: todo en verde":
backend 1711 passed, 12 deselected, cobertura 99,61 %; Vitest 563 passed y 2 skipped; Playwright + axe
126 passed; lint, tipos, arquitectura, build y trazabilidad en verde. `uv run pytest -m slow`: 12 passed.
Contrato OpenAPI sin cambios en T-08 (no hace falta `gen:api`).

Ciclo 0 · `CI=1 ./init.sh verify --e2e` (puerto 4173 libre), salida 0, "verify: todo en verde":

| Paso | Resultado |
|---|---|
| Backend: `ruff format --check`, `ruff check`, `mypy`, `lint-imports` | OK (2 contratos respetados) |
| Backend: `pytest` | 1667 passed, 6 deselected; cobertura `domain` + `application` 99,60 % |
| Frontend: `format:check`, `lint`, `typecheck`, `build` | OK |
| Frontend: `vitest` | 563 passed, 2 skipped (55 ficheros) |
| Frontend: Playwright + axe | 126 passed |
| Trazabilidad AC → test (`scripts/check_traceability.py`) | OK |
