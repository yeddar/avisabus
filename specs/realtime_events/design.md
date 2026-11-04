# Eventos en tiempo real — design

> Feature: `realtime_events` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-23, RF-28 (base), RNF-02, RNF-06, RNF-07, RNF-12, RNF-13 · Casos de uso: CU-03, CU-04, CU-07 (canal) · Depende de: project_scaffold

## 1. Resumen

```
casos de uso ──publish(channel, event)──▶ InMemoryEventPublisher ──cola acotada──▶ Subscription
                                                                                     │
navegador ──WS /ws/passenger── hello{device_id} ─▶ DeviceHasher ─▶ subscribe("device:<hash>")
                              ◀─ alerts.snapshot (PassengerSnapshotProvider) ◀───────┘
                              ◀─ eventos del canal · ping cada 25 s
```

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/events.py` | `Event` |
| domain | `models/device.py` | `parse_device_id(raw) -> DeviceId` (AC-04), `DeviceId` |
| domain | `ports/events.py` | `EventPublisher`, `Subscription` |
| domain | `ports/device.py` | `DeviceHasher` |
| domain | `errors.py` | `InvalidDeviceIdError` |
| adapters/outbound | `events/in_memory.py` | `InMemoryEventPublisher` |
| adapters/outbound | `security/hmac_device_hasher.py` | `HmacDeviceHasher` |
| adapters/inbound | `ws/passenger.py` | Endpoint `/ws/passenger` y `PassengerSnapshotProvider` |
| adapters/inbound | `ws/connections.py` | `ConnectionRegistry` (máximo, cierre al parar, `ws.stats`) |
| adapters/inbound | `http/errors.py` | Ampliación: `InvalidDeviceIdError` → 400 (lo usa `alert_create`) |
| adapters/inbound | `http/device.py` | Dependencia FastAPI `device_hash_from_header` (`X-Device-Id`) |
| raíz | `logging.py` | Filtro de excepciones (AC-12) |
| raíz | `main.py` | Composición, `ConnectionRegistry` en el `lifespan` |

## 3. Interfaces

```python
# domain/models/events.py
@dataclass(frozen=True, slots=True)
class Event:
    type: str                    # "alert.registered", "alert.expired"…
    payload: Mapping[str, object]   # JSON serializable; nunca device_id ni device_hash
    # Serialización: {"type": type, **payload}

# domain/models/device.py
@dataclass(frozen=True, slots=True)
class DeviceId:
    value: str                   # UUID v4 canónico; __repr__ y __str__ NO muestran el valor ("DeviceId(***)")
def parse_device_id(raw: str | None) -> DeviceId: ...   # lanza InvalidDeviceIdError
# regex: ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$

# domain/ports/device.py
class DeviceHasher(Protocol):
    def hash(self, device_id: DeviceId) -> str: ...   # 64 caracteres hex

# domain/ports/events.py
class Subscription(Protocol):
    @property
    def overflowed(self) -> bool: ...
    async def next_event(self) -> Event: ...          # espera; lanza SubscriptionOverflowError si desbordada
    def close(self) -> None: ...                      # idempotente; la elimina del publicador

class EventPublisher(Protocol):
    def publish(self, channel: str, event: Event) -> None: ...     # síncrona, no bloquea (AC-02)
    def subscribe(self, channel: str) -> Subscription: ...
    def subscriber_count(self, channel: str | None = None) -> int: ...

def device_channel(device_hash: str) -> str: return f"device:{device_hash}"
```

```python
# adapters/outbound/events/in_memory.py
class InMemoryEventPublisher:
    def __init__(self, queue_size: int = 100) -> None: ...
    # dict[channel, set[_Subscription]]; cada _Subscription con asyncio.Queue(maxsize=queue_size).
    # publish: put_nowait; QueueFull → overflowed = True, se vacía la cola y se despierta al lector
    # para que reciba SubscriptionOverflowError (AC-02, AC-09).

# adapters/outbound/security/hmac_device_hasher.py
class HmacDeviceHasher:
    def __init__(self, server_secret: bytes) -> None: ...
    # key = HMAC-SHA256(server_secret, b"avisabus:device-id:v1"); hash = HMAC-SHA256(key, value).hexdigest()
```

```python
# adapters/inbound/ws/passenger.py
class PassengerSnapshotProvider(Protocol):
    async def active_alerts(self, device_hash: str) -> list[Mapping[str, object]]: ...
class EmptySnapshotProvider:            # esta feature; alert_create lo sustituye
    async def active_alerts(self, device_hash: str) -> list[Mapping[str, object]]: return []

@router.websocket("/ws/passenger")      # sin prefijo /api/v1 (docs/architecture.md §7)
async def passenger_socket(websocket: WebSocket) -> None: ...
```

Protocolo (`/ws/passenger`):

| Paso | Dirección | Mensaje |
|---|---|---|
| 1 | cliente → servidor | `{"type": "hello", "device_id": "<uuid v4>"}` en ≤ 5 s (`4408` si no; `4400` si inválido) |
| 2 | servidor | `subscribe("device:<hash>")` |
| 3 | servidor → cliente | `{"type": "alerts.snapshot", "alerts": [...]}` |
| 4 | servidor → cliente | eventos del canal en orden; `{"type": "ping"}` cada 25 s |
| — | cliente → servidor | `{"type": "pong"}` u otros: se ignoran |

Códigos de cierre: `1000` normal, `1001` parada del servidor (AC-11), `1013` demasiadas
conexiones (AC-10), `4400` `hello` inválido, `4408` sin `hello`, `4429` suscripción desbordada
(AC-09).

Tareas concurrentes por conexión: una que lee del socket (ignora mensajes; detecta el cierre) y
otra que escribe (eventos y `ping`); la primera que termina cancela la otra y se cierra la
suscripción en `finally` (AC-03).

```python
# adapters/inbound/http/device.py
async def device_hash_from_header(request: Request,
                                  x_device_id: Annotated[str | None, Header()] = None) -> str: ...
# parse_device_id → hasher (de app.state) → hash; InvalidDeviceIdError → 400
# problem+json type "https://avisabus/problems/invalid-device-id"
```

### Filtro de excepciones (AC-12)

`configure_logging` añade, en el `ProcessorFormatter` y como `logging.Filter` en el *handler*
raíz, una regla: cualquier registro con `exc_info` se reescribe para conservar solo el nombre del
tipo (`error_type`) y se descartan `exc_info`, `exc_text`, `stack_info` y el mensaje original si
lo formatea `uvicorn.error` ("Exception in ASGI application"). `handle_unexpected_error` ya
registra `unhandled_exception` con el tipo; en el WebSocket, el endpoint captura `Exception`,
registra `unhandled_exception` con el tipo y cierra con `1011`. Mecanismo exacto: decisión local,
siempre que el test de AC-12 pase con un marcador en el mensaje.

## 4. Configuración

| Variable | Default |
|---|---|
| `AVISABUS_WS_MAX_CONNECTIONS` | `500` |
| `AVISABUS_WS_PING_INTERVAL_S` | `25` |
| `AVISABUS_WS_HELLO_TIMEOUT_S` | `5` |
| `AVISABUS_EVENT_QUEUE_SIZE` | `100` |

La clave del *hash* deriva de `AVISABUS_STOP_TOKEN_SECRET` (o del secreto fijo de desarrollo en
`dev`/`test`): no hay variable nueva. Cambiar el secreto invalida la relación entre dispositivos
y avisos existentes (se pierden de vista hasta que caducan); se documenta en `.env.example`.

## 5. Errores y logs

| Evento | Campos |
|---|---|
| `ws.connected` | `endpoint` |
| `ws.closed` | `endpoint`, `code`, `duration_s` |
| `ws.rejected` | `endpoint`, `code` (`1013`, `4400`, `4408`) |
| `ws.stats` (cada 5 min) | `open_connections`, `subscriptions` |
| `unhandled_exception` | `error_type`, `method` o `endpoint` |

## 6. Estrategia de test

| AC | Test |
|---|---|
| AC-01–AC-03 | `tests/unit/test_in_memory_publisher.py` (`asyncio`, sin red) |
| AC-04, AC-05 | `tests/unit/test_device.py` (tabla de UUID; *hash* estable y dependiente del secreto; `repr` sin el valor) |
| AC-06–AC-11 | `tests/integration/test_ws_passenger.py` con `starlette.testclient.TestClient.websocket_connect` (no abre sockets de red); intervalos y máximos bajos por configuración |
| AC-05 (logs), AC-12 | `tests/integration/test_log_privacy.py`: logs capturados en JSON; ruta HTTP de prueba y proveedor de instantánea que lanzan `RuntimeError("MARKER-…")`; ninguna línea contiene el marcador ni el `device_id` |
| AC-13 | `tests/unit/test_ws_connections.py` con logger falso |

La ruta HTTP que lanza la excepción se registra solo en el test (no en la app).

## 7. Decisiones locales permitidas

- Mecanismo del filtro de logs (AC-12).
- Estructura interna de `ConnectionRegistry` y del bucle de lectura/escritura.

## 8. Preguntas abiertas

Ninguna.
