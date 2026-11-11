# Revisión: driver_ui
Ciclo: 2 de la v1.2 · Fecha: 2026-11-11 · Agente: reviewer · Commit revisado: 3269e2a (spec v1.2, T-08 y T-07,
con la corrección de B-01 en d819fab; diff `origin/feat/driver_session-v1.4...HEAD`)

## Veredicto: APPROVED

B-01 está resuelto, y lo he comprobado por mi cuenta forzando la carrera en una copia fuera del
repositorio. Con el retraso, el test antiguo falla siempre en los 4 sitios afectados y el nuevo pasa
siempre.

Desde el ciclo 1 solo ha cambiado `ShiftPage.test.tsx`: no se ha tocado código de producción. T-08 sigue
cumpliendo la v1.2 tal como se aprobó en el ciclo 1. `CI=1 ./init.sh verify --e2e` sale en verde las dos
veces que lo he ejecutado (ver "Verificación ejecutada": en la primera hubo reintentos en e2e de otras
features).

P-05 se cierra: está resuelto en `docs/use_cases.md` v1.6. Para la persona siguen abiertos P-06 y P-07,
y hay una observación documental nueva sobre CU-08 (N-15).

## Matriz AC → evidencia

Los tests están en `frontend/src/features/driver/__tests__/`, salvo los de `e2e/driver.spec.ts`. El código
de producción y los tests de la v1.2 no han cambiado desde el ciclo 1 (`git diff 9327ee6 HEAD`: solo
`ShiftPage.test.tsx` y `progress/`). La evidencia de T-08 se mantiene y vuelve a pasar. Las líneas de
`ShiftPage.test.tsx` se han desplazado por el auxiliar `findSocket()` y aquí están actualizadas.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `LoginPage.test.tsx`, `session.test.ts` | OK | Sin cambios. |
| AC-02 | `ServicePicker.test.tsx:81,90,103,121,137,167` y, de la v1.2, `:182,203,218,232,252`; `ShiftPage.test.tsx:75,107` | OK | Sin cambios desde el ciclo 1. Lista vacía con el texto exacto, "Volver" y "Actualizar" (`:182`). 5xx y error de red en cada paso con "No se han podido cargar los datos" y "Reintentar" (`:203,218,232`). Los mismos textos en valenciano (`:252`). |
| AC-03 | `ShiftPage.test.tsx:58,66,87,240`; `session.test.ts`; `useDriverSocket.test.tsx`; `useDriverPosition.test.tsx` | OK | `:240` (cierre 4401) ya espera al socket con `findSocket()` (`:245`): B-01 resuelto. |
| AC-04 | `useDriverPosition.test.tsx`; `ShiftPage.test.tsx:143,160`; `DriverStatus.test.tsx`; `e2e/driver.spec.ts` | OK | `:154` espera a `watchPosition` con `waitFor` y `:155` espera al socket. Era el cuarto sitio con el patrón, y el implementer lo encontró por su cuenta. |
| AC-05 | `DemandView.test.tsx:71,81,92,120,133` y, de la v1.2, `:172`; `ShiftPage.test.tsx:98` | OK | Sin cambios. Ver P-07 para "más tiempo" y "visión". |
| AC-06 | `CapacityBanner.test.tsx:13–74` y, de la v1.2, `:89,105,120`; `DemandView.test.tsx:143,210` y, de la v1.2, `:152,162`; `e2e/driver.spec.ts:39-41,64-66` | OK | Sin cambios. Frases exactas en singular y en plural, en es y ca. |
| AC-07 | `newAlerts.test.ts`, `tone.test.ts`, `DemandView.tone.test.tsx`, `useDriverSocket.test.tsx` | OK | Sin cambios. |
| AC-08 | `DriverStatus.test.tsx:39–95`; `DemandView.test.tsx:282,291` y, de la v1.2, `:216,240,250,270`; `ServicePicker.test.tsx:270`; `ShiftPage.test.tsx:127,160` | OK | Sin cambios. Textos visibles de la cabecera con icono, en es y ca. Ver P-06. |
| AC-09 | `useDriverSocket.test.tsx`; `ShiftPage.test.tsx:143,160`; `DemandView.tone.test.tsx`; `e2e/driver.spec.ts` | OK | `:160` usa `findSocket()` (`:175`) antes de abrir el socket. Las comprobaciones posteriores (mismo socket, `clearWatch` y `release` sin llamar, un solo `watchPosition`) siguen siendo estrictas. |
| AC-10 | `DemandView.test.tsx`, `EndShiftDialog.test.tsx`, `LoginPage.test.tsx`, `ShiftPage.test.tsx:224`, `e2e/driver.spec.ts` | OK | `:224` usa `findSocket()` (`:229`). |
| AC-11 | `e2e/driver.spec.ts` (es y ca, `tablet-landscape`) | OK | Los 6 e2e de `driver` en `tablet-landscape` pasan a la primera en las dos ejecuciones, con axe y sin peticiones externas. |
| AC-12 | Capturas en `frontend/test-results/driver_ui/tablet-landscape/` | OK con reserva | Sin cambios visuales desde el ciclo 1, que revisó las capturas. Valida la persona en CP-6. |

### Comprobación de B-01 (carrera forzada fuera del repositorio)

Copia de `frontend/` en el scratchpad de la sesión (clon APFS, sin `dist/` ni `test-results/`). En la copia
he quitado el enlace `node_modules/node_modules`, que apuntaba al `node_modules` del repositorio y cargaba
dos Reacts. Tests comparados: el antiguo (`ShiftPage.test.tsx` de 9327ee6) y el nuevo (d819fab).

Dos inyecciones de retraso, controladas por variables de entorno y desactivadas sin ellas:

- **A**, en `ShiftPage.tsx`: `useDriverShift` recibe `enabled` con un `setTimeout`. Esto retrasa a la vez
  el socket y `watchPosition`, solo en la ruta de `ShiftPage`. Es el escenario real de B-01: el render que
  activa el turno viene de resolver una promesa.
- **B**, en los hooks: `useDriverSocket` llama a `connect()` y `useDriverPosition` llama a
  `watchPosition` dentro de un `setTimeout`.

| Prueba | Antiguo (9327ee6) | Nuevo (d819fab) |
|---|---|---|
| Sin inyección | 11/11 | 11/11 |
| A con 1, 50 y 300 ms | **4 fallos** en cada caso: `:143`, `:160`, `:224` y `:240` (3 con `no WebSocket has been created`; el de `:143` con `watchPosition` sin llamar) | 11/11 en cada caso |
| B con 1, 50 y 300 ms | **4 fallos** idénticos | 11/11 en cada caso |
| Suite `src/features/driver` completa, 10 veces con A = 50 ms | — | 10/10 con 112 passed |
| Suite `src/features/driver` completa, 10 veces sin inyección | — | 10/10 con 112 passed |

La inyección B aplicada a toda la suite hace fallar 34 tests de `DemandView*`, `useDriverSocket` y
`useDriverPosition`. Es lo esperado y no indica otra carrera. Esos tests montan con `render` o
`renderHook`, que van dentro de `act`, y React ejecuta los efectos pasivos antes de salir de `act`. B
cambia esa semántica a propósito al sacar la apertura a una macrotarea. Los usos de
`FakeWebSocket.last()` en `DemandView.test.tsx:37`, `DemandView.tone.test.tsx:50` y
`useDriverSocket.test.tsx` siempre ocurren después de un montaje síncrono, así que no tienen la carrera.
Coincide con lo que documenta el implementer.

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` sobre 3269e2a, con el puerto 4173 libre (comprobado con `lsof`). No he hecho
peticiones externas.

| Paso | 1.ª ejecución | 2.ª ejecución |
|---|---|---|
| backend: format, lint, types, architecture | OK | OK |
| backend: tests | 1915 passed, 9 deselected | 1915 passed, 9 deselected |
| frontend: format, lint, types | OK | OK |
| frontend: tests | 675 passed, 2 skipped (68 ficheros) | 675 passed, 2 skipped (68 ficheros) |
| frontend: build + bundle | OK (5 tests) | OK (5 tests) |
| frontend: e2e + a11y | OK: 127 passed + **5 flaky**, 12 skipped (15,3 min) | 132 passed, 12 skipped (40 s), sin reintentos |
| harness: feature_list.json y trazabilidad AC→test | OK | OK |
| **Resultado** | salida 0 | salida 0 |

Los 5 "flaky" de la 1.ª ejecución pasaron al reintentar (Playwright con `CI`). Ninguno es de esta
feature: los 5 son del perfil `iphone`, 3 de `e2e/stop-view.spec.ts` (`passenger_stop_view`) y 2 de
`e2e/map-view.spec.ts` (`passenger_map_view`). Además, el fallo fue un timeout de 30 s en `page.goto`.
Esa fase e2e tardó 15,3 min frente a 40 s en la 2.ª, lo que apunta a una máquina cargada; coincidió con
la copia de `frontend/` para el experimento. En la 2.ª ejecución no hubo ningún reintento. Los e2e de
`driver` pasaron a la primera en las dos ejecuciones. No es un hallazgo de `driver_ui`. Si se repite con la
máquina en reposo, habría que abrirlo en esas features.

Otras comprobaciones:

- `git diff 9327ee6 HEAD --stat`: desde el ciclo 1 solo cambian
  `frontend/src/features/driver/__tests__/ShiftPage.test.tsx`, `progress/` y `feature_list.json`. Es solo
  de tests, como pedía B-01.
- `git diff --stat origin/feat/driver_session-v1.4...HEAD`: solo ficheros de T-08 (`ServicePicker`,
  `DemandView`, `CapacityBanner`, sus tests y los dos `translation.json`), `ShiftPage.test.tsx`,
  `progress/` y `feature_list.json`.
- El commit d819fab sigue Conventional Commits (`test(driver_ui): …`) con la referencia a B-01 y T-07.
- `git status`: el árbol sigue limpio salvo `qr/`, sin seguimiento, que existía antes y no he tocado.

## Hallazgos

### Bloqueantes

Ninguno.

**Resueltos en este ciclo:**

- **B-01** (ciclo 1, `ShiftPage.test.tsx`): test intermitente que usaba `/ws/driver` antes de existir.
  Ahora hay un auxiliar `findSocket()` (`ShiftPage.test.tsx:37-40`) que espera con `waitFor` a que exista
  el socket. Se usa en `:155`, `:175`, `:229` y `:245`, y `:154` espera a `watchPosition`. Corrige los 3
  sitios señalados y un cuarto con el mismo patrón (`:143`, AC-04/AC-09). El auxiliar no es tautológico:
  si el socket no llega a abrirse, `waitFor` falla al cabo de 1 s. Comprobado con la carrera forzada (ver
  la tabla de arriba).

### Problemas de spec (para la persona; no bloquean)

**P-05 · Cerrado.** `docs/use_cases.md` v1.6 (PR #60) reordena CU-08: el paso 3 pide la ubicación ("que
mantiene el turno vivo mientras el conductor elige") y el paso 4 elige línea, sentido y salida. Ya coincide
con la v1.1 de `driver_ui` (AC-04, AC-09). Ver N-15 para una consecuencia documental del cambio de orden.

**P-06 · Sigue abierto.** Estado de la cabecera sin correspondencia con los estados (AC-08 v1.2). AC-08
no dice qué texto lleva la cabecera con `gps = WAITING`, con el permiso denegado ni mientras el socket
conecta por primera vez. La implementación muestra "GPS desactualizado" y "Sin conexión" en rojo al
empezar el turno, y la caja `DriverStatus` calla mientras conecta (`DriverStatus.test.tsx:76`).
Propuestas: (A) un texto neutro ("Esperando GPS", "Conectando…") o (B) dejar escrita la lectura binaria
en AC-08.

**P-07 · Sigue abierto.** Plural de "más tiempo" y "visión" (AC-05 v1.2). Salen "2 más tiempo" y
"2 visión" (en ca, "2 més temps" y "2 visió"), porque design §3 solo da un texto. Hay que fijar si se
quedan invariables o qué forma llevan (p. ej. "Más tiempo: 2").

### No bloqueantes

**Siguen abiertos** (sin cambios desde el ciclo 1; las líneas siguen siendo válidas porque el código de
producción no ha cambiado):

- **N-01** `DemandView.tsx:30-35,109`: `isFor` acepta vistas con `service: null`. Una vista en vivo así no
  lleva al selector.
- **N-02** `DemandView.tsx:245,253` y `newAlerts.ts:21`: la clave y el resalte usan `stop_id`. Una parada
  que aparece dos veces en el viaje duplica la clave; conviene usar `stop_sequence`.
- **N-03** `tone.ts:19-22`: el `AudioContext` se crea fuera de un gesto del usuario. Hay que probarlo en
  Safari/iPadOS en CP-6.
- **N-04** `useDriverSocket.ts:143`: al volver la red, `connected` se mantiene hasta que el socket nuevo se
  resuelve. Desde la v1.2 también afecta a la cabecera.
- **N-05** `DemandView.tsx:9-10`, `StopCard.tsx:5` y `ServicePicker.tsx:14` importan de
  `features/passenger` (`docs/conventions.md` §4).
- **N-07** `ShiftPage.tsx:78-96`: las fases `loading` y `failed` no tienen `h1`.
- **N-08** `e2e/driver.spec.ts:306-313` y `:341-345`: axe no se ejecuta con el GPS desactualizado ni con el
  diálogo abierto. Es la única captura con la cabecera en rojo.
- **N-09** `frontend/src/shared/device/storage.ts:2`: el comentario "The only keys" no incluye
  `avisabus.driverMute`.
- **N-10** `DemandView.tsx:30-35,107-118`: al elegir la primera salida, una vista con `service: null` que
  llegue tarde podría contar como primera vista.
- **N-11** `useDriverShift.ts` no está en design §1 (documental).
- **N-12** `ShiftPage.tsx:94` frente a `ServicePicker.tsx:152`: dos versiones del error de carga en la
  misma ruta. Cumple la spec; si la persona quiere un único texto, que lo añada a AC-02 o AC-03.
- **N-13** `translation.json` (`driver.capacity`, `driver.seats` y `driver.places`): las claves de design §3
  ahora contienen una plantilla, y la frase se compone con seis claves nuevas. Hay que reflejarlo en
  design §3 (documental).
- **N-14** `ServicePicker.tsx:144-154,200-210`: los avisos de error y de lista vacía no se anuncian, y
  cuando "Reintentar" o "Actualizar" funcionan, el foco cae al `body`. No incumple ningún AC.

**Nuevos:**

- **N-15** (documental, `docs/use_cases.md` CU-08, para la persona): la v1.6 cambió de orden los pasos 3
  y 4 y mantuvo las etiquetas de los flujos alternativos. Ahora "3a" (la salida ya la lleva otro turno)
  es una alternativa al paso 4, y "4a" (permiso denegado) y "4b" (fuera del recorrido) son alternativas
  al paso 3. Esto incumple la regla de numeración de la propia cabecera del documento
  (`<paso><letra>`). No afecta a esta feature: AC-04 cita "CU-08 4a", AC-08 cita "CU-08 4b" y los textos
  coinciden. Si se renumera, habrá que actualizar esas citas en `driver_ui` y en las specs que citen
  CU-08.

### Lista de comprobación (§4)

- **Contrato:** sin cambios desde el ciclo 1. AC-02, AC-05, AC-06 y AC-08 cumplen la v1.2 con los textos
  exactos, y los endpoints no cambian.
- **Arquitectura:** el diff no toca el backend (lint-imports en verde) ni el código de producción del
  frontend en este ciclo.
- **Tests:** sin red ni reloj real (`mockApi`, `FakeWebSocket` y temporizadores falsos donde aplica).
  `findSocket()` usa `waitFor` sin sleeps. Los tests no son tautológicos: con el socket o `watchPosition`
  retrasados, el test antiguo falla y el nuevo sigue comprobando lo mismo.
- **Privacidad:** sin cambios. Nada nuevo se registra ni se guarda.
- **Accesibilidad:** sin cambios desde el ciclo 1. axe no da violaciones en `tablet-landscape`, ni en es ni
  en ca. Pendientes no bloqueantes: N-08 y N-14.
- **i18n:** sin cambios; las claves de `driver.*` están en es y ca-valencia y el lint i18n pasa.
- **Alcance:** solo ficheros de T-08, el test de B-01, `progress/` y `feature_list.json`. No hay variables
  de configuración nuevas.
