# Eventos en tiempo real — requirements

> Feature: `realtime_events` · Versión: 1.2 · Estado: APPROVED
> Requisitos: RF-23, RF-28 (base), RNF-02, RNF-06, RNF-07, RNF-12, RNF-13 · Casos de uso: CU-03, CU-04, CU-07 (canal) · Depende de: project_scaffold

## Contexto

Las solicitudes de parada (en código, avisos: `Alert`) cambian de estado sin que el pasajero haga
nada: se entregan al conductor (bloque 4), caducan porque el autobús ha pasado o se cancelan desde
otra pestaña. El pasajero se entera por un **WebSocket** (`/ws/passenger`) que recibe los eventos
de los avisos de su dispositivo.

Esta feature pone la infraestructura común del bloque 3:

- un **publicador de eventos en memoria** por canales (ADR-003: un solo proceso);
- el **identificador anónimo del dispositivo** (`X-Device-Id`): validación y *hash* con clave del
  servidor, para que el identificador en claro no se guarde ni se registre nunca (RNF-06);
- el **WebSocket del pasajero** con un protocolo mínimo (`hello` → `alerts.snapshot` → eventos);
- la regla pendiente **H-01** de `project_scaffold` (`docs/conventions.md` §3): ninguna excepción
  no controlada llega a los logs con su mensaje, porque desde este bloque los mensajes podrían
  contener identificadores.

Los avisos en sí (crear, listar, cancelar, caducar) llegan en `alert_create`, `alert_cancel` y
`alert_expiry`; aquí el WebSocket envía una instantánea vacía hasta que `alert_create` conecta su
proveedor. El WebSocket del conductor (`/ws/driver`) se especifica con `driver_demand` (bloque 4),
reutilizando el publicador.

## Alcance

- Puerto `EventPublisher` e implementación `InMemoryEventPublisher` con colas acotadas.
- Puerto `DeviceHasher` e implementación `HmacDeviceHasher`; validación de `X-Device-Id`.
- Endpoint WebSocket `/ws/passenger` con su protocolo, latido y límites.
- Filtro de logs que impide registrar mensajes de excepciones no controladas (H-01).
- Cierre ordenado de los WebSockets al parar la aplicación.

## Fuera de alcance

- Contenido de los eventos de avisos y su emisión (`alert_create`, `alert_cancel`, `alert_expiry`).
- WebSocket y canal del conductor (`driver_demand`).
- Cliente WebSocket del frontend (`passenger_alert_ui`).
- Configuración de `nginx`/NPM para WebSockets (`deployment_rpi`).

## Criterios de aceptación

### Publicador de eventos

- **realtime_events.AC-01** — CUANDO se publica un evento en un canal, EL PUBLICADOR DEBERÁ
  entregarlo a todas las suscripciones activas de ese canal, en el orden de publicación, y a
  ninguna de otros canales.
  *Verificación:* unit
- **realtime_events.AC-02** — SI la cola de una suscripción alcanza su capacidad (100 eventos por
  defecto), ENTONCES EL PUBLICADOR DEBERÁ marcarla como desbordada y dejar de encolarle eventos,
  sin bloquear la publicación ni afectar al resto de suscripciones.
  *Verificación:* unit
- **realtime_events.AC-03** — CUANDO una suscripción se cierra (o su conexión termina por
  cualquier motivo), EL PUBLICADOR DEBERÁ eliminarla, de modo que no queden suscripciones
  huérfanas.
  *Verificación:* unit + integration (número de suscripciones tras cerrar el WebSocket)

### Identificador del dispositivo

- **realtime_events.AC-04** — EL SISTEMA DEBERÁ aceptar como identificador de dispositivo solo un
  UUID versión 4 en forma canónica (36 caracteres, minúsculas, con guiones) y rechazar cualquier
  otro valor.
  *Verificación:* unit (tabla de casos válidos e inválidos)
- **realtime_events.AC-05** — EL SISTEMA DEBERÁ obtener `device_hash` como HMAC-SHA256 del
  identificador con una clave derivada del secreto del servidor (`AVISABUS_STOP_TOKEN_SECRET`,
  con separación de dominio), en hexadecimal; el mismo identificador DEBERÁ dar siempre el mismo
  *hash* con el mismo secreto, y otro distinto con otro secreto. EL IDENTIFICADOR EN CLARO NO
  DEBERÁ guardarse ni aparecer en ningún log.
  *Verificación:* unit + integration (logs capturados de una sesión WebSocket completa)

### WebSocket del pasajero

- **realtime_events.AC-06** — CUANDO un cliente abre `/ws/passenger`, EL SISTEMA DEBERÁ esperar
  como primer mensaje `{"type": "hello", "device_id": "<uuid>"}`; SI no llega en 5 s, ENTONCES
  DEBERÁ cerrar con el código `4408`, y SI el mensaje no es válido (JSON incorrecto, otro tipo o
  identificador inválido), ENTONCES DEBERÁ cerrar con el código `4400`.
  *Verificación:* integration
- **realtime_events.AC-07** — CUANDO el `hello` es válido, EL SISTEMA DEBERÁ suscribirse al canal
  `device:<device_hash>` **antes** de pedir la instantánea, enviar
  `{"type": "alerts.snapshot", "alerts": [...]}` con los avisos activos del dispositivo (lista que
  da un proveedor inyectable; vacía en esta feature) y, a continuación, reenviar en orden los
  eventos del canal. Un evento publicado entre la suscripción y el envío de la instantánea DEBERÁ
  llegar después de ella.
  *Verificación:* integration
- **realtime_events.AC-08** — MIENTRAS la conexión esté abierta, EL SISTEMA DEBERÁ enviar
  `{"type": "ping"}` cada 25 s; los mensajes posteriores del cliente DEBERÁN ignorarse salvo
  `{"type": "pong"}`, que tampoco tiene efecto.
  *Verificación:* integration (intervalo configurable en el test)
- **realtime_events.AC-09** — SI la suscripción de una conexión se desborda (AC-02), ENTONCES EL
  SISTEMA DEBERÁ cerrarla con el código `4429`, para que el cliente se reconecte y reciba una
  instantánea nueva.
  *Verificación:* integration
- **realtime_events.AC-10** — SI ya hay abiertas tantas conexiones WebSocket como el máximo
  configurado (500 por defecto), ENTONCES EL SISTEMA DEBERÁ cerrar las nuevas con el código
  `1013` sin procesar su `hello`.
  *Verificación:* integration (máximo bajo en el test)
- **realtime_events.AC-11** — CUANDO la aplicación se detiene, EL SISTEMA DEBERÁ cerrar las
  conexiones abiertas con el código `1001` (Going Away) o `1012` (Service Restart). (v1.1) Al
  apagarse por la vía del `lifespan` la aplicación cierra con `1001`; si el servidor ASGI
  (`uvicorn` al recibir SIGTERM) cierra antes las conexiones, el cliente recibe `1012`, que es
  igualmente válido. El cliente trata ambos como un cierre tras el que debe reconectar.
  *Verificación:* integration (cierre por el `lifespan`: `1001`)

### Privacidad de los logs (H-01)

- **realtime_events.AC-12** — SI una excepción no controlada se produce al atender una petición
  HTTP o una conexión WebSocket, ENTONCES el log DEBERÁ registrar solo el evento
  `unhandled_exception` con el tipo de la excepción, y NI el mensaje de la excepción NI una traza
  que lo contenga DEBERÁN aparecer en ninguna línea de log, tampoco en las de `uvicorn`.
  *Verificación:* integration (excepción con un mensaje marcador en una ruta HTTP y en el
  WebSocket; ninguna línea capturada contiene el marcador)
- **realtime_events.AC-13** — EL SISTEMA DEBERÁ registrar `ws.connected` y `ws.closed` (con el
  código de cierre y la duración) sin `device_id` ni `device_hash`, y `ws.stats` cada 5 min con el
  número de conexiones abiertas.
  *Verificación:* unit (logger falso) + revisión

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-23 / RF-28 Confirmación y actualización en tiempo real (canal) | AC-01, AC-06, AC-07 |
| RNF-02 Latencia de eventos | AC-01, AC-07 |
| RNF-06 Privacidad | AC-05, AC-12, AC-13 |
| RNF-07 Seguridad (validación de entradas) | AC-04, AC-06 |
| RNF-12 Capacidad | AC-02, AC-09, AC-10 |
| RNF-13 Observabilidad | AC-13 |
| H-01 de `project_scaffold` (`docs/conventions.md` §3) | AC-12 |
| ADR-003 Eventos en memoria | AC-01, AC-02, AC-03 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-04 | Versión inicial aprobada (PR #37). | CP-1 del bloque 3. Aprobada por la persona. |
| 1.1 | 2026-11-04 | AC-11 admite `1001` o `1012`: `uvicorn` cierra los WebSockets con `1012` al recibir SIGTERM, antes que el `lifespan`. Sin cambios de código. | CP-3 de `realtime_events` (T-04). Aprobada por la persona (PR #38). |
| 1.2 | 2026-11-09 | Solo design y arnés: la composición está en `http/app.py` y `http/container.py` (no en `main.py`); T-06 añade `pytest-timeout` (30 s por test) para que una espera sin límite falle en vez de colgar la suite. | N-02 y N-03 de la revisión de `realtime_events` (CP-6 del bloque 3). Aprobada por la persona (PR #45). |
