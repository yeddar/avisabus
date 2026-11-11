# Revisión: driver_session
Ciclo: 1 de la v1.3 · Fecha: 2026-11-11 · Agente: reviewer · Spec: specs/driver_session/ v1.3 (APPROVED)
Base: `origin/develop...HEAD` (1bedfc7). Rama `feat/driver_session`. Cubre T-09 (commit 7193cd4) y T-07 repetida.

## Veredicto: APPROVED

T-09 cumple AC-08, AC-11 y AC-13 de la v1.3. Las tres decisiones locales caben en la spec. Los tests
cambiados no pierden fuerza: los sustituye la v1.3 o salen reforzados. No hay hallazgos bloqueantes.

## Matriz AC → evidencia

Rutas relativas a `backend/tests/`, con las líneas de HEAD. Los AC sin cambios en el código de la v1.3
(AC-01–AC-07, AC-09, AC-10, AC-12, AC-14 y AC-15) se dan por comprobados con la suite completa y la
trazabilidad en verde. Sus tests solo cambian por el renombrado del campo, sin perder ninguna aserción.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `integration/test_driver_api.py:173–199`; `unit/test_driver_login.py:86–121` | OK | `:97–101`: la sesión nueva tiene `last_fix_at` y `last_seen_at` a `None`. |
| AC-02 | `integration/test_driver_api.py:211–249`; `unit/test_driver_login.py:128–248` | OK | Sin cambios. |
| AC-03 | `integration/test_driver_api.py:262`; `unit/test_driver_login.py:257` | OK | Sin cambios. |
| AC-04 | `integration/test_driver_api.py:294–325`; `unit/test_driver_sessions.py:795` | OK | Sin cambios (N-01 sigue abierto). |
| AC-05 | `integration/test_driver_api.py:336,776`; `integration/test_network_departures.py:119,137`; `unit/test_departures.py:71,77` | OK | Sin cambios. |
| AC-06 | `integration/test_driver_api.py:358–433`; `integration/test_network_departures.py:142–232`; `unit/test_departures.py:83–214` | OK | Sin cambios. |
| AC-07 | `integration/test_driver_api.py:445–524`; `unit/test_driver_sessions.py:163–248` | OK | `:183`: elegir salida conserva `last_fix_at` y `last_seen_at`. |
| AC-08 | `integration/test_driver_api.py:536–640`, en especial `:549`, `:564` y `:574`; `unit/test_driver_sessions.py:267–380`, en especial `:268`, `:291`, `:302`, `:314`, `:324` y `:340` | OK | **v1.3.** Una posición nueva fija `last_fix_at` y `last_seen_at` con la hora del servidor y avisa al *listener*. Un reenvío (mismo `recorded_at`, también con otro huso) renueva solo `last_seen_at`: no cambia la posición, el progreso ni `last_fix_at`, y no avisa. Una posición más antigua, igual. Un `422` no es señal de vida. Por HTTP, ver las columnas en `:564` y `:574`. Mutantes detectados: `resend-no-save`, `resend-lt`, `resend-renews-fix`, `resend-notifies`, `new-no-seen` y `fix-recorded`. |
| AC-09 | `integration/test_upcoming_stops_real_shapes.py:216,224`; `unit/test_driver_sessions.py:391–684`; `unit/test_upcoming_stops.py:68–246` | OK | Los reenvíos ya no se proyectan. `:645` y `:655` mandan ahora la segunda posición 5 s después; si no, sería un reenvío. `:645` añade una aserción sobre el progreso. `pytest -m slow` en verde. Ver N-05. |
| AC-10 | `unit/test_upcoming_stops.py:261–326`; `unit/test_driver_sessions.py:574–716` | OK | Sin cambios. |
| AC-11 | `integration/test_driver_api.py:651–740`, en especial `:689` y `:701`; `unit/test_driver_sessions.py:724–786`, en especial `:761`, `:772` y `:781` | OK | **v1.3.** `STALE` se calcula con `last_fix_at`. En `:781`, con `last_seen_at` = ahora y el fijo de hace 31 s, da `STALE`. En `:761`, con reenvíos cada 5 s, `STALE` a los 35 s, y en `:772` un fijo nuevo vuelve a `OK`. Frontera de 30 s en `:689` (OK a 30 s y `STALE` a 31 s). Mutantes detectados: `stale-by-seen` y `waiting-by-seen`. |
| AC-12 | `integration/test_driver_api.py:758`; `unit/test_driver_sessions.py:811–828` | OK | Sin cambios. |
| AC-13 | `unit/test_reap_driver_sessions.py:69–242`, en especial `:86`; `integration/test_driver_api.py:701` y `:716`; `integration/test_main_driver.py:89` | OK | **v1.3.** `IDLE` se calcula con `last_seen_at` o, si no la hay, con `started_at`. En `:86`, un reenvío de hace 5 s con el último fijo de hace 20 min mantiene el turno. En `test_driver_api.py:701`, 12 min de reenvíos por HTTP, *reaper* y turno abierto. En `:716`, sin peticiones: abierto a los 9:59 y `IDLE` a los 10:00. Mutantes detectados: `idle-by-fix` e `idle-gt`. |
| AC-14 | `integration/test_cli_driver_codes.py:548–571` | OK | Solo cambia la construcción de `DriverSession`. |
| AC-15 | `integration/test_driver_api.py:796–887`; `unit/test_driver_login.py:271–285`; `unit/test_driver_sessions.py:255,835,844` | OK | T-09 no añade logs ni registra coordenadas. |

**Persistencia (T-09):** en `integration/test_driver_session_repository.py:46`, la tabla tiene `last_fix_at` y
`last_seen_at` en el orden del design §4. En `:79`, el viaje de ida y vuelta usa valores **distintos** en
los dos campos. Mutantes detectados: `sql-swap` y `sql-no-seen`.

**`driver_demand` (usa la sesión):** sus tests solo cambian `last_position_at` por `last_fix_at`
(`unit/test_build_driver_view.py:103,182,191`; `unit/test_demand_views.py:529,590`). Es el campo del que sale
`gps`, y las aserciones no cambian. La suite de `driver_demand` y su trazabilidad siguen en verde.
`DemandSessionListener._differs` (`adapters/outbound/drivers/demand_listener.py:63`) sigue siendo correcto,
porque solo se llama con un fijo nuevo. El paso a `STALE` en el WebSocket lo publica la tarea de 15 s de
`driver_demand.AC-09`, que no cambia.

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `CI=1 ./init.sh verify --e2e` (puerto 4173 libre) | **Salida 0, "verify: todo en verde"**. pytest: 1857 passed, 12 deselected, cobertura `domain`+`application` 99,65 %. Vitest: 563 passed, 2 skipped. Bundle: 5 passed. Playwright + axe: 126 passed. ruff format/check, mypy (148 ficheros), lint-imports, build, `feature_list.json` y trazabilidad: OK |
| `cd backend && uv run pytest -m slow` | **12 passed**, 1857 deselected. El aviso "coverage 70,34 % < 80 %" se debe a que el umbral global se aplica a este subconjunto, igual que en la v1.2. No falla ningún test. |
| `avisabus openapi export` a un fichero temporal, comparado con `frontend/src/shared/api/openapi.json` | Iguales en JSON (difieren solo en el formato de `prettier`). T-07 no tiene cambios que *commitear*. |

**Mutaciones** (en una copia del backend en el scratchpad, con los tests de `driver_sessions`,
`reap_driver_sessions`, `driver_api`, `driver_session_repository`, `demand_views`, `build_driver_view` y
`main_driver`; línea base: 256 passed): **12 mutantes, 12 detectados**. Son `resend-no-save`, `resend-lt`
(`<` en lugar de `<=`), `resend-renews-fix`, `resend-notifies`, `new-no-seen`, `fix-recorded` (`last_fix_at`
con la hora de la tablet), `stale-by-seen`, `waiting-by-seen`, `idle-by-fix`, `idle-gt`, `sql-swap` y
`sql-no-seen`.

**Escenario pedido**, reproducido por HTTP en la copia con un test temporal que no forma parte de la suite.
Tras un fijo, la tablet reenvía la misma posición cada 5 s durante 20 min, con `reap.tick()` cada 60 s:
- `gps = OK` a los 30 s y `STALE` desde los 35 s hasta el final.
- El turno no se cierra en ningún *tick*.

Después la tablet deja de enviar, con `tick()` cada 60 s:
- El turno sigue abierto en los *ticks* de los minutos 1 a 9.
- Se cierra en el del minuto 10, con motivo `IDLE` y `401` en la petición siguiente.

## Hallazgos

### Bloqueantes

Ninguno.

### Decisiones locales de la v1.3 (pedidas)

| Decisión | Valoración |
|---|---|
| Una posición **más antigua** renueva `last_seen_at` (`application/driver_sessions.py:478-480`) | **Cabe y es lo que pide la spec.** AC-08 dice que "toda petición válida cuenta como señal de vida", y AC-13 que vale "cualquier `PUT …/position` válido". Una posición antigua responde `204` y es válida. No es un fijo: no toca `last_fix_at`, la posición ni el progreso. Lo fija `unit/test_driver_sessions.py:291`, que compara la sesión entera. |
| Un reenvío con **coordenadas distintas** no sobrescribe la posición (`:478`, `<=`) | **Cabe.** AC-08 define el reenvío por el `recorded_at` ("un reenvío con el mismo `recorded_at` solo renueva la señal de vida") y solo es fijo una posición con `recorded_at` posterior. Aceptar las coordenadas sin renovar `last_fix_at` dejaría una posición nueva sin proyectar, en contra de "solo una posición nueva … se proyecta". La comparación se hace en UTC (`:474`), así que otro huso con el mismo instante también es un reenvío (`unit/test_driver_sessions.py:314`). |
| Los reenvíos **no llaman a `position_updated`** (`:479-480`) | **Cabe.** Ni AC-08 ni el design §3 dicen cuándo se avisa. Sin posición ni progreso nuevos, la vista solo cambia en `gps`, y el paso a `STALE` lo publica la tarea de 15 s de `driver_demand.AC-09`. Avisar haría que `_differs` (`last.gps is not OK`) publicara una vista cada 5 s con el GPS perdido. |
| `422` no es señal de vida | Cabe: AC-08 y AC-13 hablan de petición "válida" (`unit/test_driver_sessions.py:340`). |
| Sin migración | Cabe: lo dice T-09. `data/avisabus.sqlite` no tiene la tabla `driver_session` (comprobado con `sqlite3`). Una BD con la tabla de la v1.2 fallaría al escribir hasta que se borre la tabla, y los datos son efímeros. |

### Tests cambiados o sustituidos

| Test | Valoración |
|---|---|
| `test_a_position_with_the_same_time_is_accepted` → `test_a_resend_with_the_same_time_only_renews_the_sign_of_life` (`unit/test_driver_sessions.py:302`) | La v1.3 lo **exige**, porque invierte el comportamiento. El test nuevo compara la sesión entera con `replace(before, last_seen_at=…)` y comprueba que no se avisa. |
| `test_an_older_position_is_discarded` → `…_but_is_a_sign_of_life` (`:291`) | La v1.3 lo exige. Se mantiene la igualdad de la sesión entera, salvo `last_seen_at`. No se debilita. |
| `test_the_route_of_a_trip_is_cached` y `test_the_cache_is_dropped_with_a_new_feed_version` (`:645`, `:655`) | Era necesario: con el mismo `recorded_at`, la segunda posición sería un reenvío y no cargaría la ruta. `:645` gana una aserción sobre el progreso. |
| `unit/test_reap_driver_sessions.py:62-66` (`_session` con `last_seen_ago`) | Es la v1.3: el *reaper* mide desde `last_seen_at`. Las demás aserciones no cambian. |
| `integration/test_driver_session_repository.py:79-91` | Reforzado: los dos campos tienen valores distintos. |
| Tests de `driver_demand` y `tests/support/drivers.py` | Renombrado obligado (si no, `TypeError` al construir `DriverSession`), sin cambios en las aserciones. |
| `integration/test_driver_api.py:95-103` (fixture `use_cases`) | Solo refactoriza la fixture para llegar a `reap` en los tests nuevos. `client` se comporta igual. |

### No bloqueantes

Abiertos de ciclos anteriores, sin cambios en esta revisión:
- **N-01 · AC-04.** Un JSON mal formado sin token sigue respondiendo `422` en lugar de `401`.
- **N-03 · despliegue (AC-02).** El limitador usa `request.client.host`. Hay que tenerlo en cuenta en `deployment_rpi`.
- **N-04 · redacción de la spec.** `specs/driver_session/tasks.md:42` sigue citando `http/app.py`, y
  `design.md` §2 no lista `InvalidPositionError` ni `AuthenticateDriverSession`.
- **N-05 · AC-09.** Limitación de la regla con otras semillas. La v1.3 no la cambia: los reenvíos ya no se
  proyectan, así que si acaso reduce el ruido que llega a `project_progress`.
- **N-06 · redacción de la spec · `specs/driver_session/design.md:97`.** Sigue el paréntesis "(la que fijó
  el progreso)".
- **N-07 · `backend/tests/integration/test_upcoming_stops_real_shapes.py`.** El informe sale por nivel de
  ruido, no por trazado.
- **N-08 · redacción de la spec · `specs/driver_session/design.md:52-63`.** `progress_recorded_at` sigue
  sin aparecer en el modelo de §3 ni en la tabla de §4.

Cerrados: N-02 (ciclo 2 de la v1.2). N-09 (commit `wip` `f34e3de`) queda fuera de este diff, porque ya se
fusionó con la PR #53.

Nuevos:
- **N-10 · documentación · `docs/architecture.md:119`.** El diagrama de clases sigue mostrando
  `DriverSession { …; last_position_at }`, sin `last_fix_at` ni `last_seen_at`. `docs/` es de la persona:
  propongo actualizarlo, a la vez que N-08, en la próxima revisión de la documentación.
- **N-11 · redacción de la spec · `specs/driver_session/design.md:61`.** El modelo de §3 sigue declarando
  `last_position_at` con el comentario "renombrado a `last_fix_at`". El código usa `last_fix_at`, como
  piden el comentario y §4, y no hay ambigüedad real. Conviene escribir el nombre nuevo en la próxima
  versión.

### Alcance

- **Código:** solo los cuatro módulos de T-09 (`domain/models/driver.py`, `application/driver_sessions.py`,
  `application/reap_driver_sessions.py` y `persistence/sqlite_driver_sessions.py`).
- **Tests:** los que lista T-09 más `test_driver_session_repository.py`, `test_cli_driver_codes.py`,
  `tests/support/drivers.py` y dos tests de `driver_demand`. Todos son el renombrado obligado del campo.
- **Sin cambios:** frontend, contrato OpenAPI, `.env.example` (no hay configuración nueva), textos de
  interfaz y `docs/`.
- **Progreso y commits:** `feature_list.json` y `progress/*` son cambios del orquestador y del implementer
  dentro de su rol. Los commits siguen Conventional Commits con el ámbito de la feature.
- No se ha tocado `qr/` ni `.env`.
