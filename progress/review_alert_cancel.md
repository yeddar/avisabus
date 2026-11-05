# Revisión: alert_cancel
Ciclo: 1 · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/alert_cancel/` v1.0 (APPROVED) · Rama: `feat/alert_cancel`. Diff revisado: `origin/feat/alert_create...HEAD`, commits d51b25e, 7d7929f y b90f841, más los de progreso.

## Veredicto: APPROVED

No hay hallazgos bloqueantes. Los cinco AC tienen tests que verifican el comportamiento de verdad: 15 de 17 mutantes se detectan y los 2 que sobreviven son equivalentes. `CI=1 ./init.sh verify --e2e` está en verde.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | **Unit:** `test_cancelling_deletes_the_alert_with_its_needs` y `test_cancelling_publishes_alert_cancelled_on_the_device_channel`. **Integration:** `test_cancelling_deletes_the_alert_and_tells_the_device_sockets` y `test_a_cancelled_line_can_be_requested_again` | OK | La respuesta es `204` sin cuerpo. La fila se borra con sus `needs`, y el aviso del otro dispositivo queda intacto. `GET /alerts/mine` sale vacío. Las **dos** pestañas del dispositivo reciben `{"type":"alert.cancelled","alert_id":…}`. El socket del otro dispositivo no lo recibe, porque su primer mensaje es la cancelación de su propio aviso. Detecta M02, M09, M10 y M11. |
| AC-02 | **Unit:** `test_a_missing_or_foreign_alert_is_not_found_and_nothing_changes` (desconocido, no UUID, caducado y de otro dispositivo) y `test_an_alert_that_expires_while_cancelling_is_not_found`. **Integration:** `test_unknown_expired_or_foreign_alerts_are_the_same_404`, `test_an_alert_can_only_be_cancelled_once` y `test_main_wires_the_cancellation` | OK | Los 5 casos dan `404` con `problem+json` y `no-store`, y su cuerpo es **byte a byte el mismo** (`len({r.content}) == 1`). Las filas no cambian y no se publica nada en ninguno de los dos canales. En la carrera con la caducidad no hay evento, ni aviso al conductor, ni log. Detecta M01, M03, M08, M09 y M13. |
| AC-03 | **Integration:** `test_missing_or_invalid_device_id_is_a_400` (ausente, vacía, no UUID, mayúsculas y v1) | OK | Da `400 …/invalid-device-id` tanto para un aviso existente como para uno inexistente, así que la cabecera se valida antes de mirar el aviso y no se filtra si existe. La fila queda intacta. |
| AC-04 | **Unit:** `test_cancelling_a_delivered_alert_notifies_its_driver_view` y `test_cancelling_a_pending_alert_notifies_no_driver`. **Integration:** `test_main_wires_the_cancellation` (`NoopDriverViewNotifier` en `main.py`) | OK | Usa un notificador falso, que se llama con `delivered_to` y solo si lo hay (design §3). Detecta M04 y M05. |
| AC-05 | **Unit:** `test_cancellation_is_logged_without_device_hash_nor_needs`. **Integration:** `test_cancellation_is_logged_without_personal_data`, `test_an_unexpected_error_is_not_stored_either`, `test_openapi_describes_the_cancel_endpoint` y la cabecera `no-store` en los tests de AC-01, AC-02 y AC-03 | OK | El log es exactamente `alert.cancelled` con `alert_id`, `stop_id` y `line`. No incluye *hash*, `X-Device-Id`, necesidades ni `session_id`. Los dos 404 previos no dejan log. Llevan `no-store` las respuestas 204, 400, 404 y 500. El OpenAPI describe 204 sin `content` y los ejemplos de 400 y 404. Detecta M06, M07, M12, M14 y M15. |

## Verificación ejecutada

- **`CI=1 ./init.sh verify --e2e`**, con el puerto 4173 libre (`lsof` sin salida). Resultado: **`verify: todo en verde`**, exit 0.
  - backend: format, lint, mypy y `lint-imports` OK.
  - Tests del backend: **1232 passed**, 6 deselected. Cobertura de `domain`+`application`: **99,54 %**.
  - `project_scaffold.AC-11` (`test_health.py::test_unhandled_exception_becomes_problem_json_without_internals`) sigue en verde.
  - frontend: format, lint y types OK. Tests: 44 ficheros, **413 passed**, 2 skipped. Build y presupuesto: 5 passed.
  - e2e + axe: **87 passed**.
  - harness: `feature_list.json` y trazabilidad AC→test OK.
- **Mutaciones.** Se hicieron sobre una copia de `backend/` (`git archive HEAD`) en el scratchpad, sin caché de bytecode y con `--disable-socket`, ejecutando los dos ficheros de test de la feature. El repositorio no se ha tocado (`git status` limpio).
  - **Se detectan 15 de 17:**
    - M01: sin comparar `device_hash`.
    - M02: evento en otro canal.
    - M03: se ignora el `False` de `delete`.
    - M04: se notifica siempre al conductor.
    - M05: no se notifica nunca.
    - M06: el log lleva el *hash*.
    - M07: el 500 sin `no-store`.
    - M08: un aviso ajeno da 400.
    - M09: se borra antes de comprobar el dueño.
    - M10: 200 en vez de 204.
    - M11: el *payload* usa `id`.
    - M12: el log lleva las necesidades.
    - M13: otro `type` en el 404.
    - M14: sin log.
    - M15: el log usa otro nombre de evento.
  - **Sobreviven 2, ambas equivalentes:**
    - M16: publicar en `device_channel(alert.device_hash)`. Es el mismo valor tras la comparación.
    - M17: `!=` en lugar de `hmac.compare_digest`. Funcionalmente es idéntico. La diferencia es de tiempo constante, y un test sin reloj real no puede observarla. El código usa `compare_digest`, como pide el design (`application/cancel_alert.py:43`).
  - **Solo con el fichero de integración:**
    - M01, M06, M08, M09, M11 y M12 también se detectan ahí.
    - M03 sobrevive. Es lo esperado: la carrera solo se puede provocar con el repositorio falso del test unitario.
    - M02 **cuelga** el test (ver H-2).

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes

- **H-1 (`no-store` en todos los 500, AC-05; consulta del orquestador).** El cambio está en `backend/src/avisabus/adapters/inbound/http/errors.py:48-53`. **Cabe y no hace falta limitarlo a `/alerts`.**
  - AC-05 exige `no-store` en las respuestas de este endpoint. El 500 lo construye `ServerErrorMiddleware`, que está fuera de `NoStoreMiddleware`, así que el manejador genérico es el único sitio donde ponerlo. `errors.py` está en los ficheros de T-02.
  - Ninguna spec fija la cabecera `Cache-Control` de un 500 en otra ruta. `position_estimation` fija `public, max-age=86400` solo para el 200 de las formas, y `stop_arrivals_api.AC-16` pide `no-store`. Un error inesperado nunca debe cachearse.
  - Limitarlo a `/alerts` metería el prefijo de la API en `errors.py` y no aportaría nada.
  - `project_scaffold.AC-11` solo fija el estado, el `content-type` y el cuerpo, y su test sigue en verde.
  - Efecto lateral: cambia una cabecera en los 500 de las demás rutas. Es inocuo, pero conviene que una persona lo anote como comportamiento transversal la próxima vez que se toque `docs/architecture.md` o `project_scaffold`. No hace falta para cerrar.
- **H-2 (robustez del test, AC-01).** Si se rompe la publicación, `backend/tests/integration/test_alerts_cancel_api.py:159-160` **se bloquea indefinidamente** en vez de fallar.
  - `tab.receive_json()` espera sin límite, y el proyecto no tiene `pytest-timeout`.
  - Con M02, la ejecución del fichero de integración se quedó colgada hasta el *timeout* externo de 180 s, y el proceso de pytest siguió vivo hasta matarlo a mano.
  - La mutación sí la detecta el test unitario (`test_cancelling_publishes_alert_cancelled_on_the_device_channel`), y la guarda del 204 en la línea 153 cubre el caso más probable. Por eso no bloquea.
  - Se recomienda acotar la espera, por ejemplo leyendo de la suscripción con el patrón de `_queued_event` antes de leer el socket, o añadir `pytest-timeout` en una tarea transversal. El mismo patrón puede existir en tests de `realtime_events`.
- **H-3 (decisiones locales de `progress/impl_alert_cancel.md`, validadas).**
  - **Caducado = ausente.** Es coherente con `AlertRepository` ("every stored alert is active: expired and cancelled ones are deleted", `domain/ports/alerts.py:11`) y con el design §3, que no da `Clock` a `CancelAlert`. La carrera con la caducidad sigue el design al pie de la letra.
  - **Sin log en el 404.** El design §4 solo lista `alert.cancelled`. Además, no registrar intentos sobre `alert_id` ajenos evita asociar identificadores. Correcto.
  - **422 automático en el OpenAPI.** No se puede producir: `alert_id` es texto y la cabecera es opcional en el esquema. Es el mismo criterio que `GET /alerts/mine`, que también documenta `422`. Aceptable. Los contratos del design (400 y 404) están documentados con ejemplos.
  - **Método del test del WebSocket.** Para comprobar que el otro dispositivo no recibe el evento, se usa la cancelación de su propio aviso como "primer mensaje". Es válido: el socket ignora los mensajes del cliente tras el `hello` (`ws/passenger.py:6`), y si el evento ajeno llegara, el primer mensaje no coincidiría. La única pega es la de H-2.
- **H-4 (observación, sin acción).** Al declarar `DELETE /alerts/{alert_id}`, un `GET` o `POST` sobre `/alerts/<texto>` pasa de 404 a 405. No depende del `alert_id`, así que no filtra si el aviso existe, y lleva `no-store` por el *middleware*. `DELETE /alerts/mine` da el 404 `alert-not-found`, como recoge la decisión local.

### Lista de comprobación (docs/verification.md §4)

- **Contrato:**
  - Los AC se cumplen, incluidos los `SI … ENTONCES` de AC-02 y AC-03.
  - El endpoint, los códigos, los `type`, el evento y el log coinciden con el design §3 y §4.
  - `CancelAlert(alerts, events, drivers, logger)` y `execute(device_hash, alert_id)` coinciden con la interfaz.
- **Arquitectura:**
  - `AlertNotFoundError` está en `domain/errors.py`, sin identificadores en el mensaje.
  - `CancelAlert` solo depende de puertos.
  - La composición está en `container.py`; `main.py` solo cambia un comentario.
  - `lint-imports` OK. No hay `datetime.now()` ni `time.time()`.
- **Tests:**
  - Sin red: sockets desactivados, y el WebSocket va por `TestClient` en proceso.
  - `FakeClock`, sin *sleeps* reales: `asyncio.sleep(0)` es solo un turno del bucle.
  - Las fixtures son las existentes (`gtfs_mini`, `stop_508_peak`). Los tests no son tautológicos, como muestran las mutaciones.
- **Privacidad (AGENTS.md §6):**
  - No se registra `device_id`, `device_hash`, necesidades ni `session_id`, y está comprobado en unit y en integration.
  - El log del 500 sigue registrando solo el tipo y el método.
  - Se borra la fila con las necesidades (RNF-06).
  - La respuesta no revela si el aviso es de otro dispositivo: la cabecera se valida antes de buscar el aviso y el 404 es idéntico en todos los casos.
- **Frontend:** solo se han regenerado los artefactos del contrato (`openapi.json` y `schema.d.ts`, 168 líneas añadidas y 0 borradas), así que no hay interfaz. i18n y accesibilidad no aplican, y e2e + axe están en verde.
- **Convenciones:**
  - Los nombres siguen el glosario (`Alert`, `device_hash`).
  - Los commits son Conventional Commits con ámbito `alert_cancel` y citan la tarea.
  - No hay variables de configuración nuevas.
- **Alcance:**
  - El diff solo toca los ficheros de `tasks.md` (T-01 a T-03), más los ficheros de progreso y `feature_list.json` del orquestador.
  - No hay refactorizaciones ajenas.
  - El cambio en el 500 global está justificado en H-1.
- **Problemas de spec:** ninguno.
