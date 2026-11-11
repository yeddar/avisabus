# Interfaz del conductor — requirements

> Feature: `driver_ui` · Versión: 1.2 · Estado: APPROVED
> Requisitos: RF-24, RF-25, RF-26, RF-27, RF-28, RF-29, RF-30, RF-31, RNF-03, RNF-05 · Casos de uso: CU-08, CU-09, CU-10 · Depende de: frontend_i18n, driver_demand

## Contexto

La vista del conductor corre en una **tablet en horizontal** fijada en el puesto de conducción.
Se mira de reojo con el autobús en marcha: números grandes, pocas palabras, nada que leer
despacio. Cuando llega una solicitud nueva suena **un tono breve** y su parada se resalta unos
segundos (decisión de la persona); el conductor puede silenciar el tono.

El flujo: código de acceso → línea, sentido y salida → vista de demanda → finalizar turno. La
posición sale del GPS de la tablet (`watchPosition`) o del simulador (`driver_gps_simulator`).

## Alcance

- Rutas `/driver` (código) y `/driver/shift` (elección de salida y vista de demanda).
- Envío periódico de la posición, `Wake Lock` de pantalla y estados de GPS.
- Cliente de `/ws/driver` con reconexión y respaldo por consulta.
- Tono, resalte, silencio y alertas de capacidad y de asientos.
- Finalizar turno y cierre por el servidor.

## Fuera de alcance

- Navegación, mapa o indicaciones de ruta para el conductor.
- Gestión de códigos (CLI).

## Criterios de aceptación

### Acceso y salida

- **driver_ui.AC-01** — LA RUTA `/driver` DEBERÁ pedir el código en un campo numérico (8 dígitos,
  `inputmode="numeric"`, `autocomplete="one-time-code"`, agrupado "1234 5678" al escribir) con
  etiqueta visible y botón "Entrar"; CON `201`, DEBERÁ guardar el token solo en `sessionStorage`
  (`avisabus.driverSession`) e ir a `/driver/shift`; CON `401`, "Código no válido" (con foco en el
  mensaje); CON `429`, "Demasiados intentos. Inténtalo dentro de {N} minutos.".
  *Verificación:* unit
- **driver_ui.AC-02** — SIN salida elegida, `/driver/shift` DEBERÁ mostrar en tres pasos línea
  (botones con el color de línea accesible), sentido (dos botones con su `headsign`) y salida
  (lista de `GET /driver/departures` con hora, primera parada y destino; las `taken` desactivadas
  con "Ya en servicio"), con "Volver" en cada paso; al elegir la salida DEBERÁ llamar a
  `PUT …/service` y mostrar la vista de demanda; CON `409`, DEBERÁ refrescar la lista y anunciar
  "Esa salida ya la lleva otro conductor". (v1.2) SIN salidas en la ventana, DEBERÁ mostrar "No
  hay salidas de esta línea y sentido en la próxima hora" con "Volver" y "Actualizar"; CON error
  de red o `5xx` en cualquier paso, "No se han podido cargar los datos" con "Reintentar".
  *Verificación:* unit
- **driver_ui.AC-03** — SIN token válido (ausente o `401` en cualquier llamada), las rutas del
  conductor DEBERÁN volver a `/driver`.
  *Verificación:* unit

### Posición

- **driver_ui.AC-04** — MIENTRAS haya turno abierto (también en la elección de salida, v1.1), LA
  VISTA DEBERÁ seguir la posición con `watchPosition` (alta precisión) y enviar cada 5 s la
  última disponible (`PUT …/position`), **aunque se repita**, porque el reenvío es la señal de
  vida del turno (`driver_session.AC-08` v1.3); (v1.1) SI `watchPosition` no entrega ninguna
  posición en 10 s, ENTONCES DEBERÁ pedir una con `getCurrentPosition` (`maximumAge: 0`,
  `timeout: 10 s`), para que un autobús parado siga dando fijos nuevos y solo un GPS perdido
  acabe en "Posición desactualizada"; SI el permiso
  se deniega, ENTONCES DEBERÁ mostrar "Sin permiso de ubicación: no se pueden calcular las
  próximas paradas" con "Reintentar" (CU-08 4a). DEBERÁ pedir `navigator.wakeLock` de pantalla
  (y volver a pedirlo al recuperar la visibilidad), sin error si no está disponible.
  *Verificación:* unit (geolocalización y `wakeLock` simulados, temporizadores falsos)

### Vista de demanda

- **driver_ui.AC-05** — LA VISTA DEBERÁ mostrar la línea y el destino de la salida y, con la
  vista recibida, las 3 primeras próximas paradas en tarjetas grandes y las 2 siguientes en
  pequeño, cada una con nombre, distancia, el número de personas esperando a este autobús en
  grande y las necesidades con icono y texto ("1 rampa", "1 asiento", "1 más tiempo", "1 visión";
  v1.2: todos los textos con número usan el plural correcto en los dos idiomas, p. ej. "Espera 1
  persona" / "Esperan 2 personas");
  SI no hay nadie esperando en ninguna, ENTONCES "Sin solicitudes en las próximas paradas"
  (CU-09 2b).
  *Verificación:* unit
- **driver_ui.AC-06** — LA VISTA DEBERÁ mostrar las plazas libres ("30 plazas libres · 4
  asientos"; "Ocupación no disponible" sin dato) y, SI `capacity_alert`, una franja destacada
  "Esperan {n} personas y quedan {m} plazas" con icono, texto y color (`occ-full`); SI
  `seat_alert`, una franja "Piden asiento {n} personas y quedan {m} asientos". Las franjas se
  anuncian una vez al aparecer (`role="alert"`).
  *Verificación:* unit
- **driver_ui.AC-07** — CUANDO llega una vista con un `alert_id` que este turno no había visto,
  LA VISTA DEBERÁ reproducir un tono breve (≤ 0,5 s, generado con Web Audio, sin ficheros) salvo
  que esté silenciado, y resaltar esa parada con la etiqueta "Nueva" durante 10 s. La primera
  vista tras entrar o reconectar marca sus solicitudes como vistas sin tono. EL BOTÓN "Silenciar
  tono" / "Activar tono" DEBERÁ recordar la elección en el dispositivo (`avisabus.driverMute`).
  *Verificación:* unit (`AudioContext` simulado)
- **driver_ui.AC-08** — (v1.2) EL ESTADO de la cabecera (GPS y conexión) DEBERÁ llevar texto
  corto visible además del icono ("GPS correcto", "GPS desactualizado", "Conectado", "Sin
  conexión"). LA VISTA DEBERÁ indicar con texto y icono: `gps = WAITING` "Esperando
  ubicación…", `STALE` "Posición desactualizada" (manteniendo la última lista, CU-09 1a),
  `off_route` "No estás en el recorrido de esta línea" (CU-08 4b), sin conexión con el servidor
  "Sin conexión, reconectando…" (CU-09 4a) y `finished` "Fin del recorrido" con el botón "Elegir
  la siguiente salida" (vuelve al paso de salida con la misma línea y sentido). (v1.1) Elegir la
  siguiente salida NO DEBERÁ interrumpir el envío de posición, el `wakeLock` ni `/ws/driver`: el
  turno sigue abierto mientras el conductor espera en cabecera.
  *Verificación:* unit

### Tiempo real y fin

- **driver_ui.AC-09** — MIENTRAS haya turno abierto (v1.1: también en la elección de salida, con
  `service = null`), LA VISTA DEBERÁ mantener `/ws/driver` con
  `hello` y reconexión como `passenger_alert_ui.AC-10`, y MIENTRAS esté desconectada DEBERÁ pedir
  `GET …/view` cada 10 s.
  *Verificación:* unit (WebSocket simulado)
- **driver_ui.AC-10** — CUANDO se pulsa "Finalizar turno", LA VISTA DEBERÁ pedir confirmación en
  un diálogo ("¿Finalizar el turno?", "Finalizar" / "Seguir"); (v1.1) con "Seguir" o Escape, el
  diálogo se cierra y el foco DEBERÁ volver al botón "Finalizar turno"; al confirmar DEBERÁ llamar a
  `DELETE …/current`, borrar el token y volver a `/driver` con el mensaje "Turno finalizado".
  CUANDO llega `session.closed`, DEBERÁ hacer lo mismo con el motivo ("Turno cerrado por
  inactividad", "Código revocado", "Has iniciado otro turno con este código").
  *Verificación:* unit

### Calidad

- **driver_ui.AC-11** — LAS PRUEBAS E2E DEBERÁN cubrir, con API, WebSocket y geolocalización
  simulados (sin red), el flujo completo (código, salida, vista, solicitud nueva con resalte,
  alerta de capacidad, fin) en el perfil tablet horizontal, en castellano y valenciano, sin
  violaciones de axe WCAG 2.1 A/AA.
  *Verificación:* e2e
- **driver_ui.AC-12** — LA INTERFAZ DEBERÁ seguir `docs/design.md` §5.9.
  *Verificación:* revisión (capturas e2e) + manual (persona en CP-6)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-24 Código | AC-01, AC-03 |
| RF-25 Línea, sentido y salida | AC-02 |
| RF-26 Posición GPS | AC-04, AC-08 |
| RF-27 ≥ 3 paradas con necesidades | AC-05 |
| RF-28 Tiempo real | AC-07, AC-09 |
| RF-29 Alerta de capacidad | AC-06 |
| RF-30 Finalizar turno | AC-10 |
| RF-31 Idiomas | AC-11 |
| RNF-03 Accesibilidad | AC-01, AC-05, AC-06, AC-08, AC-11, AC-12 |
| RNF-05 Tablet | AC-11 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-09 | Versión inicial aprobada (PR #46). | CP-1 del bloque 4. Aprobada por la persona. |
| 1.1 | 2026-11-11 | AC-04: reenvío cada 5 s como señal de vida y `getCurrentPosition` si `watchPosition` calla 10 s; AC-08/AC-09: elegir la siguiente salida no corta posición, `wakeLock` ni socket; AC-10: foco a "Finalizar turno" al pulsar "Seguir". | CP-3 de `driver_ui` (P-01, decisión de la persona) y B-01/B-02 de la revisión del ciclo 1. Aprobada por la persona (PR #55). |
| 1.2 | 2026-11-11 | AC-02: textos sin salidas y de error; AC-05/AC-06: plurales correctos; AC-08: estado de la cabecera con texto visible. T-08. | P-02, P-03 y P-04 de la revisión de `driver_ui` (cierre del bloque 4). Aprobada por la persona (PR #60). |
