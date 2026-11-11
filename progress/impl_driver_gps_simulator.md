# Implementación: driver_gps_simulator
Spec: specs/driver_gps_simulator/ (v1.0, APPROVED, PR #46) · Ciclo de revisión: 0 · Rama:
`feat/driver_gps_simulator` (apilada sobre `feat/driver_ui`, con `driver_session` v1.3).
Exploración: no necesaria (tasks.md).

## Tareas
- [x] T-01 `simulate_route` (AC-02) — `backend/src/avisabus/domain/services/route_simulation.py`,
  `backend/tests/unit/test_route_simulation.py` (commit 9072e1d)
- [x] T-02 Comando `simulate` con cliente HTTP, cierre garantizado y salida por consola (AC-01, AC-03,
  AC-04, AC-05) — `backend/src/avisabus/adapters/inbound/cli/simulate.py`, registro en
  `cli/main.py`, `backend/tests/integration/test_cli_simulate.py` (commit 7ec43fa)
- [x] T-03 Verificación completa (este fichero)

Tests vistos en rojo antes del código: los de T-01 (módulo inexistente) y los de T-02 (con
`simulate.py` apartado: error de importación en la recogida).

Tests por AC:
- AC-01: `test_cli_simulate.py` — salida libre por defecto con todos los valores por omisión
  (orden de llamadas a la API: `POST /sessions`, `GET /lines`, `GET /departures`,
  `PUT …/service`, posiciones, `DELETE`), salta las ocupadas, `--departure HH:MM`, `--trip`, código
  desde `AVISABUS_SIM_CODE`, `recorded_at` nuevo en cada envío (= reloj del simulador, avanzado por
  la espera falsa) y esperas de `--interval-s`, User-Agent, opciones inválidas (código 2, sin
  ninguna petición).
- AC-02: `test_route_simulation.py` (trazado sintético sobre un meridiano: avance
  `velocidad × intervalo`, paso truncado en la parada, `ceil(dwell/interval)`, una sola posición en
  la última parada, posiciones sobre el trazado, ruido ≤ N m, reproducible con la semilla y en
  todas las direcciones, argumentos inválidos) + `test_sends_the_noisy_positions_of_the_seed`.
- AC-03: recorrido completo hasta la última parada (el servidor marca `finished` en el último
  estado; `DELETE` con 204, listener `ENDED`, tabla vacía, código 0); `KeyboardInterrupt` lanzado
  desde la espera falsa; cancelación de la tarea como hace `asyncio.run` con el primer Ctrl+C; y
  una señal `SIGINT` real.
- AC-04: código inexistente, revocado y bloqueo por intentos (429); línea inexistente; sentido
  inexistente (con la lista de sentidos); salida u viaje inexistentes (con la lista de salidas
  disponibles); salida ocupada (antes de elegirla y por carrera, 409); sin salidas libres; viaje
  ausente de la base de datos local; turno cerrado por el servidor a mitad de recorrido; servidor
  inalcanzable; turno que no se puede finalizar; fallo inesperado (sin traza). En todos, código 1 y
  ningún turno propio abierto.
- AC-05: una línea por envío con distancia recorrida, próxima parada y estado del turno, que
  coinciden con la respuesta de `GET …/current` de ese envío; ni el código (con y sin espacio) ni
  el token en la salida con los logs JSON reales (también en un error); `--help` con la variable
  de entorno puesta no muestra el código; una configuración rota sale con 1 sin traza.

## Decisiones locales
El `design.md` no tiene sección de decisiones locales permitidas; estas son lecturas del diseño o
detalles que la spec no fija y que no cambian ningún contrato. Las dejo a la vista del reviewer:

1. **Paradas y espera (lectura del design §2).** "Al cruzar una parada se queda en ella
   `ceil(dwell/interval)` pasos": el paso que alcanzaría o cruzaría la parada termina en ella
   (posición con `at_stop`) y después se envían `ceil(dwell/interval)` posiciones más en la misma
   parada; así el autobús está parado al menos `--dwell-s`. Se aplica también a la primera parada
   (el AC-02 dice "en cada parada del viaje") y no a la última, donde el diseño dice "termina con un
   fix en la última parada".
2. **`accuracy_m` = 5 m** en todas las posiciones (constante `ACCURACY_M`). La API la exige y la
   spec no la fija; el servidor solo la guarda (no interviene en la proyección ni en el estado).
3. **`--departure HH:MM`** se compara con la hora local de `departure_at` en `Europe/Madrid`
   (`LOCAL_TIMEZONE`, la del servidor); una salida de las 24:15 del día de servicio anterior se pide
   como `00:15`. Si varias salidas coinciden con la hora o el viaje, se toma la primera libre; si
   todas están ocupadas, error "ocupada". Formato aceptado: `H:MM` o `HH:MM` de 00:00 a 23:59.
4. **Opciones inválidas** (`--departure` y `--trip` a la vez, hora mal formada, velocidad o
   intervalo ≤ 0, espera o ruido < 0, no finitos): error de uso de Typer con código **2**, antes de
   abrir turno (el AC-04 fija el 1 solo para código, línea, sentido y salida).
5. **"Distancia recorrida"** en consola = metros sobre el trazado desde la primera parada; la
   **próxima parada** es `upcoming[0]` de `GET …/current` (nombre, `stop_id` y distancia); el estado
   es `gps`, `off_route` y `finished` de esa misma respuesta.
6. **Ctrl+C:** `asyncio.run` convierte el primer Ctrl+C en la cancelación de la tarea principal; el
   simulador trata igual `KeyboardInterrupt` y `CancelledError` (y hace `uncancel()` para poder
   enviar el `DELETE`). El `DELETE` está en un `finally`.
7. **Robustez (fuera de los AC, código 1 con mensaje):** 429 al iniciar, 401 a mitad de recorrido
   (turno cerrado por el servidor), 503 (sin red), errores de transporte de `httpx`, viaje sin
   trazado en la base de datos local y respuesta inesperada. Si el `DELETE` final falla, sale con 1
   y avisa de que el servidor cerrará el turno por inactividad. Un 401 en el `DELETE` cuenta como
   turno ya cerrado.
8. **Sin trazas:** cualquier excepción no prevista dentro del simulador o al preparar la base de
   datos se muestra solo con su tipo (salvo `ConfigurationError`, cuyo mensaje es de configuración),
   porque las trazas enriquecidas de Typer/rich muestran las variables locales, entre ellas el
   código. `SimulationOptions.code` lleva `repr=False` y el token solo vive en la cabecera
   `Authorization` del cliente (`DriverApiClient.__repr__` no la incluye).
9. **Logs de `httpx`/`httpcore` a `WARNING`** en el simulador: a `INFO` escriben una línea JSON por
   petición que tapaba las líneas de progreso (no contienen ni el código ni el token).
10. **Lectura del trazado:** se reutiliza `TripRoutes` de `application/driver_sessions.py` sobre
    `SqliteNetworkRepository(container.engine)`, de modo que las distancias de las paradas (metros
    reales) son exactamente las del servidor. `CliContainer` no se ha tocado.
11. **Inyección para tests:** `build_runtime()` devuelve `SimulatorRuntime(clock, sleep,
    transport)`; los tests lo sustituyen (FakeClock, espera falsa que avanza el reloj, transporte
    ASGI que graba peticiones), igual que `build_cli_container` y `configure_logging`.

## Bloqueos
Ninguno.

Observación para el orquestador / reviewer: `AVISABUS_SIM_CODE` no es un ajuste de `Settings` (la
lee Typer del entorno del proceso; ponerla en `.env` no tendría efecto), así que no se ha añadido a
`.env.example` (además, `test_env_example_documents_every_setting` exige que `.env.example`
documente exactamente los campos de `Settings`). Queda documentada en `--help`
(`[env var: AVISABUS_SIM_CODE]`).

## Verificación
- T-01: `uv run pytest tests/unit/test_route_simulation.py` → 18 passed (el fallo de cobertura
  < 80 % es el umbral global al ejecutar un solo fichero; `route_simulation.py` al 100 %).
- T-02: `uv run pytest tests/integration/test_cli_simulate.py` → 38 passed (mismo aviso de
  umbral global).
- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre) → **OK verify: todo en verde**:
  backend format, lint, types (150 ficheros), architecture (2 contratos), tests 1913 passed,
  12 deselected, cobertura `domain` + `application` 99,66 %; frontend format, lint, types, Vitest
  660 passed y 2 skipped, build + bundle 5 passed, Playwright + axe 132 passed; `feature_list.json`
  y trazabilidad AC→test en verde.
- `cd backend && uv run pytest -m slow` → 12 passed (el aviso de cobertura < 80 % es el umbral
  global sobre el subconjunto `slow`).
