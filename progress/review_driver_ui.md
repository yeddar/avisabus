# Revisión: driver_ui
Ciclo: 2 · Fecha: 2026-11-11 · Agente: reviewer · Commit revisado: eeb1f12 (spec v1.1; base `origin/feat/driver_session` v1.3, a7634a9, ya fusionada)

## Veredicto: APPROVED

B-01, B-02 y P-01 (ciclo 1) están resueltos, en tests y en navegador real, también contra el backend
real de la v1.3. Sin hallazgos bloqueantes ni regresiones. Queda un problema de spec nuevo, P-05, que
no bloquea: CU-08 pide la ubicación después de elegir la salida y la v1.1 la pide antes. Lo decide la
persona (CP-4). Siguen abiertos los no bloqueantes P-02 a P-04 y N-01 a N-09. Hay dos nuevos, N-10 y
N-11.

## Matriz AC → evidencia

Tests en `frontend/src/features/driver/__tests__/` salvo los de `e2e/driver.spec.ts`. Todos se han leído.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `LoginPage.test.tsx:40,51,59,77,89,107`; `session.test.ts:23,36,52` | OK | Sin cambios desde el ciclo 1. |
| AC-02 | `ServicePicker.test.tsx:58,67,80,98,114,144`; `ShiftPage.test.tsx:66,98` | OK | |
| AC-03 | `ShiftPage.test.tsx:49,57,78,232`; `session.test.ts:62,75`; `useDriverSocket.test.tsx:201`; `useDriverPosition.test.tsx:285` | OK | |
| AC-04 | `useDriverPosition.test.tsx:117,135,157,181,190,220,232,246,266,276,295,319`; `ShiftPage.test.tsx:134,153`; `DriverStatus.test.tsx:82`; `e2e/driver.spec.ts:240` (tramo `:328-338`) | OK | v1.1 cubierta: el reenvío repetido cada 5 s (`:157`), `getCurrentPosition` con las opciones exactas a los 10 s y repetido mientras dure el silencio (`:190`), nada mientras `watchPosition` entrega (`:220`), parada con permiso denegado (`:266`), el selector de la primera salida (`ShiftPage:134`) y el de la siguiente (`ShiftPage:153`). Comprobado con el backend real (ver abajo). P-05 sobre el orden del permiso. |
| AC-05 | `DemandView.test.tsx:64,74,85,113,126`; `ShiftPage.test.tsx:89` | OK | N-02 sigue abierto. |
| AC-06 | `CapacityBanner.test.tsx:13,20,32,40,58,74`; `DemandView.test.tsx:136,145` | OK | |
| AC-07 | `newAlerts.test.ts:14,21,31`; `tone.test.ts:68,79,91`; `DemandView.tone.test.tsx:79-174` (incluye `:136`, primera vista pedida al elegir salida, sin tono); `useDriverSocket.test.tsx:92` | OK | N-03 y N-10. |
| AC-08 | `DriverStatus.test.tsx:39,45,64,70,76,95`; `DemandView.test.tsx:151,160`; `ServicePicker.test.tsx:159`; `ShiftPage.test.tsx:118,153` | OK | `ShiftPage:153` fija la parte v1.1: `clearWatch` y `release` no se llaman, el socket es el mismo y las vistas de la salida anterior se descartan. |
| AC-09 | `useDriverSocket.test.tsx:56,65,77,110,136,152,172,215,232`; `ShiftPage.test.tsx:134,153`; `DemandView.tone.test.tsx:136`; `e2e/driver.spec.ts:240` (`hellos === 1` tras la siguiente salida) | OK | N-04 sigue abierto. |
| AC-10 | `DemandView.test.tsx:168,184,196`; `EndShiftDialog.test.tsx:8,17,28`; `LoginPage.test.tsx:101`; `ShiftPage.test.tsx:217`; `useDriverSocket.test.tsx:188`; `e2e/driver.spec.ts:358` | OK | B-02 resuelto: la parte v1.1 (foco con "Seguir" y con Escape) se comprueba en jsdom y en el e2e tablet (WebKit), y yo la he comprobado en Chromium y WebKit. |
| AC-11 | `e2e/driver.spec.ts:240,389` (es y ca, `tablet-landscape`) | OK | Sin peticiones externas (`external`, `unexpected`). N-08 sigue abierto. |
| AC-12 | 14 capturas en `frontend/test-results/driver_ui/tablet-landscape/` | OK con reserva | Revisadas `solicitud-nueva-es`, `eleccion-salida-ca`, `gps-desactualizado-es` y `fin-recorrido-ca` contra §5.9: sin cambios de maquetación respecto al ciclo 1. La reserva es la misma: P-02 (estado en la cabecera). Valida la persona en CP-6. |

### Comprobación de los hallazgos del ciclo 1

| Hallazgo | Estado | Evidencia |
|---|---|---|
| **B-01** Posición, `wakeLock` y socket cortados tras "Fin del recorrido" | **Resuelto** | `ShiftPage.tsx:47-51` mantiene `useDriverShift` activo en las fases `picker` y `demand`. `DemandView` ya no abre hooks propios. Tests: `ShiftPage.test.tsx:153` y el e2e `:328-338`. Lo he visto en el navegador contra el backend real: un único socket durante todo el turno y `PUT position` = 204 en el selector. |
| **B-02** Foco perdido con "Seguir" | **Resuelto** | `EndShiftDialog.tsx:43` cierra con `close()` y `DemandView.tsx:157-160` enfoca "Finalizar turno". En navegador: "Seguir" lleva el foco a `BUTTON: Finalizar turno` y Escape también, en Chromium y en WebKit. En el ciclo 1 se quedaba en `BODY`/`MAIN`. Shift+Tab sigue el orden normal. |
| **P-01** (CP-3) Reenvío frente a `STALE` | **Resuelto en spec** (v1.1 + `driver_session` v1.3) y **cumplido** | `useDriverPosition.ts:75-85` reenvía cada 5 s. `:58-74` pide `getCurrentPosition` tras 10 s de silencio. El backend separa `last_seen_at` (señal de vida, cierre por `IDLE`) de `last_fix_at` (`STALE`) (`driver_sessions.py:380-383,478-487`; `reap_driver_sessions.py:56`). |

### Decisiones del ciclo 1 en `progress/impl_driver_ui.md`

| Decisión | Juicio |
|---|---|
| Fichero nuevo `useDriverShift.ts`, fuera de design §1 | **Válida.** Design §2 dice "El hook vive en ShiftPage", y `useDriverShift` es solo una composición de `useDriverPosition` y `useDriverSocket` que llama `ShiftPage`. Pasa lo mismo que con `DriverLayout.tsx`, `types.ts` e `icons/`, aceptados en el ciclo 1. No cambia ningún contrato. Hay que añadirlo a la lista en la próxima versión de la spec (N-11). |
| Posición y socket desde el primer selector, con el permiso pedido antes de lo que dice CU-08 | **Válida frente a la spec**: AC-04 v1.1 ("también en la elección de salida") y AC-09 v1.1 ("con `service = null`", que solo se da antes de la primera salida) la piden de forma explícita. **Contradice el orden de `docs/use_cases.md` CU-08**, donde el permiso es el paso 4, después de elegir salida en el paso 3. Ver P-05: lo decide la persona. |
| El aviso de permiso denegado solo aparece en la vista de demanda | **Aceptable**, pero entra en P-05. Lo he comprobado en el navegador: si se deniega en el selector, no se muestra nada. En la vista de demanda sale "Sin permiso de ubicación…" con "Reintentar", y "Reintentar" funciona: el aviso desaparece y se envía la posición. AC-02 fija el contenido del selector y el texto de AC-04 habla de "próximas paradas", que solo existen en la vista. Aun así, CU-08 4a pide que se indique. |
| Retirada de dos tests de `DemandView.test.tsx` | **Válida.** "follows the position while the view is open" ya no es de la vista, y lo cubren `ShiftPage.test.tsx:134,153` y `useDriverPosition.test.tsx:117`. "when session.closed arrives…" lo cubren `ShiftPage.test.tsx:217` (token borrado y motivo), `useDriverSocket.test.tsx:188` y `LoginPage.test.tsx:101` (texto del motivo). No se pierde cobertura de ningún AC. |
| `useDriverSocket({ enabled })` | Válida y probada (`useDriverSocket.test.tsx:215`). |
| `DemandView` pide `GET …/view` una vez al montarse sin vista inicial y descarta las vistas de otra salida o anteriores | Válida (`DemandView.tone.test.tsx:136`, `ShiftPage.test.tsx:153`). Riesgo menor: N-10. |
| Foco explícito a "Finalizar turno" además de `close()` | Válida. WebKit no enfoca un botón al pulsarlo, así que hace falta. |
| `getCurrentPosition` deja de pedirse con permiso denegado hasta "Reintentar" | Válida (`useDriverPosition.test.tsx:266`). |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` con el puerto 4173 libre: **salida 0**.

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 1857 passed, 12 deselected |
| frontend: format, lint, types | OK |
| frontend: tests | 660 passed, 2 skipped (68 ficheros) |
| frontend: build + bundle | OK (5 tests) |
| frontend: e2e + a11y | 132 passed, 12 skipped (perfiles no tablet), sin reintentos |
| harness: `feature_list.json`, trazabilidad AC→test | OK |

**Navegador real contra el backend real v1.3.** Script fuera del repo. El backend usaba una copia de
la base de datos en el directorio temporal, con `AVISABUS_ARRIVALS_SOURCE=replay`,
`AVISABUS_DRIVER_IDLE_TIMEOUT_MIN=1` y `AVISABUS_DRIVER_REAPER_INTERVAL_S=5`. El `dist/` se servía
con `vite preview` y su proxy. La geolocalización estaba simulada en la página con tres modos:
"en marcha", "parado" (`watchPosition` calla y `getCurrentPosition` da un fijo nuevo) y "GPS perdido"
(nada; `getCurrentPosition` termina en `TIMEOUT`). Hubo 0 peticiones externas. En el log del backend
no aparecen coordenadas, tokens ni códigos.

| Comprobación | Resultado |
|---|---|
| Selector de la primera salida (`service = null`), 12 s | 1 socket, `hello` enviado, 2 `PUT position` → 204, vista `gps` de `WAITING` a `OK` |
| Elegir salida | Mismo socket (1 en total durante el turno) |
| Autobús parado, 45 s | 9 envíos con 5 `recorded_at` distintos. `getCurrentPosition` con `{enableHighAccuracy: true, maximumAge: 0, timeout: 10000}`. `gps = OK`, sin "Posición desactualizada" |
| GPS perdido, 80 s (más que el `IDLE` de 60 s) | "Posición desactualizada" a los 40 s (30 s de umbral más el refresco del servidor). 16 reenvíos con un único `recorded_at`. Turno abierto: `GET view` = 200 con `gps = STALE`, sin `session.closed` y la página sigue en `/driver/shift` |
| GPS recuperado | El aviso desaparece en menos de 12 s |
| Control: página cerrada, sin reenvío | El servidor cierra con `IDLE` (`driver.session_closed reason=IDLE`), y `GET view` = 401 a los 65 s |
| Foco: "Seguir" / Escape (Chromium y WebKit) | `Finalizar turno` / `Finalizar turno` en los dos navegadores |
| Confirmar fin | `/driver` con "Turno finalizado" y socket cerrado |
| Permiso denegado en el selector | El selector no muestra aviso. La vista de demanda muestra "Sin permiso de ubicación…" y "Reintentar". Tras "Reintentar" con el permiso concedido, el aviso desaparece y se envía la posición |

## Hallazgos

### Bloqueantes

Ninguno.

### Problemas de spec

**P-05 · Nuevo, no bloqueante, para la persona (CP-4).** La v1.1 de `driver_ui` no sigue el orden de
`docs/use_cases.md` CU-08.
- CU-08 pide el permiso de geolocalización en el paso 4, después de elegir la salida en el paso 3.
  AC-04 y AC-09 v1.1 siguen la posición desde que se abre el turno, también antes de la primera salida
  (`service = null`). Por eso el navegador pide el permiso al entrar al selector
  (`ShiftPage.tsx:47-48`).
- CU-08 4a ("lo indica; se ofrece reintentar") no tiene reflejo en el selector: si el conductor
  deniega el permiso ahí, no lo ve hasta llegar a la vista de demanda.
- El código cumple la spec aprobada, y la persona aprobó la v1.1 con este texto (PR #55). Por eso no
  bloquea, pero `docs/` y la spec quedan desalineados.
- Propuestas:
  - **A (recomendada):** actualizar CU-08 para que el permiso y el envío empiecen al abrir el turno,
    antes del paso 3 (motivo: señal de vida de `driver_session.AC-13`). Si la persona quiere que el
    selector avise del permiso denegado, añadirlo a AC-02 o AC-04 en una v1.2.
  - **B:** limitar la v1.1 a la *siguiente* salida y mantener el orden de CU-08 en la primera. Obliga
    a cambiar AC-04/AC-09 y el código, y deja la primera elección sin señal de vida, aunque el
    servidor no la necesita: `IDLE` cuenta desde `started_at`.

**P-02, P-03, P-04 · Siguen abiertos, no bloqueantes** (sin cambios desde el ciclo 1): estado en la
cabecera de §5.9 sin texto definido, plurales fijos ("Esperan 1 personas…", "1 plazas libres") y textos
sin definir para la lista vacía y los errores.

### No bloqueantes

Siguen abiertos los del ciclo 1, con las líneas actualizadas:

- **N-01** `DemandView.tsx:28-33`: `isFor` acepta vistas con `service: null`, y una vista en vivo así
  (la salida desaparece al cambiar el feed) no lleva al selector.
- **N-02** `DemandView.tsx:220,228` y `newAlerts.ts:21`: la clave y el resalte van por `stop_id`. Una
  parada que aparece dos veces en el viaje duplica la clave; conviene usar `stop_sequence`.
- **N-03** `tone.ts:21-22`: el `AudioContext` se crea fuera de un gesto del usuario. Hay que probarlo en
  Safari/iPadOS en CP-6.
- **N-04** `useDriverSocket.ts:143`: al volver la red, `connected` se mantiene hasta que el socket nuevo
  se resuelve.
- **N-05** `DemandView.tsx:8-9`, `StopCard.tsx:5`, `ServicePicker.tsx:13`: importan de
  `features/passenger` (`docs/conventions.md` §4).
- **N-06** `ServicePicker.tsx:141`: un fallo de carga no ofrece "Reintentar".
- **N-07** `ShiftPage.tsx:78-96`: las fases `loading` y `failed` no tienen `h1`.
- **N-08** `e2e/driver.spec.ts:314`, `:343`: axe no se ejecuta con el GPS desactualizado ni con el
  diálogo abierto.
- **N-09** `frontend/src/shared/device/storage.ts:2`: el comentario "The only keys" no incluye
  `avisabus.driverMute`.

Nuevos:

- **N-10** `DemandView.tsx:28-33,93-99`: riesgo bajo, deducido de leer el código y no reproducido. Al
  elegir la *primera* salida, una vista con `service: null` en vuelo (generada antes del `PUT …/service`)
  que llegue por el socket después de montar `DemandView` contaría como la "primera vista". La
  siguiente, con las solicitudes que ya existían, sonaría y las marcaría como "Nueva" (AC-07: "la primera
  vista tras entrar marca sus solicitudes como vistas sin tono"). Propuesta, junto con N-01: no tomar
  como primera vista una con `service: null` cuando la vista ya tiene salida.
- **N-11** `frontend/src/features/driver/useDriverShift.ts`: no está en la lista de design §1. Hay que
  añadirlo en la próxima versión de la spec. Es documental.

### Lista de comprobación (§4)

- **Contrato:** comportamiento según AC-01–AC-12 v1.1. Endpoints y mensajes iguales que en el
  ciclo 1, y además comprobados contra el backend real (`PUT position` con `service = null` → 204,
  `hello`, `driver.view`, `session.closed`, 401/4401).
- **Arquitectura:** el diff de la feature no toca el backend; los cambios de backend del rango vienen
  de la fusión de `feat/driver_session` v1.3.
- **Tests:** temporizadores falsos, `FakeWebSocket`, geolocalización y `wakeLock` simulados, sin red.
  No son tautológicos: los de v1.1 se vieron en rojo según `impl_driver_ui.md`, y el e2e del flujo
  falla con el `dist/` anterior (1 envío).
- **Privacidad:** el token solo está en `sessionStorage`, en la cabecera y en el `hello`; no hay
  `console.*` ni `device_id` en `features/driver`. El backend no registra posiciones ni tokens.
- **Accesibilidad:** axe sin violaciones en el perfil tablet, es y ca. Foco correcto al cerrar el
  diálogo (B-02 resuelto). Estados con icono y texto.
- **i18n:** no hay claves nuevas en este ciclo; la paridad es/ca-valencia sigue completa.
- **Alcance:** `git diff origin/feat/driver_session...HEAD` solo toca `frontend/src/features/driver/`,
  `routes.tsx`, locales, e2e y fixtures, `progress/` y `feature_list.json`. No hay variables nuevas.
  Los commits siguen Conventional Commits con el ámbito `driver_ui`.

### Fuera del alcance de esta feature (para el orquestador)

- `.env.example:158-161` todavía describe `AVISABUS_DRIVER_IDLE_TIMEOUT_MIN` y
  `AVISABUS_DRIVER_GPS_STALE_S` como "sin recibir posición". Desde `driver_session` v1.3 son "sin señal
  de vida" y "sin un fijo nuevo". Le corresponde a `driver_session`; conviene añadirlo a su lista de
  pendientes, junto a N-10/N-11 de esa feature.
