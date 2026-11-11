# Revisión: driver_gps_simulator
Ciclo: 1 · Fecha: 2026-11-11 · Agente: reviewer
Spec: `specs/driver_gps_simulator/` v1.0 (APPROVED) · Rama `feat/driver_gps_simulator`, diff
`origin/feat/driver_ui...HEAD`.

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Los cinco AC tienen tests que verifican el comportamiento, la
verificación completa está en verde y el simulador funciona también con sockets reales: recorrido
completo, Ctrl+C real y error de salida inexistente. Hay cuatro hallazgos no bloqueantes y una
nota informativa sobre `driver_session` N-05.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `tests/integration/test_cli_simulate.py:269` (orden `POST /sessions` → `GET /lines` → `GET /departures` → `PUT …/service` → posiciones → `DELETE`, primera salida libre), `:319` (salta las ocupadas), `:329` (`--departure 08:48`), `:338` (`--trip`), `:311` (código en `AVISABUS_SIM_CODE`), `:297` (`recorded_at` nuevo en cada envío y esperas de `--interval-s`), `:346` (User-Agent), `:374` (opciones inválidas: código 2, ninguna petición) | OK | Mutantes detectados: `ignore-taken` (no salta las ocupadas), `departure-utc` (`--departure` comparado en UTC) y `same-recorded-at` (mismo `recorded_at` en todos los envíos). |
| AC-02 | `tests/unit/test_route_simulation.py:54`, `:65`, `:82`, `:89`, `:100`, `:111`, `:118`, `:135`, `:145`, `:164`; `tests/integration/test_cli_simulate.py:387` (el ruido con semilla llega a la API y es reproducible) | OK | El trazado sintético va sobre un meridiano, así que lo esperado no depende del código probado. Mutantes detectados: `dwell-floor`, `no-truncate`, `dwell-last`, `noise-x2` y `noise-unseeded`. |
| AC-03 | `test_cli_simulate.py:269` (última parada: `finished` en el último estado, `DELETE` 204, `ENDED`, tabla vacía, código 0), `:407` (`KeyboardInterrupt` desde la espera falsa), `:426` (cancelación, como hace `asyncio.run`), `:451` (SIGINT real, **no se salta**, comprobado con `-v`) | OK | Mutantes detectados: `no-delete` y `ctrlc-exit1`. Ejecución real con sockets: Ctrl+C a los 6 s, código 0, "Turno finalizado." y 0 turnos abiertos. Ver N-02. |
| AC-04 | `test_cli_simulate.py:470` (código inexistente), `:480` (revocado), `:491` (429), `:503` (línea), `:516` (sentido, con la lista de sentidos), `:535` (salida o viaje inexistente, **con la lista de salidas disponibles**), `:550` y `:563` (ocupada antes de elegirla y por carrera con 409), `:580`, `:596`, `:611`, `:633`, `:653`, `:672` | OK | En todos: código 1, mensaje claro y ningún turno propio abierto. `:550` y `:563` comprueban que el turno ajeno sigue abierto. Mutantes detectados: `abort-exit0`, `no-listing` y `dir-not-checked`. Ejecución real con `--departure 03:00`: código 1, lista de salidas y 0 turnos abiertos. |
| AC-05 | `test_cli_simulate.py:694` (una línea por envío con distancia, próxima parada y estado, comparados con la respuesta de `GET …/current` de ese envío), `:725` (ni el código, con o sin espacio, ni el token, con los logs JSON reales a DEBUG), `:738` (lo mismo en un error), `:747` (`--help` con la variable puesta), `:758` (configuración rota sin traza) | OK, con N-03 | Mutantes detectados: `print-code` y `log-token`. Sobrevive `state-not-from-api` (`GPS OK` fijo en la salida), ver N-03. En la ejecución real, ni el código ni `Bearer` ni `session_token` aparecen en stdout o stderr del simulador ni en el log del servidor. |

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre): **OK, todo en verde**. Backend: format,
  lint, mypy (150 ficheros), lint-imports, pytest 1913 passed y 12 deselected, cobertura 99 %.
  Frontend: Vitest 660 passed y 2 skipped, build y bundle 5 passed, Playwright y axe 132 passed
  (12 skipped, que son las de otros perfiles, preexistentes). `feature_list.json` y trazabilidad
  en verde.
- `cd backend && uv run pytest -m slow`: 12 passed. Sale con código distinto de 0 solo por el
  umbral global de cobertura (69 % < 80 %) al ejecutar el subconjunto `slow`. Es preexistente y
  ajeno a la feature.
- `uv run pytest tests/integration/test_cli_simulate.py tests/unit/test_route_simulation.py -v`:
  56 passed, ninguno saltado (incluido `test_a_real_sigint_ends_the_shift`).
- **Mutantes**, sobre una copia de `HEAD` en el scratchpad (`git archive`, sin tocar el repo):
  15 de 17 detectados. Sobreviven `no-uncancel` (N-02) y `state-not-from-api` (N-03).
- **Ejecución real**, con un `uvicorn` local en el puerto 8765 sobre una copia de
  `data/avisabus.sqlite` en el scratchpad y un código creado con `avisabus driver-codes create`
  en esa copia. Sin red externa. Ya está parado.
  1. Ctrl+C a los 6 s (`--speed-kmh 180 --interval-s 0.5`): código 0, "Interrumpido por el
     usuario." y "Turno finalizado.", 0 turnos.
  2. Recorrido completo de la línea 93, sentido 0 (`--speed-kmh 360 --interval-s 0.5 --dwell-s 0
     --noise-m 20 --seed 5`): 205 envíos, 9 528 m. El último dice "en parada Passeig Marítim -
     Hospital Malva-rosa · próxima parada: ninguna · turno: GPS OK · recorrido terminado". Código 0
     y 0 turnos.
  3. `--departure 03:00`: código 1, la lista de salidas en stderr y 0 turnos.
  En los tres casos, ni el código ni el token aparecen en la salida del simulador ni en el log del
  servidor (458 líneas).
- Alcance: `git diff --stat origin/feat/driver_ui...HEAD`. El código solo toca
  `cli/simulate.py`, `cli/main.py` (registro), `domain/services/route_simulation.py` y sus dos
  tests, como dicen `tasks.md` y `design.md` §1. El resto son ficheros de progreso y
  `feature_list.json`, en commits `chore(progress)` del orquestador. Los commits siguen
  Conventional Commits con el ámbito de la feature.

## Juicio de las decisiones locales (`progress/impl_driver_gps_simulator.md`)

| # | Decisión | Juicio |
|---|---|---|
| 1 | Llegada a la parada más `ceil(dwell/interval)` envíos en ella; también en la primera, y en la última un solo envío | Es una lectura fiel de design §2 ("se queda en ella `ceil(dwell/interval)` pasos"; "termina con un fix en la última parada") y de AC-02 ("en cada parada del viaje"). El tiempo parado es ≥ `--dwell-s`. **Aceptada.** |
| 2 | `accuracy_m = 5` | La API la exige (`driver_session` AC-08) y la spec no la fija. El servidor solo la guarda. No inventa contrato del simulador. **Aceptada**, con una nota en N-04. |
| 3 | `--departure` en hora local `Europe/Madrid`; 24:xx como 00:xx | Es la lectura natural de "la de esa hora" (AC-01): `GET /departures` da instantes absolutos y el conductor piensa en hora local. **Aceptada.** |
| 4 | Opciones inválidas, código 2 | AC-04 fija el 1 solo para código, línea, sentido, salida u ocupada. Las opciones mal formadas son errores de uso de Typer y salen antes de abrir turno. La exclusión `--departure`/`--trip` está en la sintaxis de AC-01 (`[--departure HH:MM \| --trip TRIP_ID]`). No contradice ningún AC. **Aceptada.** |
| 5 | Distancia recorrida desde la primera parada; próxima parada = `upcoming[0]`; estado = `gps`, `off_route` y `finished` | Coincide con AC-05 y con `GET …/current` (`driver_session` design §3). **Aceptada.** |
| 6 | `KeyboardInterrupt` y `CancelledError` igual, `uncancel()`, `DELETE` en `finally` | Coincide con design §2 ("try/finally garantiza DELETE"). Funciona con SIGINT real. `uncancel()` no tiene test que lo distinga (N-02). **Aceptada.** |
| 7 | Robustez: 429, 401 a mitad, 503, transporte, sin trazado; código 1 si el `DELETE` falla; 401 en `DELETE` = ya cerrado | AC-03 condiciona el 0 a haber finalizado el turno, así que salir con 1 si no se pudo no lo contradice. El 401 en `DELETE` como "ya cerrado" es coherente con `CloseDriverSession` idempotente. **Aceptada.** |
| 8 | Sin trazas; `repr=False` en el código; token solo en la cabecera | Refuerza AC-05 frente a las trazas de Typer/rich con `show_locals` (la app raíz no lo desactiva). Cubierto por `:672` y `:758`. **Aceptada.** |
| 9 | `httpx`/`httpcore` a `WARNING` | Solo afecta a la verbosidad. No oculta nada que pida la spec. **Aceptada.** |
| 10 | `TripRoutes` sobre `SqliteNetworkRepository(container.engine)` sin tocar `CliContainer` | Cumple design §1 ("lee de la base de datos local, `NetworkRepository`") y usa las mismas distancias que el servidor. Instanciar el adaptador concreto en el adaptador de entrada se aparta de la convención de la CLI (N-01). **Aceptada, no bloqueante.** |
| 11 | `build_runtime()` inyectable | Coincide con design §2 ("sleep inyectable") y §3, y sigue el patrón de `cli/sae.py`. **Aceptada.** |
| — | `AVISABUS_SIM_CODE` leída del entorno del proceso y fuera de `.env.example` | **Correcta.** design §2 la prescribe como `typer.Option(..., envvar="AVISABUS_SIM_CODE")`, y Typer la lee del entorno del proceso. `Settings` lee `.env` con `extra="ignore"`, así que una línea en `.env` no tendría efecto y documentarla en `.env.example` sería engañoso. Además, un código de conductor no tiene "default seguro". `docs/conventions.md` §53 ("documentados en `.env.example`") se refiere a la configuración de `pydantic-settings`, y `test_env_example_documents_every_setting` exige exactamente los campos de `Settings`. Queda en `--help` (`[env var: AVISABUS_SIM_CODE]`, comprobado por `:747`). Ver la propuesta de documentación en N-04. |

Ninguna decisión inventa contrato ni contradice un AC.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes

- **N-01 · Arquitectura · `backend/src/avisabus/adapters/inbound/cli/simulate.py:34` y `:155`.**
  `simulate.py` instancia `SqliteNetworkRepository(container.engine)`. Los demás comandos de la CLI
  reciben las implementaciones concretas de `build_cli_container`, la raíz de composición de la
  CLI (`docs/architecture.md`: "solo `main.py` (composition root) conoce las implementaciones
  concretas"). El impacto es nulo, porque `TripRoutes` solo ve el puerto `NetworkRepository`. Lo
  más limpio sería exponer `trip_routes` o `network` en `CliContainer`. Ahora no se hizo porque
  `tasks.md` T-02 limita los ficheros a `cli/{simulate,main}.py`. Se puede dejar así o tratarlo
  en una tarea de mantenimiento.
- **N-02 · Tests · `simulate.py:225-228` (`_consume_cancellation` → `task.uncancel()`).** El
  mutante que lo quita sobrevive a los 56 tests, también al de SIGINT real
  (`test_cli_simulate.py:451`). Sobre `ASGITransport`, `asyncio.Runner` y las esperas siguientes
  funcionan igual sin él. El `uncancel()` es defensivo (para `anyio`/`httpcore` con sockets
  reales, que comprueban `Task.cancelling()`). En la ejecución real con sockets el Ctrl+C cierra
  bien el turno con el código tal cual está, pero ningún test fija por qué hace falta. Bastaría
  una línea en el docstring o un test que lo justifique.
  Relacionado (caso borde, sin AC): un Ctrl+C mientras `POST /sessions` está en vuelo
  (`simulate.py:206`) deja `_auth = None`. Si el servidor llegó a crear el turno, no se envía
  `DELETE` y lo cierra el *reaper* por inactividad (10 min). Con un segundo Ctrl+C durante el
  `DELETE` pasa lo mismo. Es aceptable, pero conviene saberlo.
- **N-03 · Tests de AC-05 · `test_cli_simulate.py:705-707` frente a `simulate.py:368-372`.** En
  todos los escenarios de test `gps` vale siempre `OK` y `off_route` siempre `false`, así que el
  mutante que escribe `GPS OK` fijo, sin leer `state['gps']`, sobrevive. Tampoco hay ningún test
  que muestre "fuera de ruta". La próxima parada y "recorrido terminado" sí se comparan con la
  respuesta de la API, y por eso AC-05 queda verificado en lo esencial. Para cerrar el hueco
  bastaría un caso con `--interval-s 35` (da `STALE` según `driver_session` AC-11) o una posición
  fuera del trazado.
- **N-04 · Documentación y spec (propuesta para la persona, no para el implementer).**
  1. El uso de `avisabus simulate` y de `AVISABUS_SIM_CODE` solo está en `--help`. Si se quiere
     que aparezca en `README.md` o en `docs/conventions.md` §8, o que la regla de
     `docs/conventions.md` (configuración en `.env.example`) aclare que se refiere a `Settings` y
     no a las variables de entorno de los comandos de la CLI, es un cambio de `docs/` y le
     corresponde a la persona.
  2. `accuracy_m` del simulador (5 m) no figura en la spec. Si se revisa la spec, puede añadirse
     a design §2.
  3. Cosmético: los logs JSON van a stdout mezclados con las líneas de progreso. En la ejecución
     real aparece el aviso `security.dev_stop_token_secret`. No afecta a ningún AC.

## Información: `driver_session` N-05 (umbral de 150 m medido con una sola semilla)

**¿Se puede volver a medir con el simulador?** Solo en parte, y no es la mejor herramienta.
El simulador pasa por la API real y permite elegir semilla (`--seed`). El progreso del servidor se
puede deducir de su salida (distancia de la próxima parada) y compararlo con el recorrido real.
Sin embargo:
1. Su ruido es **uniforme en un disco e independiente**, no gaussiano σ = 10 m con correlación
   ρ = 0,95, que es el modelo que fija `driver_session` AC-09.
2. Hace **un viaje por ejecución**, entre las salidas de la ventana actual, en tiempo real.
3. Redondea a metros enteros.

La medición directa de N-05 es repetir `tests/integration/test_upcoming_stops_real_shapes.py`
con otras semillas. Lo he hecho, como **información**, sobre la copia del scratchpad (cambiando
solo `SEED`, niveles σ = 10 m, 94 trazados y 18 714 posiciones por nivel):

| SEED | σ10 correlado (máx. delante / detrás) | σ10 independiente (máx. delante / detrás) |
|---|---|---|
| 20261109 (la del repo) | dentro de 150 m (pasa) | dentro de 150 m (pasa) |
| 1 | 102,4 / 144,4 m: pasa | 111,0 / 99,0 m: pasa |
| **2** | 110,5 / **341,7 m: 5 posiciones fuera, 1 trazado** | 120,6 / 90,1 m: pasa |
| 3 | 91,0 / 98,9 m: pasa | 105,6 / 54,7 m: pasa |
| **4** | 119,6 / **350,5 m: 5 posiciones fuera, 1 trazado** | 126,2 / 81,1 m: pasa |
| 5 | 116,9 / 85,3 m: pasa | 107,8 / 65,5 m: pasa |

Esto confirma la sospecha de N-05: con ruido correlado σ = 10 m, el criterio "ninguna posición a
más de 150 m por detrás" de `driver_session` AC-09 falla en 2 de 5 semillas, siempre en un único
trazado y por detrás, con unos 340-350 m de retraso. Es decir, el progreso se queda atrás, no salta
adelante. **No afecta a esta feature** ni bloquea su revisión. Si se quiere actuar, corresponde a
`driver_session` (spec o regla de proyección) y pasa por la persona (CP-3). Para reproducirlo,
cambia `SEED` a 2 o a 4 en ese test y ejecuta `uv run pytest -m slow -k sigma10_correlated -s`.
