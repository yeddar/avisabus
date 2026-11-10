# Revisión: driver_ui
Ciclo: 1 · Fecha: 2026-11-10 · Agente: reviewer · Commit revisado: 74a93c1 (base `origin/feat/driver_demand`)

## Veredicto: CHANGES_REQUESTED

Dos hallazgos bloqueantes de código (B-01, B-02) y un problema de spec que necesita decisión de la
persona (P-01 → CP-3). El protocolo con el backend real, i18n, privacidad y alcance están bien.

## Matriz AC → evidencia

Tests en `frontend/src/features/driver/__tests__/` salvo `e2e/driver.spec.ts`. Todos se han leído.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `LoginPage.test.tsx:40,51,59,77,89,107`; `session.test.ts:23,36,52` | OK | Atributos, agrupado, `sessionStorage`, 401 con foco, 429 con `Retry-After`. |
| AC-02 | `ServicePicker.test.tsx:58,67,80,98,114,144`; `ShiftPage.test.tsx:65,97` | OK | Incluye cuerpo real del `PUT` y refresco tras 409. |
| AC-03 | `ShiftPage.test.tsx:48,56,77,148`; `session.test.ts:62,75`; `useDriverSocket.test.tsx:201`; `useDriverPosition.test.tsx:182` | OK | |
| AC-04 | `useDriverPosition.test.tsx:98,116,138,153,173,192,216`; `DemandView.test.tsx:163`; `DriverStatus.test.tsx:82` | **NO CUMPLE** | B-01: la posición se corta con el turno abierto. P-01: el test de la línea 138 fija un comportamiento contrario al texto del AC. |
| AC-05 | `DemandView.test.tsx:59,69,80,108,121`; `ShiftPage.test.tsx:88` | OK | Ver N-02. |
| AC-06 | `CapacityBanner.test.tsx:13-74`; `DemandView.test.tsx:131,140` | OK | Anuncio por la región `role="alert"` del `Announcer`, válido (ver interpretaciones). |
| AC-07 | `newAlerts.test.ts`; `tone.test.ts`; `DemandView.tone.test.tsx`; `useDriverSocket.test.tsx:92` | OK | Sin comprobar en dispositivo real: N-03. |
| AC-08 | `DriverStatus.test.tsx:39-95`; `DemandView.test.tsx:146,155`; `ServicePicker.test.tsx:159`; `ShiftPage.test.tsx:117` | OK | |
| AC-09 | `useDriverSocket.test.tsx:56,65,77,110,136,152,172,215` | OK | Con la salvedad de B-01 tras "Elegir la siguiente salida". Ver N-04. |
| AC-10 | `DemandView.test.tsx:169,185,195`; `EndShiftDialog.test.tsx`; `LoginPage.test.tsx:101`; `ShiftPage.test.tsx:133`; `useDriverSocket.test.tsx:188` | OK | Comportamiento correcto; el foco al cerrar es B-02. |
| AC-11 | `e2e/driver.spec.ts:235,341` | OK | Flujo completo, es y ca, tablet, sin peticiones externas. Ver N-08. |
| AC-12 | Capturas de `e2e/driver.spec.ts` (14 ficheros en `frontend/test-results/driver_ui/tablet-landscape/`) | OK con reserva | Coinciden con `docs/design.md` §5.9 salvo el estado en la cabecera (P-02). Persona en CP-6. |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e`, puerto 4173 libre: salida 0.

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 1846 passed, 12 deselected |
| frontend: format, lint, types | OK |
| frontend: tests | 651 passed, 2 skipped (68 ficheros) |
| frontend: build + bundle | OK (5 tests) |
| frontend: e2e + a11y | 130 passed, 8 skipped (perfiles no tablet) |
| harness: `feature_list.json`, trazabilidad | OK |

Comprobación adicional en navegador real (Playwright sobre `dist/`, API y WebSocket simulados, script
fuera del repo):

| Comprobación | Chromium | WebKit |
|---|---|---|
| Foco tras "Seguir" | `BODY` | `BODY` |
| Foco tras Escape | "Finalizar turno" | `MAIN` |
| `PUT position` con posición nueva en la vista de demanda (control) | 1 | 0 (no concluyente: en WebKit `setGeolocation` no emitió posición nueva) |
| `PUT position` en 12 s y 2 posiciones nuevas, en el selector tras fin de recorrido | 0 | 0 (no concluyente) |
| `/ws/driver` abierto en ese selector | No | No |

## Hallazgos

### Bloqueantes

**B-01 · La posición, el `wakeLock` y el socket se cortan con el turno abierto tras "Fin del recorrido".**
`frontend/src/features/driver/ShiftPage.tsx:94-102`, `frontend/src/features/driver/DemandView.tsx:53`.
Incumple **AC-04** ("MIENTRAS haya turno abierto"); afecta también a **AC-09** ("MIENTRAS haya salida
elegida": la salida sigue guardada en el servidor hasta el siguiente `PUT …/service`).
- "Elegir la siguiente salida" pasa a la fase `picker` y desmonta `DemandView`, que es donde viven
  `useDriverPosition(true)` y `useDriverSocket`. Comprobado en Chromium: 0 envíos y socket cerrado.
- Consecuencia real: el selector ofrece salidas hasta 60 min vista, así que esperar en cabecera es
  normal. A los 10 min sin posición el servidor cierra el turno con `IDLE`
  (`backend/src/avisabus/application/reap_driver_sessions.py:55-57`). Sin socket no llega
  `session.closed`: el conductor solo ve un 401 al elegir salida y vuelve a `/driver` sin motivo
  (AC-10). Además se libera el `wakeLock` y la pantalla puede apagarse.
- La interpretación del implementer se apoya en CU-08 (paso 4 tras elegir salida). Vale para la
  **primera** elección, pero no para este caso, en el que CU-08 ya se ha cumplido. La firma
  `useDriverPosition(enabled)` de design §2 apunta a un control por encima de la vista; hoy siempre
  recibe `true`.
- Corrección esperada: mantener posición, `wakeLock` y socket mientras haya salida elegida, también en
  el selector tras fin de recorrido, con un test que lo cite (AC-04, AC-09).

**B-02 · "Seguir" pierde el foco al cerrar el diálogo.**
`frontend/src/features/driver/EndShiftDialog.tsx:41`, `frontend/src/features/driver/DemandView.tsx:197`.
Incumple **RNF-03** (WCAG 2.1 AA, 2.4.3 Orden del foco) y AGENTS.md §6.
- "Seguir" llama a `onCancel`, que desmonta el `<dialog>` sin `close()`, así que el navegador no
  devuelve el foco. Reproducido en Chromium y WebKit: el foco queda en `BODY`. Con Escape en Chromium
  sí vuelve a "Finalizar turno".
- `frontend/src/features/passenger/alerts/RequestDialog.tsx:169` ya resuelve esto con
  `dialog.current?.close()`. axe no lo detecta y ningún test lo cubre.
- Corrección esperada: cerrar con `close()` como en `RequestDialog` y añadir un e2e que compruebe que
  el foco vuelve a "Finalizar turno".

### Problemas de spec

**P-01 · CP-3 · "Enviar la última cada 5 s" contradice la detección de GPS perdido.** Bloquea el cierre
de la feature hasta que decida la persona; el implementer no puede resolverlo solo.
- AC-04 dice "enviar la última cada 5 s"; `useDriverPosition.ts:47` envía cada posición una sola vez
  y `useDriverPosition.test.tsx:138` lo fija citando AC-04.
- El motivo del implementer es cierto: `STALE` se calcula con `last_position_at`
  (`backend/src/avisabus/application/driver_sessions.py:381`), y cada envío lo renueva aunque se repita
  `recorded_at` (`:477`). Reenviar literalmente ocultaría `STALE` (CU-09 1a, AC-08).
- Sin reenvío, si la tablet no emite posiciones con el autobús parado, aparece un `STALE` falso a los
  30 s y el turno se cierra a los 10 min (CU-10 1a está pensado para cerrar la vista, no para esto).
- Debió pararse como CP-3 (AGENTS.md §2) en lugar de anotarse y seguir.
- Propuestas:
  - **A (recomendada):** enviar cada 5 s la última posición, también repetida, y calcular `STALE` con
    la antigüedad de `recorded_at`, que es lo que dice `driver_session.AC-11` ("si la última tiene más
    de 30 s"). `last_position_at` sigue sirviendo al cierre por inactividad. Toca el backend de
    `driver_session`.
  - **B:** reescribir AC-04 como "cada 5 s, si hay una posición nueva", mantener el código actual y
    comprobar en CP-6 qué hace una tablet real parada.

**P-02 · No bloqueante.** §5.9 pide "estado (GPS, conexión)" en la cabecera, pero ni AC-08 ni design §3
dan texto para el estado correcto. La cabecera no lo muestra (`DemandView.tsx:143-149`) y añadirlo
obligaría a inventar texto. Propuesta: decidir en CP-6 y ajustar §5.9 o la spec.

**P-03 · No bloqueante.** Plurales fijos en design §3: salen "Esperan 1 personas y quedan 0 plazas" y
"1 plazas libres · 1 asientos". Propuesta: añadir `_one` a `driver.capacity`, `driver.seats` y
`driver.places`.

**P-04 · No bloqueante.** Textos sin definir en la spec: lista de salidas vacía (`driver.pick.empty`) y
errores de red o 5xx. La reutilización de `stop.error.body` es razonable. Propuesta: añadirlos a design §3.

### Interpretaciones de `progress/impl_driver_ui.md`

| Interpretación | Juicio |
|---|---|
| `driverApi` devuelve todo salvo 401; exporta `subscribeDriverAuthLost` y `loseDriverAuth` | Válida: es aditiva y necesaria con la firma fijada. |
| Posición solo en la vista de demanda | Válida para la primera elección (CU-08). **No válida** tras fin de recorrido: B-01. |
| "Volver" en el paso de línea va a `/driver` | Aceptable: AC-02 pide "Volver" en cada paso. |
| Estados y franjas a la vez | Válida: `docs/design.md` §1 da prioridad a la spec en comportamiento y AC-06 no condiciona. Conviene aclarar "en lugar de" en §5.9. |
| Cabecera sin indicador | Hueco de spec: P-02. |
| Texto "N personas esperando"; distancia y necesidades en paradas 4 y 5 | Válida: design §3 y AC-05. |
| Franjas anunciadas por el `Announcer` | Válida: `frontend_i18n.AC-12` prohíbe regiones propias, y la región es `role="alert"`. |
| Claves con punto dentro de `driver` | Válida: los nombres son los de la spec y se resuelven (tests y e2e). |
| 429 sin `Retry-After` → 15 min | Válida como respaldo; el backend siempre envía la cabecera. |
| `DELETE` fallido: se borra el token igualmente | Válida: AC-10 no condiciona. |
| Cada posición se envía una vez | Contradicción de spec: P-01. |

### Protocolo y API frente al backend real

Sin discrepancias en: `hello`, mensaje `driver.view` plano (`Event.message()`), `ping`/`pong` (el
servidor ignora el `pong`), `session.closed` con sus 4 motivos, cierre `4401`, cuerpos y códigos de
`POST /sessions` (201/401/429), `lines`, `departures`, `PUT service` (200/409/422), `PUT position` (204),
`GET view` y `DELETE current`. Las fixtures e2e tienen la forma real de los esquemas.

### Lista de comprobación (§4)

- **Arquitectura:** sin cambios de backend. Convención: N-05.
- **Tests:** sin red y con temporizadores falsos; no tautológicos.
- **Privacidad:** correcta. Token solo en `sessionStorage`, cabecera `Authorization` y mensaje `hello`;
  nunca en URL. Código solo en el cuerpo del `POST`. Sin `console.*` en la feature. `localStorage` solo
  guarda `avisabus.driverMute`. El service worker no cachea `/api` ni `/ws`.
- **i18n:** paridad completa `es` / `ca-valencia` en las claves `driver.*`. Valenciano sin revisión
  humana: pendiente de CP-6.
- **Accesibilidad:** axe sin violaciones, objetivos ≥ 44 px, icono y texto en estados y necesidades,
  foco en errores y cambios de paso. Excepción: B-02.
- **Alcance:** solo `features/driver`, `routes.tsx`, locales, e2e y progreso. Sin variables nuevas.
  Commits conformes.

### No bloqueantes

- **N-01** `DemandView.tsx:74-81`: una vista en vivo con `service: null` (la salida desaparece al cambiar
  el feed, `build_driver_view.py:77-80`) no lleva al selector; solo queda "Finalizar turno" (AC-02).
- **N-02** `DemandView.tsx:167,175` y `newAlerts.ts:21`: clave y resalte por `stop_id`. Una parada que
  aparece dos veces en el viaje duplica la clave y se resaltaría dos veces; conviene `stop_sequence`
  (`driver_demand.AC-05` distingue la aparición).
- **N-03** `tone.ts:21-22`: el `AudioContext` se crea fuera de un gesto. Tras recargar, o en Safari/iPadOS,
  puede quedar suspendido y no sonar. Conviene desbloquearlo en la primera pulsación y probarlo en CP-6.
- **N-04** `useDriverSocket.ts:140`: al volver la red, `socketStatus` conserva `connected` hasta que
  el socket nuevo se resuelve; se oculta "Sin conexión" y se para la consulta durante ese intervalo.
- **N-05** `DemandView.tsx:8-9`, `StopCard.tsx:5`, `ServicePicker.tsx:13`: importan de `features/passenger`.
  `docs/conventions.md` §4 lleva lo compartido a `shared/`; moverlo requiere una tarea.
- **N-06** `ServicePicker.tsx:141`: un fallo de carga no ofrece "Reintentar"; en el paso de línea, "Volver"
  saca a `/driver`.
- **N-07** `ShiftPage.tsx:60-79`: las fases `loading` y `failed` no tienen `h1` (`docs/conventions.md` §4).
- **N-08** `e2e/driver.spec.ts:326-332`: axe no se ejecuta con el diálogo abierto ni con el GPS desactualizado.
- **N-09** `frontend/src/shared/device/storage.ts:2`: el comentario "The only keys" no incluye
  `avisabus.driverMute`.
