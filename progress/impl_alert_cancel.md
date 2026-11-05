# Implementación: alert_cancel
Spec: specs/alert_cancel/ (v1.0, APPROVED) · Ciclo de revisión: 0
Rama: `feat/alert_cancel` (apilada sobre `feat/alert_create` y `feat/realtime_events`).

## Tareas
- [x] T-01 `AlertNotFoundError` y `CancelAlert` (commit d51b25e)
- [x] T-02 Endpoint `DELETE /alerts/{alert_id}`, error 404 y composición (commit 7d7929f)
- [x] T-03 Contrato del frontend (`npm run gen:api`) y verificación completa (commit de este
      fichero: `frontend/src/shared/api/openapi.json` y `schema.d.ts` regenerados; solo
      añadidos: ruta `/api/v1/alerts/{alert_id}` con `delete`)

## Decisiones locales
- T-01: `AlertNotFoundError` no lleva atributos ni identificadores en el mensaje
  (`"alert not found"`), igual que `BusNotRequestableError`: el 404 no los necesita.
- T-01: la constante `ALERT_CANCELLED = "alert.cancelled"` (nombre del evento y del log) vive en
  `application/cancel_alert.py`, el fichero que fija la tarea, y no en `alert_events.py`.
- T-01: "ya caducó" (AC-02) se modela como aviso ausente: los avisos caducados se borran
  (`AlertRepository`: "every stored alert is active") y `CancelAlert` no recibe `Clock` en el
  design §3. La carrera con la caducidad (`delete` → `False`) también da `AlertNotFoundError`, sin
  evento, sin notificar al conductor y sin log.
- T-01: un `404` no se registra en el log (el design §4 solo lista `alert.cancelled`).
- T-02 (hallazgo H-1 de la revisión de `alert_create`): `handle_unexpected_error`
  (`adapters/inbound/http/errors.py`, fichero de la tarea) pone `Cache-Control: no-store` en el
  `500` genérico. Lo cubre AC-05 ("las respuestas DEBERÁN llevar `no-store`"): Starlette construye
  el `500` en `ServerErrorMiddleware`, fuera de `NoStoreMiddleware`, así que el middleware no
  puede añadirla. Se pone en **todos** los `500`, no solo bajo `/api/v1/alerts`: `errors.py` no
  conoce el prefijo de la API y una respuesta de error inesperado nunca debe guardarse en caché.
  Ningún test ni spec fija lo contrario (`project_scaffold.AC-11` solo fija el cuerpo). Test:
  `test_an_unexpected_error_is_not_stored_either`. Punto a validar en la revisión por si se
  prefiere acotarlo a `/alerts`.
- T-02: el `204` se devuelve con `response_class=Response` y sin cuerpo. `alert_id` es texto
  libre en la ruta (design §3); `DELETE /alerts/mine` también es un `404`.
- T-02: el OpenAPI del `DELETE` incluye, además de `204`, `400` y `404`, el `422` que FastAPI
  añade por sí solo a toda ruta con parámetros (no se puede dar en la práctica: `alert_id` es
  texto y la cabecera es opcional en el esquema).
- T-02: `CancelAlert` comparte el `SqliteAlertRepository` y el logger `avisabus.alerts` con
  `CreateAlert`, y recibe `NoopDriverViewNotifier` (bloque 3). `main.py` no cambia de lógica: la
  composición está en `build_alert_use_cases`; solo se actualiza su comentario.
- T-02: el evento por `/ws/passenger` se comprueba con dos pestañas del mismo dispositivo y una de
  otro; que el otro no lo recibe se comprueba porque su primer mensaje posterior es la
  cancelación de su propio aviso (el socket no responde a mensajes del cliente tras el `hello`).
- T-02: hasta T-03 falla `test_frontend_openapi_matches_the_backend`
  (passenger_stop_view.AC-02): el contrato del frontend se regenera en T-03.

## Bloqueos
Ninguno.

## Verificación
`CI=1 ./init.sh verify --e2e` (2026-11-04, puerto 4173 libre, tras T-03): **todo en verde**
(`verify: todo en verde`, exit 0).

| Paso | Resultado |
|---|---|
| backend: format / lint / types | OK (`ruff format --check`, `ruff check`, `mypy`: 116 ficheros sin errores) |
| backend: architecture | OK (`lint-imports`: 2 contratos respetados) |
| backend: tests | OK: 1232 passed, 6 deselected; cobertura `domain`+`application` 99,54 % |
| frontend: format / lint / types | OK |
| frontend: tests | OK: 44 ficheros, 413 passed, 2 skipped |
| frontend: build + bundle | OK (5 tests de presupuesto) |
| frontend: e2e + a11y | OK: 87 passed |
| harness: `feature_list.json` / trazabilidad AC→test | OK |

Tests nuevos: `backend/tests/unit/test_cancel_alert.py` (10) y
`backend/tests/integration/test_alerts_cancel_api.py` (13). Mutaciones comprobadas a mano:
quitar la comparación del `device_hash` en `CancelAlert` rompe 2 tests (unit e integration de
AC-02); quitar `no-store` del `500` rompe `test_an_unexpected_error_is_not_stored_either`.
