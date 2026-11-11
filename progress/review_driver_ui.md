# Revisión: driver_ui
Ciclo: 1 de la v1.2 · Fecha: 2026-11-11 · Agente: reviewer · Commit revisado: 9327ee6 (spec v1.2, T-08 y T-07;
diff `origin/feat/driver_session-v1.4...HEAD`)

## Veredicto: CHANGES_REQUESTED

T-08 cumple la v1.2. Los textos de AC-02 y AC-08 son exactamente los de la spec. Los plurales de AC-05 y
AC-06 son correctos en es y ca-valencia. La cabecera muestra el estado con icono y texto, y no lo anuncia
dos veces. Las capturas se ajustan a `docs/design.md` §5.9.

El único bloqueante es **B-01**: la primera ejecución de `CI=1 ./init.sh verify --e2e` **falló** por un
test intermitente de `ShiftPage.test.tsx`. Ese test no se ha tocado en la v1.2, pero es de esta feature, y
la regla del proceso es clara: si `verify` falla, el veredicto es `CHANGES_REQUESTED`. La segunda ejecución
salió en verde. El arreglo es de una línea por test.

Para la persona quedan dos problemas de spec nuevos que no bloquean: P-06 (estado de la cabecera en
`WAITING` y mientras conecta) y P-07 (plural de "más tiempo" y "visión"). P-05 sigue pendiente en CP-4.

## Matriz AC → evidencia

Los tests están en `frontend/src/features/driver/__tests__/`, salvo los de `e2e/driver.spec.ts`. He leído
todos los tests nuevos de la v1.2. Los ACs que la v1.2 no cambia mantienen la evidencia del ciclo 2 de la
v1.1: su código y sus tests no han cambiado y vuelven a pasar.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `LoginPage.test.tsx`, `session.test.ts` | OK | Sin cambios. |
| AC-02 | `ServicePicker.test.tsx:81,90,103,121,137,167` y, de la v1.2, `:182,203,218,232,252`; `ShiftPage.test.tsx:66,98` | OK | Parte v1.2. `:182`: lista vacía con el texto exacto, "Volver" y "Actualizar"; "Actualizar" vuelve a pedir las salidas (2 llamadas) y el aviso desaparece. `:203`: 5xx al cargar las líneas. `:218`: error de red al cargar las salidas. `:232`: 5xx y error de red en `PUT …/service`. Los tres comprueban el texto exacto, "Reintentar" y la recarga, y `:203` comprueba que ya no sale "Comprueba la conexión". `:252`: los mismos textos en valenciano. El paso "sentido" no hace petición propia (usa los datos de las líneas), así que el error de `:203` también lo cubre. |
| AC-03 | `ShiftPage.test.tsx:49,57,78,232`; `session.test.ts`; `useDriverSocket.test.tsx`; `useDriverPosition.test.tsx` | OK, con B-01 | `ShiftPage.test.tsx:232` es intermitente (B-01). |
| AC-04 | `useDriverPosition.test.tsx`; `ShiftPage.test.tsx:134,153`; `DriverStatus.test.tsx`; `e2e/driver.spec.ts` | OK | Sin cambios. |
| AC-05 | `DemandView.test.tsx:71,81,92,120,133` y, de la v1.2, `:172`; `ShiftPage.test.tsx:89` | OK | `:172` comprueba, por tarjeta y en es y ca, "1 persona esperando" / "2 personas esperando", "1 rampa" / "2 rampas" y "1 asiento" / "2 asientos". Ver P-07 para "más tiempo" y "visión". |
| AC-06 | `CapacityBanner.test.tsx:13–74` y, de la v1.2, `:89,105,120`; `DemandView.test.tsx:143,210` y, de la v1.2, `:152,162`; `e2e/driver.spec.ts:39-41,64-66` | OK | Comprueban las frases enteras con `getByText` exacto: "Espera 1 persona y quedan 0 plazas", "Esperan 2 personas y queda 1 plaza", "Pide asiento 1 persona y quedan 0 asientos", "Piden asiento 5 personas y queda 1 asiento", "1 plaza libre · 1 asiento", "2 plazas libres · 0 asientos" y sus equivalentes en ca. El caso plural del e2e ("Esperan 35 personas y quedan 30 plazas", "30 plazas libres · 4 asientos") coincide letra por letra con AC-06. El anuncio único (`:58`) sigue pasando con el texto compuesto. |
| AC-07 | `newAlerts.test.ts`, `tone.test.ts`, `DemandView.tone.test.tsx`, `useDriverSocket.test.tsx` | OK | Sin cambios. |
| AC-08 | `DriverStatus.test.tsx:39–95`; `DemandView.test.tsx:282,291` y, de la v1.2, `:216,240,250,270`; `ServicePicker.test.tsx:270`; `ShiftPage.test.tsx:118,153` | OK | `:216`: "GPS correcto" y "Conectado" con icono; con `STALE`, "GPS desactualizado"; con el socket cerrado, "Sin conexión" con icono. `:240`: con `WAITING` y antes de conectar, "GPS desactualizado" y "Sin conexión" (P-06). `:250`: con el permiso denegado, "GPS desactualizado". `:270`: los textos en valenciano. Los tests comprueban que hay icono, pero no que sea distinto en cada estado. Lo he visto en las capturas: comprobación en el estado correcto y aviso en el incorrecto. |
| AC-09 | `useDriverSocket.test.tsx`; `ShiftPage.test.tsx:134,153`; `DemandView.tone.test.tsx`; `e2e/driver.spec.ts` | OK, con B-01 | El patrón de B-01 también está en `ShiftPage.test.tsx:168` (AC-09). |
| AC-10 | `DemandView.test.tsx`, `EndShiftDialog.test.tsx`, `LoginPage.test.tsx`, `ShiftPage.test.tsx:217`, `e2e/driver.spec.ts` | OK, con B-01 | El patrón de B-01 también está en `ShiftPage.test.tsx:224`. |
| AC-11 | `e2e/driver.spec.ts` (es y ca, `tablet-landscape`) | OK | 132 e2e en verde las dos veces, con axe y sin peticiones externas. |
| AC-12 | 14 capturas en `frontend/test-results/driver_ui/tablet-landscape/` | OK con reserva | He revisado `alerta-capacidad-es`, `gps-desactualizado-ca` y `fin-recorrido-es`. Cumplen §5.9: GPS y conexión a la derecha, junto a "Silenciar tono", con icono y texto, y la parte correcta en verde con una comprobación y la incorrecta en rojo con un aviso. Las franjas y las plazas usan el plural correcto. La cabecera se parte en dos filas a 1080 px de ancho, con el estado alineado a la derecha; lo permite la decisión local de maquetación (design §5). Valida la persona en CP-6. |

### Interpretaciones de `progress/impl_driver_ui.md` (v1.2)

| Interpretación | Juicio |
|---|---|
| Cabecera con dos valores por indicador: `WAITING`, el permiso denegado y la falta de vista se muestran como "GPS desactualizado"; el socket que conecta por primera vez, como "Sin conexión" | **Compatible con la spec, pero la spec no permite decidirlo (P-06).** AC-08 da cuatro textos sin decir a qué estado corresponde cada uno. La lectura binaria no inventa texto y es prudente: solo dice "correcto" cuando lo es. Sin embargo, al empezar el turno el conductor ve en rojo "GPS desactualizado" y "Sin conexión", aunque todavía no ha fallado nada. Además, choca con la intención de la v1.0: `useDriverSocket.ts:66-67` y `DriverStatus.test.tsx:76` evitan precisamente mostrar "Sin conexión" mientras se conecta, y ahora la caja calla pero la cabecera lo dice. |
| "Más tiempo" y "visión" no tienen plural ("2 más tiempo", "2 visión") | **Correcto no redactar.** Design §3 solo da el singular y la v1.2 no fija otro texto. Inventar "visiones" habría ido contra la regla de no improvisar textos. Si el resultado cumple "plural correcto" lo decide la persona (P-07). |
| No se han tocado los errores de `ShiftPage` ni del acceso | **Válida.** "En cualquier paso" de AC-02 se refiere a los tres pasos que el mismo AC enumera: línea, sentido y salida. La carga inicial de `ShiftPage` (`ShiftPage.tsx:80-96`) es anterior a esos pasos, y el acceso está en AC-01. Además, ninguno de los dos ficheros está en la lista de T-08. Aun así, la misma ruta muestra ahora dos versiones del error (N-12). |
| Frases con dos cifras compuestas de dos mitades con claves nuevas | **Válida.** i18next solo admite un `count` por clave, y cada cifra concuerda con sus propias palabras ("Esperan 2 personas y queda 1 plaza"). En plural, el resultado coincide letra por letra con el texto de AC-06 y de design §3. Las formas en singular se derivan gramaticalmente de esas frases o vienen del ejemplo de AC-05 ("Espera 1 persona"): las exige "plural correcto" y no son textos nuevos. Las claves de design §3 (`driver.capacity`, `driver.seats` y `driver.places`) se mantienen, pero ahora contienen una plantilla. Habría que reflejarlo en design §3 (N-13, documental). |
| El ejemplo de AC-05 ("Espera 1 persona" / "Esperan 2 personas") se aplica a la franja; las tarjetas mantienen "N persona(s) esperando" | **Válida.** El ejemplo empieza por "p. ej." y sale de P-03, que hablaba de la franja ("Esperan 1 personas"). Las tarjetas siguen design §3 y §5.9 ("esperando"), ya con plural correcto. |
| Valenciano propio | Aceptable. Las traducciones son correctas y coherentes con las de la v1.0. Se revisan en CP-6. |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e`, con el puerto 4173 libre, sobre 9327ee6. No he hecho peticiones externas.

| Paso | 1.ª ejecución | 2.ª ejecución |
|---|---|---|
| backend: format, lint, types, architecture | OK | OK |
| backend: tests | 1915 passed, 9 deselected | 1915 passed, 9 deselected |
| frontend: format, lint, types | OK | OK |
| frontend: tests | **FAIL**: 674 passed, **1 failed**, 2 skipped: `ShiftPage.test.tsx > [driver_ui.AC-03] the close 4401 of the socket returns to /driver`, con `Error: no WebSocket has been created` en `FakeWebSocket.last` (`ShiftPage.test.tsx:238`) | 675 passed, 2 skipped (68 ficheros) |
| frontend: build + bundle | OK (5 tests) | OK (5 tests) |
| frontend: e2e + a11y | 132 passed | 132 passed |
| harness: feature_list.json y trazabilidad AC→test | OK | OK |
| **Resultado** | **salida 1** | salida 0 |

Para caracterizar el fallo, repetí después el fichero aislado 8 veces, la suite completa 6 veces, la suite
completa 3 veces con otra suite en paralelo y el fichero 24 veces en tandas de 4 en paralelo. En total
fueron 41 ejecuciones y ninguna falló. Es un fallo poco frecuente, pero real.

Otras comprobaciones:

- `git diff --stat origin/feat/driver_session-v1.4...HEAD`: solo cambian `features/driver/{ServicePicker,
  DemandView,CapacityBanner}.tsx`, sus tests, los dos `translation.json`, `progress/` y `feature_list.json`.
  `StopCard.tsx` y `DriverStatus.tsx` están en la lista de T-08, pero no ha hecho falta tocarlos.
- Los commits siguen Conventional Commits con el ámbito `driver_ui` y la referencia a T-08.
- Los dos idiomas tienen las mismas claves en `driver.*` (volcado de los dos JSON).
- `i18n.ts:72` tiene `escapeValue: false`, así que la composición por mitades no escapa nada.

## Hallazgos

### Bloqueantes

**B-01 · `ShiftPage.test.tsx:236-238`: test intermitente que hizo fallar `verify`** (AGENTS.md §6
"Verificación"; `docs/verification.md` §3: `verify` en verde; T-07)

- `await screen.findByText('Salida a las 08:40')` termina en cuanto React confirma `DemandView`. El socket,
  en cambio, se abre en un efecto pasivo: `useDriverShift` → `useDriverSocket.ts:90-131`, con
  `enabled = true` desde la fase `demand`.
- React puede retrasar los efectos pasivos de un render que no viene de un evento discreto (aquí, la
  resolución de una promesa). Si `findByText` gana la carrera, `FakeWebSocket.last()` lanza
  `no WebSocket has been created`.
- El patrón viene de a944032 (v1.1, ciclo 1) y no lo ha introducido T-08. Pero el test es de esta feature
  y hace que `verify` no sea determinista.
- Hay el mismo patrón en `ShiftPage.test.tsx:167-168` (AC-04/AC-08/AC-09) y en `:221-225` (AC-10).
- Arreglo: esperar al socket antes de usarlo en los tres sitios, p. ej.
  `await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))`, o usar un `findSocket()`
  auxiliar. No hay que tocar código de producción.

### Problemas de spec (para la persona; no bloquean)

**P-05 · Sigue abierto** (CP-4, sin cambios). CU-08 pide la ubicación después de elegir la salida, y la
v1.1 la pide desde el selector.

**P-06 · Estado de la cabecera sin correspondencia con los estados** (AC-08 v1.2)

- AC-08 fija "GPS correcto", "GPS desactualizado", "Conectado" y "Sin conexión", pero no dice qué texto
  corresponde a `gps = WAITING`, al permiso denegado ni al socket que conecta por primera vez.
- La implementación usa "GPS desactualizado" y "Sin conexión", en rojo y con icono de aviso. Por eso, al
  empezar cada turno, la cabecera indica un fallo que todavía no existe. Además contradice a la caja, que
  calla mientras se conecta (`DriverStatus.test.tsx:76`).
- Propuestas:
  - **A:** añadir a AC-08 un texto neutro para "todavía no" ("Esperando GPS", "Conectando…").
  - **B:** dar por buena la lectura binaria y dejarla escrita en AC-08.

**P-07 · Plural de "más tiempo" y "visión"** (AC-05 v1.2: "todos los textos con número usan el plural
correcto")

- Salen "2 más tiempo" y "2 visión", en ca "2 més temps" y "2 visió", porque design §3 solo da un texto.
- Como etiqueta de categoría se puede defender, pero no concuerda con "2 rampas" ni con "2 asientos".
- Hay que fijar en la spec si se quedan invariables o qué plural llevan. Una opción es reformularlas como
  categoría: "Más tiempo: 2".

### No bloqueantes

**Resueltos por la v1.2:**

- P-02: estado de la cabecera sin texto.
- P-03: plurales fijos.
- P-04: lista vacía y errores sin texto.
- N-06: el fallo de carga del selector no ofrecía "Reintentar". Resuelto en `ServicePicker.tsx:144-154`.

**Siguen abiertos** (con las líneas actuales):

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
  diálogo abierto. Con la v1.2 tiene más interés: es la única captura con la cabecera en rojo.
- **N-09** `frontend/src/shared/device/storage.ts:2`: el comentario "The only keys" no incluye
  `avisabus.driverMute`.
- **N-10** `DemandView.tsx:30-35,107-118`: al elegir la primera salida, una vista con `service: null` que
  llegue tarde podría contar como primera vista.
- **N-11** `useDriverShift.ts` no está en design §1 (documental).

**Nuevos:**

- **N-12** `ShiftPage.tsx:94` frente a `ServicePicker.tsx:152`: en la misma ruta conviven dos versiones del
  error. La carga inicial muestra "**No se han podido cargar los datos.** Comprueba la conexión y vuelve a
  intentarlo." y el selector muestra "No se han podido cargar los datos". La interpretación cumple la spec
  (ver la tabla). Si la persona quiere un único texto, que lo añada a AC-02 o AC-03.
- **N-13** `translation.json` (`driver.capacity`, `driver.seats` y `driver.places`): las claves de design §3
  ahora contienen una plantilla ("{{waiting}} y {{places}}"), y la frase se compone con seis claves nuevas
  (`capacityWaiting_*`, `capacityPlaces_*`, `seatRequests_*`, `seatsLeft_*`, `freePlaces_*` y
  `freeSeats_*`). Hay que reflejarlo en design §3 en la próxima versión. Es documental.
- **N-14** `ServicePicker.tsx:144-154,200-210`: los avisos de error y de lista vacía no se anuncian (no
  tienen `role="status"` ni `announce`). Además, cuando "Reintentar" o "Actualizar" funcionan, el botón
  desaparece con el aviso y el foco cae al `body`. AC-02 solo pide anunciar el 409, así que no incumple
  ningún AC. Propuesta: `role="status"` en el error y el foco al `h1` del paso tras recargar, como ya se
  hace al cambiar de paso (`:75-80`).

### Lista de comprobación (§4)

- **Contrato:** AC-02, AC-05, AC-06 y AC-08 cumplen la v1.2 con los textos exactos. Los endpoints no
  cambian.
- **Arquitectura:** el diff no toca el backend. En el frontend no hay ficheros nuevos.
- **Tests:** sin red ni reloj real (`mockApi`, `NetworkFailure` y `FakeWebSocket`). Los tests nuevos no son
  tautológicos: comprueban la frase exacta en singular y en plural, y el implementer los vio en rojo, salvo
  el de AC-05, que fija un comportamiento que ya existía. Hay una carrera en `ShiftPage.test.tsx` (B-01).
- **Privacidad:** sin cambios. Nada nuevo se registra ni se guarda.
- **Accesibilidad:**
  - El estado de la cabecera no depende solo del color: lleva texto y un icono de forma distinta, y los dos
    colores superan 7:1 sobre blanco.
  - El estado de la cabecera es texto plano y no es región viva. Los anuncios siguen en las cajas
    `role="status"` de `DriverStatus` y en el `Announcer` de las franjas, así que no se duplican.
  - axe no da violaciones en el perfil tablet, en es ni en ca.
  - Los botones nuevos usan `Button` (mínimo 44 px).
  - Pendientes: N-14 (anuncio y foco en el selector) y N-08.
- **i18n:** no hay literales (pasa el lint). Todas las claves nuevas están en es y ca-valencia y se añadieron
  en el mismo commit.
- **Alcance:** solo los ficheros de T-08, `progress/` y `feature_list.json`. No hay variables nuevas.
