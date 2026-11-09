# Implementación: driver_session
Spec: specs/driver_session/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-09

## Tareas
- [x] T-01 Modelos, puertos, errores, `SqliteDriverSessionRepository` y consulta de turno abierto para `driver-codes list/revoke` (AC-14) (commit cd4d2e0)
- [x] T-02 `list_lines` y `departures` en la red; `ListDriverLines` y `ListDepartures` (AC-05, AC-06) (commit 26f7792)
- [x] T-03 `project_progress` y `upcoming_stops` (AC-09, AC-10) (commit 4a7326b)
- [x] T-04 Casos de uso de sesión, `CloseDriverSession`, `NoopDriverSessionListener` (AC-01, AC-02, AC-03, AC-07 – AC-12, AC-15) (commit aa956b5)
- [x] T-05 Endpoints `/driver`, autenticación por token, errores, configuración y composición (AC-01 – AC-08, AC-11, AC-12, AC-15) (commit a7b6a88)
- [x] T-06 `ReapDriverSessions` y su tarea de fondo (AC-13) (commit 04651ae)
- [x] T-07 Contrato del frontend regenerado (`npm run gen:api`) y verificación completa (commit de este fichero)

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

Ninguno.

### Avisos para la persona (no bloquean)
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

## Verificación

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre), salida 0, "verify: todo en verde":

| Paso | Resultado |
|---|---|
| Backend: `ruff format --check`, `ruff check`, `mypy`, `lint-imports` | OK (2 contratos respetados) |
| Backend: `pytest` | 1667 passed, 6 deselected; cobertura `domain` + `application` 99,60 % |
| Frontend: `format:check`, `lint`, `typecheck`, `build` | OK |
| Frontend: `vitest` | 563 passed, 2 skipped (55 ficheros) |
| Frontend: Playwright + axe | 126 passed |
| Trazabilidad AC → test (`scripts/check_traceability.py`) | OK |
