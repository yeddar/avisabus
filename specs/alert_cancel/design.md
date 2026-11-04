# Cancelar solicitud de parada — design

> Feature: `alert_cancel` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-22, RF-28 (pasajero), RNF-06, RNF-07 · Casos de uso: CU-04 · Depende de: alert_create

## 1. Resumen

```
DELETE /alerts/{id} ─▶ device_hash_from_header ─▶ CancelAlert
   get(id) ∧ device_hash coincide ─▶ delete ─▶ publish alert.cancelled ─▶ DriverViewNotifier
   en otro caso ─▶ AlertNotFoundError (404)
```

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `errors.py` | `AlertNotFoundError` |
| application | `cancel_alert.py` | `CancelAlert` |
| adapters/inbound | `http/routes/alerts.py` | `DELETE /alerts/{alert_id}` |
| adapters/inbound | `http/errors.py`, `http/container.py`, `main.py` | Error 404 y composición |

## 3. Interfaces

```python
# DriverViewNotifier y NoopDriverViewNotifier: de alert_create (domain/ports/alerts.py)

# application/cancel_alert.py
class CancelAlert:
    def __init__(self, alerts: AlertRepository, events: EventPublisher,
                 drivers: DriverViewNotifier, logger: Logger) -> None: ...
    async def execute(self, device_hash: str, alert_id: str) -> None: ...
    # alert = get(alert_id); si None o alert.device_hash != device_hash → AlertNotFoundError
    # (comparación con hmac.compare_digest); delete; si delete devuelve False (carrera con la
    # caducidad) → AlertNotFoundError; publish(device_channel(hash), Event("alert.cancelled",
    # {"alert_id": alert_id})); si delivered_to → drivers.alert_removed(delivered_to); log.
```

`DELETE /api/v1/alerts/{alert_id}` → `204` sin cuerpo; `alert_id` se acepta como texto (un valor
que no es UUID simplemente no existe → 404).

| Caso | status | type |
|---|---|---|
| Cabecera ausente o inválida | 400 | `…/invalid-device-id` |
| No existe / otro dispositivo / caducado | 404 | `…/alert-not-found` |

## 4. Errores y logs

| Evento | Campos |
|---|---|
| `alert.cancelled` | `alert_id`, `stop_id`, `line` |

## 5. Estrategia de test

| AC | Test |
|---|---|
| AC-01–AC-03, AC-05 | `tests/integration/test_alerts_cancel_api.py` (aviso creado con `POST` en el mismo test; evento por `/ws/passenger`) |
| AC-04, AC-05 | `tests/unit/test_cancel_alert.py` (fakes de repositorio, publicador, notificador y logger) |

## 6. Decisiones locales permitidas

Ninguna relevante.

## 7. Preguntas abiertas

Ninguna.
