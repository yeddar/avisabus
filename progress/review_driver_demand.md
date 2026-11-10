# Revisión: driver_demand
Ciclo: 2 · Fecha: 2026-11-10 · Agente: reviewer

## Veredicto: APPROVED

B-01 está resuelto: `/ws/driver` tiene tests de los cierres `4429` y `1001` que fallan si cambia el código de cierre, comprobado con mutaciones propias en una copia fuera del repositorio. Los 12 AC tienen evidencia válida y la verificación completa está en verde. Quedan abiertos los no bloqueantes N-01 a N-08, ninguno afecta al comportamiento exigido.

## Matriz AC → evidencia

Rutas relativas a `backend/tests/`. Entre ciclos solo han cambiado `integration/test_driver_demand.py` (53 líneas añadidas) y ficheros de progreso; las líneas de ese test se han actualizado.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `integration/test_driver_demand.py:405,444`; `unit/test_deliver_alerts.py:186,208,218,249,256` | OK | E2E por `POST /alerts`: `DELIVERED`, `alert.delivered` al pasajero y vista nueva. Mutación (sin `touch` al crear) detectada. |
| AC-02 | `integration/test_driver_demand.py:454,476`; `unit/test_deliver_alerts.py:67-131`; `unit/test_demand_views.py:610`; `integration/test_alert_repository.py:278,297` | OK | Tres mutaciones detectadas: sin devolver al cambiar de salida, sin entregar pendientes y devolver con la misma salida. |
| AC-03 | `integration/test_driver_demand.py:502,526,539`; `unit/test_deliver_alerts.py:139`; `unit/test_demand_views.py:273,622` | OK | Sin devolver al cerrar, sin `session.closed` y `1000`→`1001` detectadas. |
| AC-04 | `unit/test_demand_views.py:637`; `integration/test_driver_demand.py:549,565` | OK | Notificador sin `touch` detectado por unit e integración. |
| AC-05 | `unit/test_build_driver_view.py:111-189`; `unit/test_demand.py:20-64`; `unit/test_demand_views.py:402`; `integration/test_driver_demand.py:430`; `integration/test_alert_repository.py:266` | OK | Sin comparar `stop_sequence`, `total_waiting = 0` y `VISUAL` contando `SEAT` detectadas. |
| AC-06 | `unit/test_demand.py:68,94`; `unit/test_build_driver_view.py:199,212,223` | OK | Límites `>`→`>=` de plazas y asientos, y alerta sin dato, detectados. |
| AC-07 | `unit/test_build_driver_view.py:241`; `unit/test_demand_views.py:459`; `integration/test_driver_demand.py:223` | OK | Alerta o plazas con `service = null` detectadas. `unit/test_build_driver_view.py:253` cita AC-07 para otro caso (N-02). |
| AC-08 | `integration/test_driver_demand.py:211-402`; `integration/test_main_driver.py:110` | OK | **B-01 cerrado.** `4429` en `:354` y `1001` en `:378`, este con un socket conectado y otro esperando el `hello`. Además: `4408`, `4401`, `4400`, vista actual, vistas nuevas, `ping` de 25 s, aislamiento entre turnos y `1013`. Sin test del orden suscripción → vista (N-03). |
| AC-09 | `unit/test_demand_views.py:140-378,545-601,649`; `integration/test_driver_demand.py:584`; `integration/test_main_driver.py:118` | OK | Sin agrupación, refresco de turnos sin suscriptores, `touch` en toda posición, ignorar `off_route` o `gps` y refresco de 30 s, detectados. |
| AC-10 | `integration/test_driver_demand.py:601,620`; `integration/test_main_driver.py:111` | OK | Compara la respuesta con el mensaje del socket; `free_seats` alterado detectado. |
| AC-11 | `integration/test_driver_demand.py:626` | OK | Válido dentro de lo que permite la regla de no usar reloj real (N-04). Intervalo mínimo de 10 s detectado. |
| AC-12 | `unit/test_deliver_alerts.py:156,197`; `unit/test_demand_views.py:307`; `integration/test_driver_demand.py:647,673,688` | OK | Log sin `session_id` y log con `needs` detectados. Tres tests más citan AC-12 por la IP (N-01). |

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `CI=1 ./init.sh verify --e2e` (puerto 4173 libre) | Salida 0, "verify: todo en verde". Ruff, mypy (148 ficheros), lint-imports, pytest 1846 passed / 12 deselected con cobertura 99,65 %, vitest 563 passed / 2 skipped, build y presupuesto JS 5 passed, Playwright + axe 126 passed, `feature_list.json` y trazabilidad OK. |
| `git diff e0b4d91 HEAD --stat` y `git diff 2340148 HEAD -- backend/src` | Desde el ciclo 1 solo cambian `test_driver_demand.py` y progreso. Sin cambios en el código de producción. |
| Mutaciones de B-01, en copia fuera del repositorio (`git archive HEAD`) | 7 de 7 detectadas, ver tabla. |
| Mutaciones de los demás AC, en la misma copia | 30 aplicadas: 28 detectadas, 1 superviviente (N-03) y 1 equivalente que descarto (la salida inventada también da `service = null`). |
| Repetición de los dos tests nuevos (`-k "4429 or 1001"`) | 30 de 30 ejecuciones en verde. |

La copia usa el intérprete de `backend/.venv` con `PYTHONPATH` a su propio `src` (comprobado con `avisabus.__file__`), sin instalar nada ni usar la red. Al terminar, el `src` de la copia coincide con el del repositorio y `git status` solo muestra `qr/`.

| Mutación de B-01 (`adapters/inbound/ws/driver.py`) | Test en rojo | Fallo |
|---|---|---|
| `:196`, `4429`→`1000` | `test_closes_with_4429_when_the_subscription_overflows` | `assert 1000 == 4429` |
| `:196`, `4429`→`1001` | ídem | `assert 1001 == 4429` |
| `:196`, `4429`→`1011` | ídem | `assert 1011 == 4429` |
| `:143`, `1001`→`1000` (esperando el `hello`) | `test_closes_open_sockets_with_1001_when_the_application_stops` | `assert 1000 == 1001` |
| `:143`, `1001`→`4408` (esperando el `hello`) | ídem | `assert 4408 == 1001` |
| `:206`, `1001`→`1000` (socket conectado) | ídem | `assert 1000 == 1001` |
| `:206`, `1001`→`4429` (socket conectado) | ídem | `assert 4429 == 1001` |

No se repiten en este ciclo la sonda con `uvicorn` real ni `pytest -m slow`: el código de producción no ha cambiado desde el ciclo 1.

Sin frontend de interfaz en esta feature: i18n y accesibilidad no aplican (solo `openapi.json` y `schema.d.ts` generados). Sin variables de entorno nuevas. Los tests nuevos no usan reloj real ni esperas reales, y sus sockets se esperan con el límite en vueltas del bucle de `tests/support/ws.py`.

## Hallazgos

### Bloqueantes

Ninguno.

**B-01 (ciclo 1) · Resuelto.** `backend/tests/integration/test_driver_demand.py:354` y `:378`, ambos con la cita `driver_demand.AC-08`, ejercitan el desbordamiento real de la cola (`AVISABUS_EVENT_QUEUE_SIZE=2` y tres eventos al canal del turno) y la parada real del `lifespan` con los dos sockets abiertos. También comprueban que se liberan la conexión y la suscripción. Las tres rutas de cierre (`ws/driver.py:196`, `:143` y `:206`) fallan con cualquier código distinto.

### No bloqueantes

Siguen abiertos y con la misma numeración; el código al que se refieren no ha cambiado.

- **N-01 · Trazabilidad · `integration/test_driver_demand.py:718,727,735` y `http/access_log.py:9`:** citan `driver_demand.AC-12` para la IP en logs, pero AC-12 trata de los logs de entrega. La regla aplicable es `driver_session.AC-15` ("ningún log debe incluir… la IP").
- **N-02 · Problema de spec menor (no requiere parar) · `application/build_driver_view.py:77-91`, `unit/test_build_driver_view.py:253`:** si la salida desaparece de la red activa, la vista da `service = null`. Ninguna spec lo contempla; AC-07 habla de un turno sin salida elegida, y aquí sí la hay. Es una salida razonable y está anotada, pero las solicitudes entregadas a ese turno dejan de verse. Conviene fijarlo en la spec y que el test no cite AC-07.
- **N-03 · AC-08 · `ws/driver.py:111`:** ningún test comprueba que la suscripción ocurre antes de construir la vista inicial. La mutación que suscribe después de enviar la vista sigue sobreviviendo en este ciclo. El orden del código es el correcto, pero una regresión abriría una ventana de vistas perdidas sin que falle nada.
- **N-04 · AC-11 · `integration/test_driver_demand.py:637,643`:** con `FakeClock` la resta `generated_at - created_at` es siempre 0, así que esa aserción no puede fallar. El test sí tiene valor por `receive_json_soon` y `FakeSleep`: con un intervalo mínimo de 10 s falla por sí solo. El caso peor (vista agrupada, ≤ 1 s) solo lo cubren los unit; la medida real corresponde a `nfr_validation`.
- **N-05 · Ambigüedad entre AC-09 y design §3 · `adapters/outbound/drivers/demand_listener.py:49-69`:** `distance_m` cambia con cada posición y no dispara `touch`; se actualiza con el refresco de 15 s (`demand_views.py:171-173`). Es coherente con design §3, pero AC-09 dice "próximas paradas" sin precisar. Conviene aclararlo.
- **N-06 · AC-04, carrera acotada, código de `alert_expiry` · `application/watch_passages.py:73,84` y `application/expire_alert.py:47`:** `WatchPassages` lee los avisos antes de esperar al SAE. Si uno pasa de `PENDING_DRIVER` a `DELIVERED` en esa espera y caduca, no se llama a `alert_removed`. La vista se corrige sola en ≤ 15 s con el refresco. Ninguna tarea autoriza tocar ese módulo; lo dejo anotado.
- **N-07 · Mantenibilidad · `ws/driver.py:28-43` y `:121-208`:** importa nombres privados de `ws/passenger.py` y duplica `_first_message`, `_forward` y `_write`. Propuesta para una tarea futura: un `ws/protocol.py` común.
- **N-08 · Fuera de esta feature:** la IP sigue escrita en `uvicorn.error` para `/ws/passenger` (código de `realtime_events`). Lo anotó el implementer y corresponde decidirlo a la persona.

### Desviaciones respecto al design

Sin cambios desde el ciclo 1: el código de producción es el mismo. Ninguna contradice la spec ni inventa un contrato público. Conviene reflejarlas en `design.md` §2-§3 en la próxima revisión de la spec.

| Desviación | Juicio |
|---|---|
| `DeliveryObservingAlerts` (`deliver_alerts.py:91`) | Aceptable. El design no dice quién llama a `touch` tras crear el aviso y ninguna tarea autoriza cambiar `create_alert.py`. Solo actúa si el aviso se guardó de verdad (`:108`). |
| `UndeliverSessionAlerts.__call__(session_id, reason=…)` | Necesaria: design §4 exige `reason` en el log. Compatible con la firma del design por tener valor por defecto. |
| `DemandViews(…, *, logger, sleep)`, `last_view`, `forget`, `aclose` | Aceptable. Internas y necesarias para el log de fallos, el test sin reloj real y no publicar tras cerrar. `logger` es obligatorio, así que la firma del design literal no compila; es un ajuste menor. |
| `BuildDriverView.for_session_id`, `open_session_ids` | Aceptable: `refresh_all` las necesita y el puerto no busca por id. |
| `driver_channel` en `application/demand_views.py` | Aceptable. `device_channel` está en `domain/ports/events.py`; moverlo sería más coherente, pero exigía tocar otro módulo. |
| Comparación de `gps` en `position_updated` | Correcta: AC-09 enumera `gps`, aunque design §3 no lo cite. Manda el AC. |
| `GET …/view` sin `type` | Correcta: `type` es la envoltura del mensaje WebSocket; el test compara el resto campo a campo. |
| `4400` para `hello` malformado | Correcta: design §3, "los de `realtime_events` más `4401`". |
| `NoDriverDirectory`, `NoopDriverViewNotifier` y `NoopDriverSessionListener` siguen como valor por defecto (`http/container.py:306,318,359,407`) | Aceptable: `main.py` usa los reales y `test_main_alerts.py`, `test_alert_expiry.py`, `test_alerts_cancel_api.py` y `test_main_driver.py` lo comprueban. |

### Alcance: cambios en código de otras features

Diff respecto a `origin/feat/driver_session`. Sin cambios fuera del alcance. El ciclo 2 solo añade tests a `test_driver_demand.py` y actualiza ficheros de progreso y `feature_list.json`. `qr/` y `.env` no se han tocado.

| Fichero | Autorización | Juicio |
|---|---|---|
| `persistence/sqlite_alerts.py` | T-02 y design §2 | Dentro. |
| `domain/ports/alerts.py`, `tests/support/alerts.py` | Implícita en T-02: el `Protocol` y su doble deben ampliarse | Dentro. |
| `background/driver_tasks.py` | T-03 | Dentro. |
| `http/routes/driver.py`, `http/container.py`, `http/app.py` | T-04 | Dentro. |
| `main.py` | No listado en T-04, pero es la raíz de composición que T-04 ordena sustituir | Dentro por necesidad. |
| `http/access_log.py` | No listado en ninguna tarea | Justificado: sin el filtro, `/ws/driver` incumpliría `driver_session.AC-15`. El cambio es mínimo y aditivo. Debería constar en `tasks.md`. |
| `test_main_alerts.py`, `test_alert_expiry.py`, `test_alerts_cancel_api.py`, `test_main_driver.py` | T-04 (afirmaban los componentes vacíos) | Dentro: cambian solo el valor esperado. `test_main_driver.py` añade además sondas de vista, socket y refresco. |
| `tests/integration/test_alert_repository.py` | T-02 | Dentro: solo añade tests. |
| `feature_list.json`, `progress/current.md`, `progress/history.md` | Orquestador | Dentro. |

### Lista de comprobación (`docs/verification.md` §4)

| Bloque | Resultado |
|---|---|
| Contrato | OK. Los cierres de `realtime_events` en `/ws/driver` ya tienen evidencia. |
| Arquitectura | OK: lint-imports en verde, dominio sin I/O, sin reloj real. |
| Tests | OK. Sin red ni esperas reales; los tests de B-01 no son tautológicos (mutaciones detectadas) y son estables (30 de 30). |
| Privacidad y seguridad | OK. `ws.*` sin `session_id`; `alert.delivered` y `alert.undelivered` solo con los campos del design; la vista no se registra; excepciones solo por tipo. La comprobación con `uvicorn` real es del ciclo 1 y el código no ha cambiado. |
| Frontend | No aplica. |
| Convenciones | OK: glosario y Conventional Commits con ámbito. |
