# Arquitectura — AvisaBus

> Estado: **APROBADO** (v1.0 · 2026-10-31; v1.1 · 2026-11-04: avisos por viaje elegido, ADR-016, aprobada en la PR #37; v1.2 · 2026-11-09: ubicación del limitador y orden de validaciones, aprobada en la PR #45; v1.3 · 2026-11-09: conductor (salida elegida, códigos con HMAC, API y eventos), ADR-017 y ADR-018, aprobada en la PR #46). Deriva de `docs/vision.md`, `docs/requirements.md`
> y `docs/use_cases.md`. Las decisiones se registran como ADR en la sección 10.
> Los nombres de código están en inglés; ver glosario en `docs/conventions.md`.

## 1. Principios

1. **Hexagonal (puertos y adaptadores).** El dominio no conoce frameworks, HTTP, SQL ni el SAE.
2. **Fuentes de datos intercambiables.** Toda fuente externa (SAE, ocupación, GPS, reloj) entra por un puerto.
3. **Determinismo en tests.** Nada en los tests toca la red ni el reloj real.
4. **Privacidad por diseño.** Sin datos personales; lo efímero se borra al caducar.
5. **Simplicidad.** Un proceso, SQLite, eventos en memoria. Escalar es trabajo futuro.

## 2. Contexto (C4 nivel 1)

```mermaid
flowchart LR
  P([Pasajero<br/>móvil, vía QR]) -->|HTTPS| S[AvisaBus]
  C([Conductor<br/>tablet]) -->|HTTPS + WSS| S
  A([Administrador]) -->|CLI| S
  S -->|HTTP| SAE[(SAE EMT València<br/>tiempos de llegada)]
  S -.->|import| GTFS[(GTFS estático EMT)]
  P -->|teselas| OSM[(OpenStreetMap)]
  C -->|teselas| OSM
```

## 3. Contenedores (C4 nivel 2) y despliegue

Despliegue en **Raspberry Pi propia (SO de 64 bits, arm64)** con dominio propio y Docker Compose,
detrás del **Nginx Proxy Manager (NPM) ya existente** en la Raspberry.

```mermaid
flowchart LR
  Internet((Internet)) -->|443| NPM
  subgraph RPi[Raspberry Pi]
    NPM[Nginx Proxy Manager<br/>existente · TLS Let's Encrypt<br/>Websockets Support ON]
    subgraph Compose[docker compose · avisabus]
      WEB[web<br/>nginx:alpine<br/>sirve build React · SPA fallback<br/>proxy interno /api y /ws]
      BE[backend<br/>uvicorn · 1 proceso<br/>FastAPI + tareas de fondo]
      DB[(SQLite · WAL<br/>volumen data/)]
    end
    NPM -->|http://web:80| WEB
    WEB -->|/api, /ws| BE
    BE --> DB
  end
  BE -->|HTTP| SAE[(SAE EMT)]
```

- **Nginx Proxy Manager (externo al proyecto)**: termina TLS (HTTPS obligatorio para geolocalización y PWA) con un único *Proxy Host* para el dominio apuntando a `web:80`, con *Websockets Support* activado. El proyecto no gestiona certificados.
- **web**: contenedor `nginx:alpine` que sirve el build de React (con fallback a `index.html` para el router) y reenvía `/api` y `/ws` al backend por la red interna. Así NPM solo necesita un destino y la configuración de rutas vive versionada en el repositorio (`deploy/nginx/web.conf`).
- El servicio `web` se conecta a la red Docker de NPM (red externa declarada en `docker-compose.yml`, nombre configurable); `backend` solo está en la red interna del proyecto y no expone puertos.
- **backend**: un único proceso `uvicorn` (ADR-003). Contiene API REST, WebSockets, CLI (mismo paquete, otro punto de entrada) y tareas de fondo.
- **SQLite** en modo WAL sobre un volumen. Recomendado: almacenamiento en SSD/USB en lugar de la tarjeta SD (desgaste por escrituras).
- Imágenes `linux/arm64` construidas en el Mac (Apple Silicon, nativo) y llevadas a la Raspberry por SSH (`docker save | docker load`); sin registro de imágenes (`deployment_rpi`).
- Configuración por variables de entorno con prefijo `AVISABUS_` (ver `.env.example`).

## 4. Backend: capas

```
backend/
├── pyproject.toml
├── src/avisabus/
│   ├── domain/                # Puro: sin I/O, sin frameworks
│   │   ├── models/            # Entidades y value objects (dataclasses frozen)
│   │   ├── services/          # Reglas: expiry, assignment, capacity, position_estimation,
│   │   │                      #         passage_detection, occupancy_level, direction_resolver
│   │   ├── ports/             # Protocols (interfaces) hacia el exterior
│   │   └── errors.py          # Excepciones de dominio
│   ├── application/           # Casos de uso (1 módulo por CU), orquestan dominio + puertos
│   ├── adapters/
│   │   ├── inbound/
│   │   │   ├── http/          # Routers FastAPI, esquemas Pydantic, mapeo de errores
│   │   │   ├── ws/            # Endpoints WebSocket
│   │   │   └── cli/           # Typer: gtfs, qr, driver-codes, simulate, sae-record
│   │   └── outbound/
│   │       ├── sae/           # http, cache, replay, recorder, scheduled_fallback
│   │       ├── persistence/   # SQLAlchemy + SQLite: network, alerts, driver sessions/codes
│   │       ├── occupancy/     # simulated sensor
│   │       ├── events/        # in-memory pub/sub
│   │       ├── security/      # HMAC stop tokens and device ids, code hashing
│   │       ├── rate_limit/    # in-memory sliding-window rate limiter
│   │       └── clock.py       # SystemClock
│   ├── background/            # PassageWatcher, AlertExpiryTicker, DriverSessionReaper
│   ├── config.py              # pydantic-settings
│   └── main.py                # Composition root: crea adaptadores e inyecta en casos de uso
└── tests/
    ├── unit/                  # domain + application con fakes
    ├── integration/           # adaptadores (SQLite temporal, replay SAE), API con TestClient
    └── fixtures/
        ├── gtfs_mini/         # GTFS reducido (2–3 líneas, ~20 paradas)
        └── sae_recordings/    # Respuestas SAE grabadas (JSON)
```

**Regla de dependencias** (verificada con import-linter):

```
adapters ──▶ application ──▶ domain
background ─▶ application
domain ──▶ (nada de avisabus fuera de domain)
```

Solo `main.py` (composition root) conoce las implementaciones concretas.

## 5. Modelo de dominio

```mermaid
classDiagram
  class Stop { stop_id: str; name: str; lat; lon }
  class Line { short_name: str; route_ids: set }
  class Direction { line: str; direction_id: int; headsign: str }
  class Shape { shape_id; points: list }
  class Arrival { line; destination; eta: timedelta|None; scheduled_at: time|None; source: REALTIME|SCHEDULED; in_network: bool }
  class EstimatedPosition { lat; lon; shape_distance_m; source: REALTIME|SCHEDULED }
  class Occupancy { capacity; occupied; free_seats; level: FREE|MEDIUM|FULL }
  class Alert { alert_id; stop_id; line; direction_id; trip_id; service_date; stop_sequence; needs: set~Need~; device_hash; created_at; status; last_seen_at; last_arrival_at; last_delay_s; delivered_to: session_id|None }
  class Need { <<enum>> RAMP; EXTRA_TIME; SEAT; VISUAL }
  class AlertStatus { <<enum>> PENDING_DRIVER; DELIVERED; EXPIRED; CANCELLED }
  class DriverSession { session_id; token_hash; code_id; line; direction_id; trip_id; service_date; position; progress_m; off_route; last_fix_at; last_seen_at }
  class DriverCode { code_id; code_hash; label; created_at; revoked_at }
  Alert --> Need
  Alert --> AlertStatus
  Line "1" --> "*" Direction
  Direction --> Shape
  DriverSession --> Direction
```

Notas:
- `Line` agrupa `route_id` por `route_short_name` (RF-03).
- `Alert.device_hash`: hash del identificador anónimo del dispositivo; nunca se guarda en claro.
- `Alert.trip_id`/`service_date`: el autobús elegido por el pasajero (ADR-013, ADR-016). `last_seen_at`, `last_arrival_at` y `last_delay_s`: última observación en tiempo real de ese viaje en la parada; base de la detección de paso (D12) y de la estimación de llegada a la parada siguiente.
- Los avisos `EXPIRED`/`CANCELLED` se **borran** (RNF-06); los estados existen solo para emitir el evento final.

### Servicios de dominio clave

| Servicio | Responsabilidad | RF |
|---|---|---|
| `derive_directions` | El feed de EMT no trae `direction_id`: lo deriva al importar por línea, a partir de los extremos de cada trazado. Las circulares de EMT (C1, C2, C3) vienen partidas en medios viajes y se tratan igual ("hacia el destino de cada mitad"); la regla por orientación queda para feeds con el bucle en un solo viaje. Guarda todas las formas de cada sentido. | RF-03 |
| `DirectionResolver` | Traduce el `destino` del SAE a `direction_id` para una parada y línea, en este orden: sentido único en la parada → override (por headsign) → coincidencia de texto con los headsigns de los viajes que paran allí → **sentido que sale** de la parada (cabeceras) → sin resolver. | RF-11, RF-16 |
| `PositionEstimator` | Dado ETA a una parada y los tiempos programados entre paradas del viaje, sitúa el autobús sobre el shape (interpolación por distancia). | RF-12 |
| `OccupancyClassifier` | Convierte ocupación en nivel con umbrales configurables. | RF-15 |
| `AlertAssigner` | Asigna el aviso al autobús elegido (viaje GTFS) y busca, mediante el puerto `DriverDirectory`, el conductor conectado que lleva ese servicio (en el bloque 3 no hay conductores: el aviso queda "sin conductor conectado"). | RF-20, RF-23 |
| `PassageDetector` | Con cada observación en tiempo real de la parada: si el viaje del aviso aparece, actualiza su seguimiento; si desaparece y en la última observación llegaba en ≤ 2 min, ha pasado. | RF-21 |
| `ExpiryPolicy` | Paso por la parada, llegada estimada a la siguiente (horario + último retraso) o 30 min desde la creación. | RF-21 |
| `UpcomingStopsResolver` | Proyecta la posición GPS del conductor sobre el shape y devuelve las próximas N paradas; detecta desvío > 150 m. | RF-26 |
| `CapacityAlertPolicy` | Σ personas esperando en próximas paradas > plazas libres. | RF-29 |

## 6. Puertos y adaptadores

| Puerto (domain/ports) | Adaptadores | Notas |
|---|---|---|
| `ArrivalsSource` | `SaeHttpArrivalsSource`, `SaeReplayArrivalsSource` + decoradores `CachedArrivalsSource` (TTL 20 s), `RecordingArrivalsSource`, `ScheduledFallbackArrivalsSource` | La composición por defecto: Fallback(Cached(SaeHttp)). En tests: Replay. |
| `NetworkRepository` | `SqliteNetworkRepository` | Paradas, líneas, direcciones, shapes, horarios activos por fecha. |
| `AlertRepository` | `SqliteAlertRepository` | Persistente para sobrevivir a reinicios. |
| `DriverSessionRepository` | `SqliteDriverSessionRepository` | Posición solo la última; se borra al cerrar turno. |
| `DriverCodeRepository` | `SqliteDriverCodeRepository` | HMAC-SHA256 con clave derivada del secreto del servidor (ADR-017). |
| `OccupancySensor` | `SimulatedOccupancySensor` | Determinista con semilla configurable. |
| `EventPublisher` | `InMemoryEventPublisher` | Pub/sub por canal (`device:<hash>`, `driver:<session>`). |
| `DeviceHasher` | `HmacDeviceHasher` | `device_hash` = HMAC-SHA256 del identificador anónimo con una clave derivada del secreto del servidor. |
| `DriverDirectory` | `NoDriverDirectory` (bloque 3); `SessionDriverDirectory` (`driver_demand`) | Turno abierto que lleva un viaje (el conductor elige su salida, ADR-018). |
| `Clock` | `SystemClock`, `FakeClock` (tests) | Siempre `datetime` UTC con zona. |
| `StopTokenSigner` | `HmacStopTokenSigner` | Token = HMAC-SHA256(secret, stop_id) truncado, base64url. |

## 7. Superficie de la API

Prefijo `/api/v1`. JSON en `snake_case`. Respuestas > 1 KB comprimidas con gzip. Errores en formato RFC 9457 (`application/problem+json`).
El cliente envía el identificador anónimo de dispositivo en la cabecera `X-Device-Id`.
El contrato es el OpenAPI generado por FastAPI; el frontend genera sus tipos a partir de él.

| Método | Ruta | Uso | CU |
|---|---|---|---|
| GET | `/stops/{stop_id}?t={token}` | Datos de parada y líneas | CU-01 |
| GET | `/stops/{stop_id}/arrivals?t={token}` | Llegadas + ocupación | CU-01 |
| GET | `/stops/{stop_id}/lines/{line}/position?direction_id=&t=` | Posición estimada del próximo autobús (incluye `shape_id` del viaje) | CU-02 |
| GET | `/shapes/{shape_id}` | Trazado (coordenadas GeoJSON) y paradas; cacheable con `ETag` | CU-02 |
| POST | `/alerts` | Crear aviso (`stop_id`, `token`, `line`, `direction_id`, `trip_id`, `service_date`, `needs`) | CU-03 |
| GET | `/alerts/mine` | Avisos activos del dispositivo | CU-03 |
| DELETE | `/alerts/{alert_id}` | Cancelar | CU-04 |
| POST | `/driver/sessions` | Iniciar turno (`code`) → token de sesión | CU-08 |
| GET | `/driver/lines` · `/driver/departures` | Líneas y salidas próximas de una línea y sentido | CU-08 |
| PUT | `/driver/sessions/current/service` | Elegir salida (`line`, `direction_id`, `trip_id`, `service_date`) | CU-08 |
| GET | `/driver/sessions/current` · `/driver/sessions/current/view` | Estado del turno · vista de demanda (respaldo del WebSocket) | CU-09 |
| PUT | `/driver/sessions/current/position` | Enviar posición GPS | CU-09 |
| DELETE | `/driver/sessions/current` | Finalizar turno | CU-10 |
| WS | `/ws/passenger` | Eventos de los avisos del dispositivo | CU-03/04/07 |
| WS | `/ws/driver` | Snapshot + eventos de la vista de conductor | CU-09 |

### Eventos (WebSocket)

| Evento | Canal | Contenido |
|---|---|---|
| `alerts.snapshot` | pasajero | avisos activos del dispositivo, al conectarse (tras el mensaje `hello` con el identificador) |
| `alert.registered` | pasajero | aviso creado, sin conductor |
| `alert.delivered` | pasajero | entregado a la vista del conductor |
| `alert.expired` | pasajero | motivo: `PASSED` \| `NEXT_STOP` \| `TIMEOUT` |
| `alert.cancelled` | pasajero | confirmación de cancelación |
| `driver.view` | conductor | snapshot completo: próximas paradas, avisos, plazas libres, alerta de capacidad, estado GPS |
| `session.closed` | conductor | el turno se ha cerrado (`ENDED`, `IDLE`, `REVOKED`, `REPLACED`) |

La vista del conductor recibe siempre **snapshots completos** (no deltas): simplifica el cliente y la reconexión.

## 8. Tareas de fondo

| Tarea | Frecuencia | Función |
|---|---|---|
| `PassageWatcher` | cada 15 s | Para cada (parada, línea, sentido) con avisos activos, consulta `ArrivalsSource` (vía caché) y aplica `PassageDetector`. |
| `AlertExpiryTicker` | cada 10 s | Caduca avisos con más de 30 min. |
| `DriverSessionReaper` | cada 60 s | Cierra sesiones sin posición en 10 min. |
| `FeedValidityCheck` | al arrancar y diario | Avisa si el feed caduca en ≤ 7 días. |

Todas reciben el `Clock` inyectado y exponen un método `tick()` que los tests invocan directamente.

## 9. Secuencias principales

### Crear aviso (CU-03)

```mermaid
sequenceDiagram
  participant PA as Pasajero (PWA)
  participant API as API /alerts
  participant UC as CreateAlert
  participant AS as AlertAssigner
  participant REPO as AlertRepository
  participant EV as EventPublisher
  participant DR as Conductor (WS)
  PA->>API: POST /alerts (X-Device-Id, token, line, direction_id, needs)
  API->>UC: execute(cmd)
  UC->>UC: rate limit (dispositivo, IP), unicidad, token y autobús (GetStopArrivals)
  UC->>AS: assign(stop, trip elegido)
  AS-->>UC: driver_session?
  UC->>REPO: save(alert)
  alt hay conductor conectado
    UC->>EV: publish driver:<session> driver.view
    EV-->>DR: snapshot actualizado
    UC->>EV: publish device:<hash> alert.delivered
  else sin conductor
    UC->>EV: publish device:<hash> alert.registered
  end
  API-->>PA: 201 alert
```

### Caducidad por paso del autobús (CU-07)

```mermaid
sequenceDiagram
  participant W as PassageWatcher
  participant SRC as ArrivalsSource
  participant PD as PassageDetector
  participant REPO as AlertRepository
  participant EV as EventPublisher
  W->>REPO: active alert groups (stop, line, direction)
  loop cada grupo
    W->>SRC: arrivals(stop)
    W->>PD: passed?(seguimiento del viaje, new arrivals)
    alt ha pasado
      W->>REPO: delete alerts del grupo
      W->>EV: alert.expired(PASSED) a cada dispositivo
      W->>EV: driver.view al conductor afectado
    else no
      W->>REPO: update seguimiento (last_seen_at, last_arrival_at, last_delay_s)
    end
  end
```

## 10. Frontend

```
frontend/src/
├── app/                 # Router, providers (QueryClient, i18n), layout
├── features/
│   ├── passenger/
│   │   ├── stop/        # Vista de parada y llegadas (CU-01)
│   │   ├── map/         # Mapa y posición estimada (CU-02)
│   │   ├── alerts/      # Crear/cancelar aviso, estado (CU-03/04)
│   │   └── profile/     # Perfil de accesibilidad local (CU-05)
│   └── driver/
│       ├── login/       # Código + línea/sentido (CU-08)
│       └── demand/      # Vista de demanda (CU-09/10)
├── shared/
│   ├── api/             # Cliente generado desde OpenAPI + hooks TanStack Query
│   ├── ws/              # Cliente WebSocket con reconexión
│   ├── device/          # Identificador anónimo (localStorage)
│   ├── i18n/            # Configuración i18next
│   └── ui/              # Componentes accesibles reutilizables
└── locales/
    ├── es/translation.json
    └── ca-valencia/translation.json
```

| Ruta | Vista |
|---|---|
| `/p/:stopId?t=:token` | Vista de parada (destino del QR) |
| `/p/:stopId/map/:line/:directionId` | Mapa |
| `/profile` | Perfil de accesibilidad |
| `/driver` | Acceso conductor |
| `/driver/shift` | Vista de demanda |

## 11. Decisiones de arquitectura (ADR)

| ADR | Decisión | Alternativas descartadas | Motivo |
|---|---|---|---|
| ADR-001 | Arquitectura hexagonal | MVC por capas | OBJ-08: sustituir fuentes sin tocar dominio |
| ADR-002 | SQLite (WAL) | PostgreSQL/PostGIS | Sin servidor; tests sin servicios; suficiente para el volumen |
| ADR-003 | Un proceso, eventos en memoria | Redis pub/sub, varios workers | RNF-12 (200 clientes) se cumple; menos piezas en la Raspberry |
| ADR-004 | ETA del SAE con caché 20 s y respaldo GTFS | Solo horario GTFS | Datos reales con uso respetuoso de una API no documentada |
| ADR-005 | Posición estimada por interpolación sobre shape | Simulación total; sin mapa | No existe feed público de posiciones |
| ADR-006 | Detección de paso solo con SAE | GPS del conductor | Igual comportamiento con o sin conductor; GPS como mejora futura |
| ADR-007 | Raspberry Pi + Docker Compose detrás del Nginx Proxy Manager existente; contenedor `web` (nginx) propio para estáticos y proxy interno | PaaS; Caddy | Infraestructura ya operativa del autor; TLS centralizado en NPM; rutas versionadas en el repo |
| ADR-008 | Código en inglés; documentación en castellano | Todo en castellano | Mejor encaje con librerías y agentes IA |
| ADR-009 | Snapshots completos a la vista del conductor | Deltas | Cliente simple, reconexión trivial |
| ADR-010 | Tipos del frontend generados desde OpenAPI | Tipos manuales | Contrato único entre backend y frontend |
| ADR-011 | Esquema con `create_all` y sin migraciones; datos de red versionados por `feed_version_id` con activación atómica | Alembic | Los datos de red son reimportables y los efímeros no necesitan migrarse; menos piezas |
| ADR-012 | Repositorios SQLite síncronos invocados desde casos de uso `async` | SQLAlchemy async / aiosqlite | Consultas locales de milisegundos; más simple de testear |
| ADR-013 | Identidad del autobús = viaje GTFS emparejado con el ETA (`TripMatcher`) | Identificador de vehículo | El SAE no publica vehículos; el viaje da una identidad estable para posición, ocupación y avisos |
| ADR-014 | Trazado servido por `shape_id` (no por línea y sentido) | `/lines/{line}/directions/{d}/shape` | El viaje concreto puede usar una variante de recorrido distinta de la representativa |
| ADR-015 | Tiempos de llegada leídos de la página `QR.php` (HTML) que enlaza el Ajuntament, con User-Agent identificado | XML `getSAE` mediante `emtvlcapi`/`pyemtvlc` | EMT restringe `getSAE` a su visor; usarlo exigiría imitar al visor y eludir un control de acceso. Permiso solicitado a EMT el 2026-11-02; si lo concede, adaptador nuevo tras `ArrivalsSource` |
| ADR-016 | El aviso se asigna al **viaje GTFS** que elige el pasajero (no al "próximo autobús") y se sigue por ese viaje | Seguir el ETA mínimo de la línea | Permite esperar a un autobús menos lleno; la identidad por viaje (ADR-013) evita confundir autobuses al detectar el paso. Si el emparejamiento cambia de viaje entre consultas, el aviso puede caducar más tarde (LIM-02) |
| ADR-017 | Códigos de conductor con HMAC-SHA256 y clave derivada del secreto del servidor | `scrypt` por código | Búsqueda por índice; con 8 dígitos la protección real es el límite de intentos y, sin el secreto, la base de datos no permite probar códigos |
| ADR-018 | El conductor elige la **salida** (viaje GTFS) al iniciar el turno | Deducir el viaje con GPS, horario y SAE | Entrega exacta de las solicitudes por viaje (ADR-016); un paso más para el conductor, una vez por recorrido |

## 12. Riesgos técnicos

| ID | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| R-01 | El SAE cambia o bloquea el acceso (EMT ya cerró `getSAE` a terceros; `QR.php` es HTML y puede cambiar) | Sin tiempos reales | Respaldo GTFS; grabaciones para demo; parser aislado que falla de forma explícita (`unparseable`); permiso solicitado a EMT (ADR-015) |
| R-02 | El `destino` del SAE no casa con los headsign del GTFS; el feed no trae `direction_id` | Aviso con sentido erróneo | Sentidos derivados y validados por la persona (`gtfs info --directions`); `DirectionResolver` con todos los headsigns de la parada, normalización, alias y *overrides*; tests con grabaciones reales |
| R-03 | Recursos de la Raspberry (RAM/CPU) al importar `stop_times` (33 MB) | Importación lenta | Importación por lotes en streaming; importar en el Mac y copiar la BD si hace falta |
| R-04 | Caducidad mensual del feed GTFS | Horarios desfasados | RF-02 + comprobación diaria |
| R-05 | Desgaste de la tarjeta SD | Corrupción de BD | SSD/USB, WAL, copias de seguridad |
