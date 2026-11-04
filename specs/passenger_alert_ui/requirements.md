# Interfaz de la solicitud de parada — requirements

> Feature: `passenger_alert_ui` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-16, RF-17, RF-18, RF-19, RF-22, RF-23, RNF-02, RNF-03, RNF-04, RNF-05, RNF-06 · Casos de uso: CU-03, CU-04, CU-05, CU-07 · Depende de: passenger_stop_view, alert_create, alert_cancel, alert_expiry

## Contexto

Es la parte visible del bloque 3: el botón **"Solicitar"** de cada llegada (`docs/design.md` §5.3,
§7), el panel de confirmación con las necesidades, el estado de la solicitud y su cancelación, y
la página "Mis necesidades" (CU-05). Decisiones de la persona: la solicitud va **al autobús de esa
tarjeta** (no siempre al primero) y **siempre** hay un paso de confirmación, para evitar
solicitudes por toques accidentales que el conductor vería como reales. Así se cumple RNF-04
(≤ 2 interacciones: "Solicitar" y "Solicitar parada").

El estado llega por el WebSocket del pasajero (`realtime_events`): entregada al conductor (bloque
4), caducada (el autobús ha pasado, ha llegado a la parada siguiente o han pasado 30 min) o
cancelada desde otra pestaña. En el bloque 3 no hay conductores, así que la solicitud se muestra
"sin conductor conectado".

## Alcance

- Identificador anónimo del dispositivo y cliente HTTP con `X-Device-Id` para `POST`/`DELETE`.
- Botón "Solicitar" en las llegadas que lo admiten (`can_alert`).
- Panel de confirmación (diálogo modal) con necesidades precargadas del perfil.
- Estado de la solicitud en la tarjeta y aviso para solicitudes cuyo autobús ya no está en la
  lista; "Cancelar solicitud".
- Cliente WebSocket con reconexión y respaldo por consulta periódica.
- Anuncios para lectores de pantalla de los cambios de estado.
- Página "Mis necesidades" (perfil solo en el dispositivo).

## Fuera de alcance

- Notificaciones del sistema (Web Push) con la aplicación cerrada.
- Vista del conductor (bloque 4).

## Criterios de aceptación

### Dispositivo y perfil

- **passenger_alert_ui.AC-01** — CUANDO la aplicación necesita el identificador del dispositivo
  por primera vez, DEBERÁ generarlo con `crypto.randomUUID()` y guardarlo en el dispositivo
  (`avisabus.deviceId`); SI el almacenamiento no está disponible, ENTONCES DEBERÁ usarlo solo en
  memoria durante la sesión. El identificador DEBERÁ enviarse solo en la cabecera `X-Device-Id` y
  en el `hello` del WebSocket, nunca en la URL.
  *Verificación:* unit
- **passenger_alert_ui.AC-02** — LA PÁGINA "Mis necesidades" (`/necesidades`) DEBERÁ ofrecer
  cuatro casillas ("Necesito la rampa", "Necesito más tiempo para subir", "Necesito un asiento",
  "Tengo discapacidad visual"), un botón "Guardar" y otro "Borrar mis necesidades"; el perfil
  DEBERÁ guardarse solo en el dispositivo (`avisabus.needsProfile`) y anunciarse de forma educada
  "Necesidades guardadas" o "Necesidades borradas". LA PORTADA DEBERÁ enlazarla.
  *Verificación:* unit

### Solicitar

- **passenger_alert_ui.AC-03** — CUANDO una llegada tiene `can_alert = true` y el dispositivo no
  tiene una solicitud activa para esa parada y línea, LA TARJETA DEBERÁ mostrar el botón
  principal "Solicitar" con nombre accesible "Solicitar parada a la línea {línea} hacia
  {destino}" (destino hablado de `passenger_stop_view.AC-05`); con `can_alert = false` no DEBERÁ
  mostrarlo. SI hay una solicitud activa de esa línea en la parada para **otro** autobús,
  ENTONCES las demás tarjetas de la línea DEBERÁN mostrar, en lugar del botón, "Ya has solicitado
  otro autobús de esta línea".
  *Verificación:* unit
- **passenger_alert_ui.AC-04** — CUANDO se pulsa "Solicitar", LA VISTA DEBERÁ abrir un diálogo
  modal (`<dialog>` con `showModal`) titulado "Solicitar parada a la línea {línea} hacia
  {destino}" con: la hora de llegada, las cuatro casillas precargadas con el perfil, la casilla
  "Recordar mis necesidades en este dispositivo", el botón principal "Solicitar parada" y el
  secundario "Volver". El foco DEBERÁ ir al título al abrir, quedar dentro del diálogo, cerrarse
  con Escape o "Volver" y volver al botón "Solicitar" al cerrar sin solicitar.
  *Verificación:* unit + e2e (teclado)
- **passenger_alert_ui.AC-05** — CUANDO se pulsa "Solicitar parada", LA VISTA DEBERÁ enviar
  `POST /alerts` con el viaje de esa llegada y las necesidades marcadas (y, si se marcó
  "Recordar", guardar el perfil); mientras espera, el botón DEBERÁ quedar desactivado con el texto
  "Enviando…". CON `201` o `200`, DEBERÁ cerrar el diálogo, anunciar de forma educada "Parada
  solicitada para la línea {línea}" y mover el foco al botón "Cancelar solicitud" de esa tarjeta.
  *Verificación:* unit
- **passenger_alert_ui.AC-06** — SI la petición falla, ENTONCES el diálogo DEBERÁ seguir abierto
  y mostrar un mensaje con `role="alert"`, con el foco en él: `422` → "Este autobús ya no se puede
  solicitar." (y se refrescan las llegadas); `429` → "Has hecho demasiadas solicitudes. Inténtalo
  dentro de {N} minutos." (N a partir de `Retry-After`, redondeando hacia arriba); `404` → "La
  parada ya no está disponible. Vuelve a escanear el código QR."; red o `503` → "No se ha podido
  enviar la solicitud. Comprueba la conexión." con "Solicitar parada" disponible para reintentar.
  *Verificación:* unit

### Estado y cancelación

- **passenger_alert_ui.AC-07** — MIENTRAS haya una solicitud activa para un autobús que está en la
  lista, SU TARJETA DEBERÁ mostrar, en lugar de "Solicitar", el estado ("Parada solicitada. Aún
  no hay conductor conectado en esta línea." con `PENDING_DRIVER`; "El conductor ha recibido tu
  solicitud." con `DELIVERED`), las necesidades indicadas ("Has indicado: rampa y asiento") y el
  botón secundario "Cancelar solicitud".
  *Verificación:* unit
- **passenger_alert_ui.AC-08** — MIENTRAS haya una solicitud activa en esta parada cuyo autobús
  ya no aparece en la lista, LA VISTA DEBERÁ mostrar encima de las llegadas un aviso con su línea,
  destino, estado y "Cancelar solicitud".
  *Verificación:* unit
- **passenger_alert_ui.AC-09** — CUANDO se pulsa "Cancelar solicitud", LA VISTA DEBERÁ enviar
  `DELETE /alerts/{alert_id}` sin pedir confirmación; CON `204` o `404`, DEBERÁ quitar la
  solicitud, anunciar "Solicitud cancelada" (o "La solicitud ya no estaba activa" con `404`) y
  mover el foco al botón "Solicitar" de esa tarjeta o, si no existe, al `h2` "Próximas llegadas";
  CON error de red, DEBERÁ anunciar "No se ha podido cancelar la solicitud" y mantener el foco.
  *Verificación:* unit

### Tiempo real

- **passenger_alert_ui.AC-10** — MIENTRAS la vista de parada esté abierta, LA APLICACIÓN DEBERÁ
  mantener abierto `/ws/passenger`, enviar el `hello`, sustituir su estado con cada
  `alerts.snapshot` y aplicar los eventos; SI la conexión se cierra, ENTONCES DEBERÁ reconectar
  con esperas crecientes (1, 2, 4, 8, 16 y 30 s, con variación aleatoria de ±20 %), sin
  reconectar mientras no haya conexión de red, y MIENTRAS esté desconectada DEBERÁ consultar
  `GET /alerts/mine` cada 30 s.
  *Verificación:* unit (WebSocket simulado y temporizadores falsos)
- **passenger_alert_ui.AC-11** — CUANDO llega un evento, LA VISTA DEBERÁ anunciar de forma
  educada: `alert.delivered` → "El conductor de la línea {línea} ha recibido tu solicitud";
  `alert.expired` → "Tu solicitud de la línea {línea} ha terminado: " + "el autobús ha pasado por
  la parada" (`PASSED`), "el autobús ya ha llegado a la parada siguiente" (`NEXT_STOP`) o "han
  pasado 30 minutos" (`TIMEOUT`); y DEBERÁ actualizar el estado sin anunciar nada con
  `alert.registered`, `alert.cancelled` y `alerts.snapshot`. SI el foco estaba en un control de
  la solicitud que desaparece, ENTONCES DEBERÁ pasar al botón "Solicitar" de esa tarjeta o al
  `h2` "Próximas llegadas".
  *Verificación:* unit

### Calidad

- **passenger_alert_ui.AC-12** — LAS PRUEBAS E2E DEBERÁN cubrir, con la API y el WebSocket
  simulados (`page.route` y `page.routeWebSocket`, sin red): solicitar con necesidades,
  confirmación, evento de caducidad, cancelar, error `429` y la página "Mis necesidades", en los
  perfiles móvil y tablet, en castellano y en valenciano, y axe NO DEBERÁ reportar violaciones
  WCAG 2.1 A/AA (también con el diálogo abierto).
  *Verificación:* e2e
- **passenger_alert_ui.AC-13** — LA INTERFAZ DEBERÁ seguir `docs/design.md` (§5.3 fila de
  acciones, §5.5 botones, §5.8 diálogo y estado de la solicitud, §7 terminología).
  *Verificación:* revisión (capturas e2e) + manual (persona en CP-6)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-16 Crear desde la parada | AC-03, AC-04, AC-05 |
| RF-17 Necesidades | AC-02, AC-04 |
| RF-18 Perfil en el dispositivo | AC-02, AC-04, AC-05 |
| RF-19 Una por dispositivo, parada y línea | AC-03 |
| RF-22 Cancelar | AC-09 |
| RF-23 Confirmación / sin conductor | AC-07, AC-11 |
| RNF-02 Confirmación ≤ 5 s | AC-10 |
| RNF-03 Accesibilidad | AC-03, AC-04, AC-05, AC-06, AC-09, AC-11, AC-12, AC-13 |
| RNF-04 ≤ 2 interacciones | AC-04, AC-05 |
| RNF-05 Compatibilidad | AC-12 |
| RNF-06 Privacidad | AC-01, AC-02 |
| CU-05 Perfil | AC-02 |
| CU-07 Caducidad | AC-11 |
