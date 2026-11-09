# Turno del conductor — requirements

> Feature: `driver_session` · Versión: 1.2 · Estado: APPROVED
> Requisitos: RF-24, RF-25, RF-26, RF-30, RNF-06, RNF-07, RNF-13 · Casos de uso: CU-08, CU-09 (posición), CU-10, CU-13 (revocación) · Depende de: gtfs_import, driver_codes_cli

## Contexto

El conductor inicia su turno en la tablet con su código (RF-24), elige **línea, sentido y la
salida que hace** (RF-25; decisión de la persona, ADR-018) y la tablet envía su posición GPS
cada pocos segundos. Con la salida elegida el sistema sabe **qué viaje GTFS** lleva cada
conductor, que es como se identifican los autobuses de las solicitudes (ADR-016): así la entrega
es exacta. Con la posición, el sistema calcula sus **próximas paradas** (RF-26) y si se ha
salido del recorrido.

El turno termina cuando el conductor lo finaliza (RF-30), tras 10 min sin posición, si el
administrador revoca su código o si inicia otro turno con el mismo código. La posición se borra
al terminar.

Esta feature gestiona la sesión y la posición; la demanda (solicitudes, plazas, alerta de
capacidad) y el WebSocket del conductor son de `driver_demand`.

## Alcance

- Modelo `DriverSession`, repositorio SQLite y token de sesión.
- Endpoints `/api/v1/driver/...`: iniciar turno, líneas, salidas, elegir salida, posición,
  estado y finalizar.
- Límite de intentos fallidos de código (CU-08 2a).
- `UpcomingStopsResolver`: proyección de la posición sobre el trazado del viaje.
- Tarea de fondo `DriverSessionReaper`.
- Puerto `DriverSessionListener` (avisos al abrir, cambiar o cerrar un turno), vacío aquí.

## Fuera de alcance

- Demanda, entrega de solicitudes, alerta de capacidad y `/ws/driver` (`driver_demand`).
- Interfaz (`driver_ui`) y simulador (`driver_gps_simulator`).

## Criterios de aceptación

### Inicio y autenticación

- **driver_session.AC-01** — CUANDO se hace `POST /api/v1/driver/sessions` con `{"code": …}`
  válido (8 dígitos; se ignoran espacios) de un código activo, LA API DEBERÁ crear una sesión y
  responder `201` con `session_id`, `session_token` (aleatorio, ≥ 32 bytes, base64url) y
  `idle_timeout_s` (600). EL SISTEMA DEBERÁ guardar solo el SHA-256 del token.
  *Verificación:* integration
- **driver_session.AC-02** — SI el código no existe o está revocado, ENTONCES LA API DEBERÁ
  responder `401` (`…/invalid-driver-code`) con el mismo cuerpo en ambos casos. SI desde una IP
  se acumulan 5 intentos fallidos en 15 min, ENTONCES DEBERÁ responder `429` (`…/rate-limited`,
  con `Retry-After`) a cualquier intento desde esa IP hasta 15 min después del último fallo,
  aunque el código sea válido.
  *Verificación:* unit (`FakeClock`) + integration
- **driver_session.AC-03** — SI el código ya tiene un turno abierto, ENTONCES EL SISTEMA DEBERÁ
  cerrar ese turno (motivo `REPLACED`) antes de crear el nuevo.
  *Verificación:* integration
- **driver_session.AC-04** — LOS ENDPOINTS de turno (todos salvo el `POST` de inicio) DEBERÁN
  exigir `Authorization: Bearer <session_token>` de una sesión abierta; SI falta o no es válido,
  ENTONCES DEBERÁN responder `401` (`…/invalid-session`).
  *Verificación:* integration

### Línea, sentido y salida

- **driver_session.AC-05** — CUANDO se hace `GET /api/v1/driver/lines`, LA API DEBERÁ devolver
  las líneas de la red activa en el orden de `line_order`, con color, color de texto y sus
  sentidos (`direction_id`, `headsign`).
  *Verificación:* integration
- **driver_session.AC-06** — CUANDO se hace `GET /api/v1/driver/departures?line=…&direction_id=…`,
  LA API DEBERÁ devolver los viajes de esa línea y sentido con servicio activo cuya salida de la
  primera parada está entre 30 min antes y 60 min después de ahora (incluidos los de horas
  ≥ 24:00 del día de servicio anterior), ordenados por hora, con `trip_id`, `service_date`,
  `departure_at`, nombre de la primera parada, `headsign` y `taken` (si otro turno abierto ya lo
  lleva).
  *Verificación:* unit (ventana y día de servicio con `FakeClock`) + integration (`gtfs_mini`)
- **driver_session.AC-07** — CUANDO se hace `PUT /api/v1/driver/sessions/current/service` con
  `{line, direction_id, trip_id, service_date}` de una salida que AC-06 devolvería, EL SISTEMA
  DEBERÁ asociarla a la sesión, reiniciar su progreso y avisar a `DriverSessionListener`; SI la
  salida no es válida, ENTONCES DEBERÁ responder `422` (`…/invalid-departure`), y SI otro turno
  abierto ya la lleva, `409` (`…/departure-taken`). El conductor PUEDE cambiar de salida durante
  el turno (p. ej. al terminar un recorrido).
  *Verificación:* integration

### Posición y próximas paradas

- **driver_session.AC-08** — CUANDO se hace `PUT /api/v1/driver/sessions/current/position` con
  `{lat, lon, accuracy_m, recorded_at}`, EL SISTEMA DEBERÁ guardar solo la última posición
  (descartando las que tengan `recorded_at` anterior a la guardada) y responder `204`; SI los
  valores están fuera de rango (lat/lon, `accuracy_m` < 0, `recorded_at` más de 30 s en el
  futuro), ENTONCES `422`.
  *Verificación:* integration
- **driver_session.AC-09** — CON una salida elegida, EL SISTEMA DEBERÁ proyectar cada posición
  sobre el trazado de su viaje y el progreso NO DEBERÁ retroceder. (v1.1) La búsqueda DEBERÁ
  limitarse a lo que el autobús ha podido recorrer: de 100 m por detrás del progreso anterior a
  `20 m/s × Δt + 50 m` por delante, siendo `Δt` el tiempo entre el `recorded_at` de la posición y
  el de la última aceptada (mínimo 0); sin progreso anterior (primera posición o salida recién
  elegida), en todo el trazado, quedándose con el tramo **más temprano** cuya distancia a la
  posición no supere en más de 30 m a la mínima (el autobús empieza el recorrido por el principio).
  SI la posición está a más de 150 m del trazado **dentro de esa ventana**, ENTONCES DEBERÁ marcar
  `off_route = true` sin cambiar el progreso (CU-08 4b); la ventana sigue creciendo con `Δt`, de
  modo que el progreso se recupera al volver al recorrido.
  *Verificación:* unit (trazado sintético con bucle, con ida y vuelta por la misma calle y con dos
  pasadas a pocos metros separadas por 400 m de recorrido; hueco de GPS de 5 min) + integration
  `slow` con los trazados del feed real: recorriendo cada trazado a 30 km/h con una posición cada
  5 s y ruido gaussiano σ = 10 m (semilla fija, correlado ρ = 0,95 e independiente), NINGUNA
  posición DEBERÁ tener el progreso más de 150 m por delante del real ni más de 150 m por detrás
  (v1.2: las pasadas posteriores que causaban P-01 están a 330 m o más). (v1.2) El progreso, las
  ventanas y los márgenes de AC-09 y AC-10 se miden en **metros reales** sobre la forma, con las
  mismas distancias que `position_estimation.AC-06` v1.4.
- **driver_session.AC-10** — EL SISTEMA DEBERÁ calcular las próximas paradas del viaje como las
  que están más de 20 m por delante del progreso, en orden y hasta 5, con `stop_id`, nombre,
  `stop_sequence` y distancia; SI el progreso alcanza la última parada (a menos de 20 m), ENTONCES
  DEBERÁ marcar el recorrido como terminado (`finished = true`, sin próximas paradas).
  *Verificación:* unit
- **driver_session.AC-11** — CUANDO se hace `GET /api/v1/driver/sessions/current`, LA API DEBERÁ
  devolver la salida elegida, `gps` (`WAITING` sin posición; `OK`; `STALE` si la última tiene más
  de 30 s, CU-09 1a), `off_route`, `finished` y las próximas paradas.
  *Verificación:* integration

### Fin del turno

- **driver_session.AC-12** — CUANDO se hace `DELETE /api/v1/driver/sessions/current`, EL SISTEMA
  DEBERÁ borrar la sesión con su posición (RF-30), responder `204` y avisar a
  `DriverSessionListener` con el motivo `ENDED`.
  *Verificación:* integration
- **driver_session.AC-13** — `DriverSessionReaper`, cada 60 s, DEBERÁ cerrar con el mismo efecto
  las sesiones sin posición en los últimos 10 min (contando desde el inicio si nunca la hubo;
  motivo `IDLE`) y las de códigos revocados (motivo `REVOKED`); DEBERÁ exponer `tick()` y seguir
  tras una excepción (solo el tipo en el log).
  *Verificación:* unit (`FakeClock`) + integration (`lifespan`)
- **driver_session.AC-14** — `driver-codes list` y `driver-codes revoke` DEBERÁN informar de si
  el código tiene un turno abierto consultando las sesiones (sustituye al valor fijo de
  `driver_codes_cli`).
  *Verificación:* integration

### Privacidad y logs

- **driver_session.AC-15** — NINGÚN log DEBERÁ incluir el código, el token, las coordenadas ni la
  IP; EL SISTEMA DEBERÁ registrar `driver.session_started`, `driver.service_selected` (línea,
  sentido, `trip_id`), `driver.session_closed` (motivo, duración) con `session_id`, y
  `driver.login_failed` sin datos del intento. Las respuestas de `/driver` DEBERÁN llevar
  `Cache-Control: no-store`.
  *Verificación:* unit (logger falso) + integration (logs capturados)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-24 Código de acceso | AC-01, AC-02, AC-04 |
| RF-25 Línea, sentido (y salida) | AC-05, AC-06, AC-07 |
| RF-26 Próximas paradas por GPS | AC-08, AC-09, AC-10, AC-11 |
| RF-30 Finalizar turno | AC-12, AC-13 |
| RNF-06 Privacidad | AC-01, AC-12, AC-15 |
| RNF-07 Seguridad | AC-02, AC-04, AC-08 |
| RNF-13 Observabilidad | AC-15 |
| CU-08 2a, 4b · CU-09 1a · CU-10 1a · CU-13 | AC-02, AC-09, AC-11, AC-13, AC-14 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-09 | Versión inicial aprobada (PR #46). | CP-1 del bloque 4. Aprobada por la persona. |
| 1.1 | 2026-11-09 | AC-09: ventana de búsqueda limitada por la distancia que el autobús ha podido recorrer (`20 m/s × Δt + 50 m`) y, sin progreso anterior, tramo más temprano entre los casi mínimos; verificación con los trazados reales y ruido. CU-08 4b alineado (trazado del viaje elegido). | CP-3 de `driver_session` (P-01): con la ventana fija de 3 km, el ruido GPS hacía saltar el progreso a la pasada posterior en 56–91 de 94 trazados reales. Aprobada por la persona (PR #50). |
| 1.2 | 2026-11-09 | AC-09 y AC-10 en metros reales (las distancias de `shape_dist_traveled` no son metros); umbral del test con trazados reales y ruido σ 10 m: 150 m (máximo observado: 108 m por delante y 139 m por detrás). | CP-3 de `driver_session` en T-08: P-02 y P-03. Pendiente de aprobación. |
