# Caducidad de las solicitudes de parada — requirements

> Feature: `alert_expiry` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-21, RF-28 (pasajero), RNF-06, RNF-08 · Casos de uso: CU-07 · Depende de: alert_create

## Contexto

Una solicitud de parada no debe quedarse viva cuando ya no sirve (CU-07, RF-21). Caduca:

1. **`PASSED`** — cuando el autobús elegido **ha pasado** por la parada. Se detecta solo con el
   SAE (D12): el aviso sigue a su viaje GTFS (ADR-016) en las llegadas en tiempo real de la parada;
   si el viaje deja de aparecer y en la última observación llegaba en muy poco tiempo, ha pasado.
2. **`NEXT_STOP`** — cuando, según el horario del viaje y su último retraso observado, el
   autobús ya debería haber llegado a la **parada siguiente** y no se le ha visto en la última
   observación en tiempo real. Cubre los casos en que el SAE falla o el paso no se ve.
3. **`TIMEOUT`** — en todo caso, a los **30 min** de crearse (D9).

Al caducar, el aviso se **borra** con sus necesidades (RNF-06) y el pasajero recibe
`alert.expired` con el motivo.

El emparejamiento de viajes puede cambiar de viaje entre consultas (CP-3 de
`position_estimation`), así que la detección prefiere **caducar tarde a caducar antes de tiempo**:
un autobús que desaparece cuando aún estaba lejos no se da por pasado (LIM-02).

## Alcance

- Servicios de dominio `PassageDetector` y `ExpiryPolicy`.
- Tareas de fondo `PassageWatcher` (cada 15 s) y `AlertExpiryTicker` (cada 10 s).
- Método interno de `GetStopArrivals` para consultar una parada sin token.
- Evento `alert.expired` y notificación a la vista del conductor (vacía en el bloque 3).

## Fuera de alcance

- Detección de paso con el GPS del conductor (trabajo futuro, D12).
- Interfaz (`passenger_alert_ui`).

## Criterios de aceptación

### Detección de paso (`PASSED`)

- **alert_expiry.AC-01** — CUANDO llega una observación `REALTIME` de la parada y el viaje del
  aviso (`trip_id` y `service_date`) aparece en ella, EL SISTEMA DEBERÁ actualizar su
  seguimiento: `last_seen_at` = instante de la observación, `last_arrival_at` y `last_delay_s` de
  esa llegada.
  *Verificación:* unit
- **alert_expiry.AC-02** — CUANDO llega una observación `REALTIME` en la que el viaje del aviso
  **no** aparece, SI en su última observación (`last_seen_at`) llegaba en ≤ 2 min
  (`last_arrival_at − last_seen_at ≤ 2 min`, configurable), ENTONCES EL SISTEMA DEBERÁ caducar el
  aviso con motivo `PASSED`; SI llegaba en más tiempo o nunca se le vio en tiempo real, ENTONCES NO
  DEBERÁ caducarlo por paso.
  *Verificación:* unit (tabla de casos, incluidos 0 min, 2 min, 3 min y nunca visto)
- **alert_expiry.AC-03** — LAS OBSERVACIONES `SCHEDULED` (SAE no disponible) NO DEBERÁN
  actualizar el seguimiento ni provocar `PASSED`.
  *Verificación:* unit + integration (fuente que falla)
- **alert_expiry.AC-04** — EN CADA ciclo del vigilante, EL SISTEMA DEBERÁ consultar las llegadas
  de cada parada con avisos activos **una sola vez**, a través de `GetStopArrivals` (misma caché
  del SAE), aunque la parada tenga varios avisos; las paradas sin avisos no se consultan.
  *Verificación:* integration (contador de peticiones de la fuente con varias paradas y avisos)

### Parada siguiente y tiempo máximo

- **alert_expiry.AC-05** — SI el viaje tiene una parada posterior a la del aviso, Y la última
  observación `REALTIME` de la parada no lo incluye (o no hay ninguna desde que se creó el aviso),
  Y `ahora ≥ hora programada en la parada siguiente + last_delay_s + 2 min` (margen configurable),
  ENTONCES EL SISTEMA DEBERÁ caducar el aviso con motivo `NEXT_STOP`. SI la parada del aviso es la
  última del viaje, ENTONCES no aplica.
  *Verificación:* unit (`FakeClock`; con y sin observación reciente; última parada)
- **alert_expiry.AC-06** — CUANDO `ahora ≥ expires_at` (`created_at` + 30 min), EL SISTEMA DEBERÁ
  caducar el aviso con motivo `TIMEOUT`.
  *Verificación:* unit
- **alert_expiry.AC-07** — SI en un mismo ciclo se cumplen varias condiciones, ENTONCES el motivo
  DEBERÁ ser el primero de `PASSED`, `NEXT_STOP`, `TIMEOUT`.
  *Verificación:* unit

### Efectos de la caducidad

- **alert_expiry.AC-08** — CUANDO un aviso caduca, EL SISTEMA DEBERÁ borrarlo (con sus
  necesidades), publicar `{"type": "alert.expired", "alert_id": …, "reason": …}` en el canal de su
  dispositivo, llamar a `DriverViewNotifier.alert_removed` si estaba `DELIVERED` y registrar
  `alert.expired` con `alert_id`, `stop_id`, `line` y `reason`. SI el aviso ya no existía
  (cancelado en paralelo), ENTONCES no DEBERÁ publicar nada.
  *Verificación:* unit + integration (evento por `/ws/passenger`; fila borrada)
- **alert_expiry.AC-09** — EL SEGUIMIENTO DEBERÁ guardarse en la base de datos, de modo que tras
  un reinicio la detección continúa con la última observación.
  *Verificación:* integration

### Tareas de fondo

- **alert_expiry.AC-10** — `PassageWatcher` (cada 15 s) y `AlertExpiryTicker` (cada 10 s) DEBERÁN
  arrancar y parar con la aplicación, exponer `tick()` para los tests y usar el `Clock` inyectado;
  SI un ciclo lanza una excepción, ENTONCES DEBERÁN registrar `unhandled_exception` (solo el tipo)
  y seguir con el siguiente ciclo.
  *Verificación:* unit + integration (arranque y parada con el `lifespan`)
- **alert_expiry.AC-11** — CON la red de `gtfs_mini` y la reproducción de `stop_508_peak`, para
  avisos creados sobre los autobuses de la línea 93 en la parada 508 y el vigilante ejecutado cada
  20 s de la sesión: (a) NINGÚN aviso DEBERÁ caducar como `PASSED` mientras su viaje siga
  apareciendo en la observación siguiente con más de 2 min; (b) AL MENOS un aviso DEBERÁ caducar
  como `PASSED` en los dos ciclos siguientes a la última observación en que su viaje aparecía con
  ≤ 2 min. El test DEBERÁ informar de cuántos avisos caducan por cada motivo.
  *Verificación:* integration (sesión real; resultado contrastado con la exploración E-01)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-21 Caducidad (paso, parada siguiente, 30 min) | AC-01 … AC-07, AC-11 |
| RF-28 Actualización al caducar | AC-08 |
| RNF-06 Borrado de necesidades | AC-08 |
| RNF-08 Sin peticiones extra al SAE | AC-04 |
| D12 Paso solo con SAE | AC-02, AC-03 |
| LIM-02 Detección imperfecta | AC-02, AC-05, AC-11 |
| CU-07 flujos 1a, 1b | AC-05, AC-06 |
