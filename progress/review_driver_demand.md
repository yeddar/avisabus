# Revisión: driver_demand
Ciclo: 1 · Fecha: 2026-11-10 · Agente: reviewer

## Veredicto: CHANGES_REQUESTED

Un único hallazgo bloqueante (B-01): AC-08 hereda el protocolo y los límites de `realtime_events`, y dos de esos comportamientos no tienen ningún test en `/ws/driver`. El código hace lo correcto; lo que falta es la evidencia. No hay defectos funcionales ni de privacidad.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `test_driver_demand.py:352,391`; `test_deliver_alerts.py:186,208,218,249,256` | OK | E2E por `POST /alerts`: `DELIVERED`, `alert.delivered` al pasajero y vista nueva con paradas y necesidades. |
| AC-02 | `test_driver_demand.py:401,423`; `test_deliver_alerts.py:67-131`; `test_demand_views.py:610`; `test_alert_repository.py:278,297` | OK | Cubre entrega al elegir, cambio de salida con `alert.registered` y aviso actualizado, misma salida y otro día de servicio. |
| AC-03 | `test_driver_demand.py:449,473,486`; `test_deliver_alerts.py:139`; `test_demand_views.py:273,622` | OK | Integración con `ENDED` y `REPLACED`; unit parametrizado con los cuatro motivos. `IDLE` y `REVOKED` pasan por el mismo `CloseDriverSession`. Orden `session.closed` → `1000` comprobado. |
| AC-04 | `test_demand_views.py:637`; `test_driver_demand.py:496,512` | OK | Cancelación y caducidad reales. |
| AC-05 | `test_build_driver_view.py:111-189`; `test_demand.py:20-64`; `test_demand_views.py:402`; `test_driver_demand.py:377`; `test_alert_repository.py:266` | OK | Incluye aparición del viaje (`stop_sequence`), máximo 5 paradas, total solo de las mostradas y ausencia de datos del dispositivo. |
| AC-06 | `test_demand.py:68,94`; `test_build_driver_view.py:199,212,223` | OK | Tabla de casos con límites (`=` no alerta) y sin dato. |
| AC-07 | `test_build_driver_view.py:241`; `test_demand_views.py:459`; `test_driver_demand.py:221` | OK | `test_build_driver_view.py:253` cita AC-07 para un caso que AC-07 no describe (N-02). |
| AC-08 | `test_driver_demand.py:209-349`; `test_main_driver.py:110` | **Parcial** | Verificados: `4408`, `4401`, `4400`, vista actual, vistas nuevas, `ping` de 25 s, aislamiento entre turnos, `1013`. **Sin test: `4429` y `1001` (B-01).** |
| AC-09 | `test_demand_views.py:140-378,545-601,649`; `test_driver_demand.py:531`; `test_main_driver.py:118` | OK | Agrupación con `FakeClock` y contador, refresco de 15 s y arranque y parada de la tarea. |
| AC-10 | `test_driver_demand.py:548,567`; `test_main_driver.py:111` | OK | Compara la respuesta con el mensaje del socket campo a campo. |
| AC-11 | `test_driver_demand.py:573` | OK | Válido dentro de lo que permite la regla de no usar reloj real (N-04). |
| AC-12 | `test_deliver_alerts.py:156,197`; `test_demand_views.py:307`; `test_driver_demand.py:594,620,635` | OK | Campos exactos con logger falso y logs capturados. Tres tests más citan AC-12 por la IP (N-01). |

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `CI=1 ./init.sh verify --e2e` | Salida 0, "verify: todo en verde". Ruff, mypy (148 ficheros), lint-imports (2 contratos), pytest 1844 passed / 12 deselected con cobertura 99,65 %, vitest 563 passed / 2 skipped, build y presupuesto JS 5 passed, Playwright + axe 126 passed, trazabilidad OK. |
| `cd backend && uv run pytest -m slow` | 12 passed. Imprime `FAIL Required test coverage of 80%` (70,34 %) porque el umbral se aplica a un subconjunto de 12 tests; no es un fallo de la feature, la suite completa da 99,65 %. |
| Cobertura de adaptadores en `test_driver_demand.py` + `test_main_driver.py` | `ws/driver.py` 95 %, sin cubrir 138, 143, 175, 195-196, 206. |
| Mutaciones propias, en copia fuera del repositorio | 16 aplicadas, 12 detectadas. Sobreviven: `4429`→`1000` y `1001`→`1000` (B-01), suscribirse tras enviar la vista (N-03) y quitar la comparación de `finished` (equivalente en la práctica: `finished` cambia junto con las próximas paradas). |
| Sonda con `uvicorn` real en local (`avisabus.main:app`) | Login, `GET …/view`, `/ws/driver?session_token=LEAKME`, token inválido (`4401`) y cierre del turno (`session.closed` y `1000`). En los logs no aparece el token, el código, `LEAKME` ni la IP del cliente; la única coincidencia de `127.0.0.1:` es la línea de arranque "Uvicorn running on". |
| Pruebas de `4429` y `1001` en la copia | `4429`: pasa. `1001`: las dos conexiones registraron `ws.closed code=1001`; la prueba no terminó limpia por el desmontaje de mi propio arnés, no por la aplicación. |

Sin frontend de interfaz en esta feature: i18n y accesibilidad no aplican (solo `openapi.json` y `schema.d.ts` generados). Sin variables de entorno nuevas. Sin `datetime.now()`, `time.time()` ni esperas reales en el diff; el único `asyncio.sleep` es `sleep(0)` en `settle()`.

## Hallazgos

### Bloqueantes

**B-01 · AC-08 · `backend/src/avisabus/adapters/inbound/ws/driver.py:196`, `:143` y `:206` · `backend/tests/integration/test_driver_demand.py` (falta)**
AC-08 exige "mismo protocolo y límites que `realtime_events`", y en esa spec el desbordamiento (`4429`, AC-09) y el cierre al detener la aplicación (`1001`, AC-11) se verifican por integración. En `/ws/driver` ningún test los ejercita: cambiar cualquiera de los dos códigos por `1000` deja la suite en verde. Los tests de `/ws/passenger` no los protegen, porque `_write` y `_first_message` de `ws/driver.py` son copias y no código compartido.
Qué hacer: añadir a `test_driver_demand.py`, con la cita `driver_demand.AC-08`, un test de `4429` (`AVISABUS_EVENT_QUEUE_SIZE` bajo y varios eventos al canal `driver:<session_id>`) y otro de `1001` (socket conectado y socket esperando el `hello`, parada por el `lifespan`). Sirven de modelo `test_ws_passenger.py:307` y `:389`. No hace falta tocar código de producción.

### No bloqueantes

- **N-01 · Trazabilidad · `test_driver_demand.py:665,674,682` y `http/access_log.py:9`:** citan `driver_demand.AC-12` para la IP en logs, pero AC-12 trata de los logs de entrega. La regla aplicable es `driver_session.AC-15` ("ningún log debe incluir… la IP").
- **N-02 · Problema de spec menor (no requiere parar) · `application/build_driver_view.py:77-91`, `test_build_driver_view.py:253`:** si la salida desaparece de la red activa, la vista da `service = null`. Ninguna spec lo contempla; AC-07 habla de un turno sin salida elegida, y aquí sí la hay. Es una salida razonable y está anotada, pero las solicitudes entregadas a ese turno dejan de verse. Conviene fijarlo en la spec y que el test no cite AC-07.
- **N-03 · AC-08 · `ws/driver.py:111`:** ningún test comprueba que la suscripción ocurre antes de construir la vista inicial. El orden del código es el correcto, pero una regresión abriría una ventana de vistas perdidas sin que falle nada.
- **N-04 · AC-11 · `test_driver_demand.py:584,590`:** con `FakeClock` la resta `generated_at - created_at` es siempre 0, así que esa aserción no puede fallar. El test sí tiene valor por `receive_json_soon` y `FakeSleep`: con un intervalo mínimo de 10 s falla por sí solo. El caso peor (vista agrupada, ≤ 1 s) solo lo cubren los unit; la medida real corresponde a `nfr_validation`.
- **N-05 · Ambigüedad entre AC-09 y design §3 · `adapters/outbound/drivers/demand_listener.py:49-69`:** `distance_m` cambia con cada posición y no dispara `touch`; se actualiza con el refresco de 15 s (`demand_views.py:171-173`). Es coherente con design §3, pero AC-09 dice "próximas paradas" sin precisar. Conviene aclararlo.
- **N-06 · AC-04, carrera acotada, código de `alert_expiry` · `application/watch_passages.py:73,84` y `application/expire_alert.py:47`:** `WatchPassages` lee los avisos antes de esperar al SAE. Si uno pasa de `PENDING_DRIVER` a `DELIVERED` en esa espera y caduca, no se llama a `alert_removed`. La vista se corrige sola en ≤ 15 s con el refresco. Ninguna tarea autoriza tocar ese módulo; lo dejo anotado.
- **N-07 · Mantenibilidad · `ws/driver.py:28-43` y `:121-208`:** importa nombres privados de `ws/passenger.py` y duplica `_first_message`, `_forward` y `_write`. Esta duplicación es la causa de B-01. Propuesta para una tarea futura: un `ws/protocol.py` común.
- **N-08 · Fuera de esta feature:** la IP sigue escrita en `uvicorn.error` para `/ws/passenger` (código de `realtime_events`). Lo anotó el implementer y corresponde decidirlo a la persona.

### Desviaciones respecto al design

Ninguna contradice la spec ni inventa un contrato público. Conviene reflejarlas en `design.md` §2-§3 en la próxima revisión de la spec.

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

Sin cambios fuera del alcance. `qr/` y `.env` no se han tocado.

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
| Contrato | OK, salvo la evidencia de B-01. |
| Arquitectura | OK: lint-imports en verde, dominio sin I/O, sin reloj real. |
| Tests | OK, salvo B-01. Sin red ni esperas reales. |
| Privacidad y seguridad | OK. `ws.*` sin `session_id`; `alert.delivered` y `alert.undelivered` solo con los campos del design; la vista no se registra; excepciones solo por tipo; sin IP, token ni query string en los logs de `uvicorn` para `/ws/driver` y `GET …/view`. |
| Frontend | No aplica. |
| Convenciones | OK: glosario y Conventional Commits con ámbito. |
