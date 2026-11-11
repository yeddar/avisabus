# Implementación: driver_ui
Spec: specs/driver_ui/ (v1.2, APPROVED, PR #60) · Ciclo de revisión: 0 de la v1.2 · Rama:
`feat/driver_ui-v1.2` (apilada sobre `feat/driver_codes_cli-v1.1`, PR #61). Exploración: no necesaria
(tasks.md). Las secciones "Ciclo 1" y "Ciclo 0" de abajo son de la v1.1 y la v1.0.

## v1.2 · Ciclo 0 (T-08 y T-07)

### Tareas
- [x] T-08 (AC-02) Textos sin salidas y de error en `ServicePicker`: lista vacía "No hay salidas de esta
  línea y sentido en la próxima hora" con "Actualizar" (y el "Volver" de siempre); error de red o 5xx en
  cualquier paso (líneas, salidas o `PUT …/service`) "No se han podido cargar los datos" con "Reintentar"
  (commit 5f3ea75)
- [x] T-08 (AC-05, AC-06) Plurales con `count` en todos los textos con número, es y ca-valencia: franjas de
  capacidad y de asientos y plazas libres (commit fe29745)
- [x] T-08 (AC-08) Estado de la cabecera con texto visible e icono: "GPS correcto" / "GPS desactualizado" y
  "Conectado" / "Sin conexión", junto a "Silenciar tono" (commit 22d5e2e); alineado a la derecha cuando la
  cabecera se parte en dos líneas, según `docs/design.md` §5.9, visto en las capturas (commit 505d200)
- [x] T-07 Verificación completa (este fichero)

Tests en rojo antes del código: los 5 nuevos de `ServicePicker.test.tsx` (AC-02), los 3 nuevos de
`CapacityBanner.test.tsx` (AC-06), los 2 de plazas libres de `DemandView.test.tsx` (AC-06) y los 4 de la
cabecera de `DemandView.test.tsx` (AC-08). El nuevo de AC-05 en `DemandView.test.tsx` (personas esperando,
rampas y asientos en singular y plural, es y ca) pasó a la primera: esos textos ya tenían `_one`/`_other`
desde la v1.0; el test fija el comportamiento de la v1.2 en los dos idiomas.

Tests nuevos por AC (`frontend/src/features/driver/__tests__/`):
- AC-02 `ServicePicker.test.tsx`: sin salidas con "Volver" y "Actualizar"; 5xx en las líneas, error de red
  en las salidas y 5xx/error de red al elegir, con "Reintentar"; textos en valenciano.
- AC-05 `DemandView.test.tsx`: plurales de las tarjetas en es y ca.
- AC-06 `CapacityBanner.test.tsx` (singular y plural de las dos franjas, es y ca) y `DemandView.test.tsx`
  (plazas libres, es y ca).
- AC-08 `DemandView.test.tsx`: textos e iconos de la cabecera y sus cambios (STALE, socket cerrado),
  `WAITING`, permiso denegado y valenciano.

### Decisiones locales e interpretaciones
- **Plurales por mitades:** cada frase con dos cifras se compone de dos mitades pluralizadas con `count`,
  porque cada cifra concuerda con sus palabras ("Esperan 2 personas y queda 1 plaza"). `driver.capacity`,
  `driver.seats` y `driver.places` (nombres de design §3) quedan como plantilla de la frase
  ("{{waiting}} y {{places}}"); las mitades son claves nuevas: `driver.capacityWaiting_*`,
  `driver.capacityPlaces_*`, `driver.seatRequests_*`, `driver.seatsLeft_*`, `driver.freePlaces_*`,
  `driver.freeSeats_*`. Con alerta, `free_places`/`free_seats` nunca son `null`
  (`domain/services/demand.py:44-53`); el `?? 0` de `CapacityBanner` solo estrecha el tipo.
- **El ejemplo de AC-05** ("Espera 1 persona" / "Esperan 2 personas") se lee como la franja de capacidad,
  que es lo que dice P-03. Las tarjetas mantienen el texto de design §3, que la v1.2 no cambia
  ("1 persona esperando" / "2 personas esperando", ya con plural correcto).
- **"más tiempo" y "visión" no cambian en plural** ("2 más tiempo", "2 visión"): design §3 les da un único
  texto y la v1.2 no fija otro. No he redactado uno nuevo; ver Bloqueos.
- **Estado de la cabecera con dos valores por indicador:** la v1.2 da cuatro textos para dos indicadores.
  GPS: "GPS correcto" solo con `gps = OK` y el permiso concedido; en cualquier otro caso (`STALE`,
  `WAITING`, permiso denegado, sin vista aún) "GPS desactualizado". Conexión: "Conectado" solo con el
  socket conectado; si no (también mientras conecta la primera vez), "Sin conexión". El detalle sigue en
  las cajas de AC-08 ("Esperando ubicación…", "Sin permiso de ubicación…", "Sin conexión,
  reconectando…"). Ver Bloqueos para `WAITING`.
- **Maquetación de la cabecera** (decisión permitida en design §5): cada estado lleva icono de 24 px y
  texto de 18 px en negrita. El correcto va con el icono de comprobación en `occ-free-fg` y el incorrecto
  con el de aviso en `occ-full-fg`, así que no depende solo del color. Va a la derecha, junto a "Silenciar
  tono", y es texto plano: el anuncio lo hacen las cajas `role="status"`, así que no se anuncia dos veces.
  Lo pinta una función auxiliar dentro de `DemandView.tsx`, no un componente nuevo, por la regla de un
  componente por fichero y para no añadir ficheros fuera de la lista de T-08.
- **Avisos del selector:** el texto se pone entero en negrita, porque es una sola frase (§5.6). "Reintentar"
  vuelve a cargar lo que muestra el paso: líneas o salidas. Tras un fallo al elegir salida, recarga las
  salidas y el conductor vuelve a elegir. "Actualizar" y "Reintentar" llevan el icono de actualizar, como en
  la vista de parada. El `422` al elegir sigue con el aviso de error y la lista recargada (como en v1.0).
- **Valenciano:** las traducciones nuevas son mías, igual que en la v1.0: "No hi ha eixides d'esta línia i
  sentit en la pròxima hora", "Actualitza", "No s'han pogut carregar les dades", "Reintenta", "GPS
  correcte", "GPS desactualitzat", "Connectat", "Sense connexió", "Espera 1 persona" / "Esperen …
  persones", "queda 1 plaça" / "queden … places", "Demana seient 1 persona" / "Demanen seient … persones",
  "queda 1 seient" / "queden … seients", "1 plaça lliure" / "… places lliures". Conviene revisarlas en CP-6.
- **`driver.pick.empty`** cambia de texto: era redacción propia de la v1.0 y ahora es el de la spec.

### Bloqueos
Ninguno impide la revisión. Quedan anotados para que los decida la persona; propuesta entre paréntesis:
1. **`gps = WAITING` en la cabecera:** la v1.2 no da texto para "aún sin posición". Aplico "GPS
   desactualizado", porque no es un GPS correcto, y la caja dice "Esperando ubicación…". (Si se quiere un
   tercer texto, por ejemplo "Esperando GPS", añadirlo a AC-08.) Pasa lo mismo con la conexión mientras se
   abre el primer socket: sale "Sin conexión", pero sin la caja "Sin conexión, reconectando…".
2. **Plural de "más tiempo" y "visión":** "2 más tiempo" y "2 visión" salen tal cual de design §3. Si la
   persona no los da por correctos, hay que fijar el texto del plural en la spec.
3. **Fuera de la lista de ficheros de T-08:** el error de la carga inicial de `/driver/shift`
   (`ShiftPage.tsx`, antes de saber si hay salida) y el del acceso siguen con `stop.error.body` ("No se
   han podido cargar los datos. Comprueba la conexión…"). No los he tocado. (Aclarar si "en cualquier
   paso" los incluye.)

### Verificación
`CI=1 ./init.sh verify --e2e`, puerto 4173 libre: **todo en verde** (salida 0, sobre el commit 505d200).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 1915 passed, 12 deselected |
| frontend: format, lint, types | OK |
| frontend: tests | 675 passed, 2 skipped (68 ficheros) |
| frontend: build + bundle | OK (5 tests) |
| frontend: e2e + a11y | 132 passed, 12 skipped (perfiles no tablet), sin reintentos |
| harness: feature_list.json, trazabilidad AC→test | OK |

He regenerado las capturas de AC-12 en `frontend/test-results/driver_ui/tablet-landscape/`: 14 ficheros con
los mismos nombres, sin versionar. Las he revisado: `sin-solicitudes-es`, `gps-desactualizado-es/ca` y
`fin-recorrido-ca`. La cabecera muestra los dos estados con icono y texto, a la derecha y junto a
"Silenciar tono". En la primera tanda el grupo se quedaba a la izquierda al partirse la cabecera; está
corregido en 505d200. Las franjas y las plazas libres mantienen su texto con las cifras del e2e (35/30,
5/2). El e2e no tiene capturas de la lista vacía ni de los errores del selector; los cubren los tests
unitarios.

## Ciclo 1 (correcciones de `progress/review_driver_ui.md`)

### Tareas
- [x] T-03 AC-04 v1.1 (P-01 resuelto en la spec): reenvío de la última posición cada 5 s aunque se
  repita y `getCurrentPosition` (`enableHighAccuracy`, `maximumAge: 0`, `timeout: 10 s`) si
  `watchPosition` calla 10 s, repetido cada 10 s mientras dure el silencio. Sustituido el test que
  fijaba el envío único (`useDriverPosition.test.tsx:138` del ciclo 0) (commit 3a54162)
- [x] T-02, T-05 B-01: posición, `wakeLock` y `/ws/driver` viven en `ShiftPage` (`useDriverShift`), no en
  `DemandView`; "Elegir la siguiente salida" ya no los corta, y también funcionan en la elección de la
  primera salida (AC-04, AC-08, AC-09 v1.1) (commit a944032)
- [x] T-05, T-06 B-02: "Seguir" cierra el `<dialog>` con `close()` y el foco vuelve a "Finalizar turno"
  (también con Escape); e2e nuevo del foco y comprobación en el flujo completo de que la posición se
  sigue enviando por el mismo socket al elegir la siguiente salida (commit c186b39)
- [x] T-07 Verificación completa (este fichero)

Tests vistos en rojo antes del código: los de AC-04 v1.1 de `useDriverPosition.test.tsx`; los dos nuevos
de `ShiftPage.test.tsx` (primera salida y siguiente salida); el de `enabled` de `useDriverSocket.test.tsx`;
el de la vista pedida al elegir salida (`DemandView.tone.test.tsx`); los de foco de `DemandView.test.tsx`
y `EndShiftDialog.test.tsx`; el e2e de foco y la parte nueva del flujo completo (este último, contra un
`dist/` construido con el código anterior: se quedaba en 1 envío de posición).

Tests nuevos o cambiados por AC: AC-04 `useDriverPosition.test.tsx` (reenvío, `getCurrentPosition`,
silencio con permiso denegado), `ShiftPage.test.tsx` (posición y socket en el selector);
AC-08/AC-09 `ShiftPage.test.tsx`, `useDriverSocket.test.tsx`, `DemandView.tone.test.tsx`;
AC-10 `DemandView.test.tsx`, `EndShiftDialog.test.tsx`, `e2e/driver.spec.ts` (test nuevo `[driver_ui.AC-10]`).
Retirados de `DemandView.test.tsx` (ya no son de la vista): "follows the position while the view is open"
(cubierto en `ShiftPage.test.tsx`) y "when session.closed arrives…" (cubierto por el test AC-10 de
`ShiftPage.test.tsx`, que ya comprobaba token borrado y motivo).

### Decisiones locales e interpretaciones
- **`useDriverShift.ts`** (fichero nuevo, no está en design §1): reúne `useDriverPosition(enabled)` y
  `useDriverSocket` y reparte las vistas a quien escuche. Lo llama `ShiftPage` (design §2: "El hook vive en
  ShiftPage"), con `enabled` mientras la fase es selector o vista de demanda. `DemandView` recibe la
  prop `shift` en lugar de abrir sus propios hooks; el cierre por el servidor (`session.closed`) lo
  gestiona ahora `ShiftPage`.
- **`useDriverSocket`** acepta `enabled` (por defecto `true`): sin turno abierto en la página no abre
  socket ni consulta.
- **También en la elección de la primera salida:** AC-04 y AC-09 v1.1 dicen "también en la elección de
  salida, con `service = null`", así que la posición, el `wakeLock` y el socket empiezan en el selector,
  antes de elegir la primera salida. El permiso de ubicación se pide por tanto al entrar al selector
  (CU-08 lo pone en el paso 4, tras elegir salida). El aviso "Sin permiso de ubicación…" con "Reintentar"
  sigue mostrándose solo en la vista de demanda: el selector no muestra estados de GPS.
- **Vista tras elegir salida:** con el socket ya abierto no llega una vista "de entrada", así que
  `DemandView` pide `GET …/view` una vez al montarse sin vista inicial. La primera vista que recibe una
  salida marca sus solicitudes como vistas sin tono (como antes, cuando el socket se reabría al elegir).
  Se descartan las vistas de otra salida (una tardía del viaje anterior) y las más antiguas que la última
  aplicada; las de `service = null` se siguen mostrando como antes (N-01 queda fuera de este ciclo).
- **Foco al cerrar el diálogo:** además de `close()`, `DemandView` enfoca "Finalizar turno"
  explícitamente al cerrarse el diálogo: WebKit no enfoca un botón al pulsarlo, así que no tiene nada que
  restaurar (el reviewer lo vio en WebKit: `BODY`/`MAIN`), y el perfil tablet de los e2e es WebKit.
- **`getCurrentPosition` con permiso denegado:** deja de pedirse hasta "Reintentar".

### Bloqueos
Ninguno. Los no bloqueantes P-02 a P-04 y N-01 a N-09 quedan fuera de este ciclo (la v1.1 no los
resuelve en la spec); siguen anotados abajo y en `progress/review_driver_ui.md`.

### Verificación
`CI=1 ./init.sh verify --e2e`, puerto 4173 libre: **todo en verde** (salida 0, sobre el commit c186b39).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 1857 passed, 12 deselected |
| frontend: format, lint, types | OK |
| frontend: tests | 660 passed, 2 skipped (68 ficheros) |
| frontend: build + bundle | OK (5 tests) |
| frontend: e2e + a11y | 132 passed, 12 skipped (perfiles no tablet), sin reintentos |
| harness: feature_list.json, trazabilidad AC→test | OK |

Capturas de AC-12 regeneradas en `frontend/test-results/driver_ui/tablet-landscape/` (14 ficheros, mismos
nombres; no versionadas). No cambia la maquetación: el flujo nuevo del e2e no añade capturas.

## Ciclo 0

Spec v1.0 (PR #46), rama apilada sobre `feat/driver_demand`. Superado en el ciclo 1: la interpretación
"posición solo en la vista de demanda" (B-01) y el bloqueo 2 "autobús parado y GPS" (resuelto en la spec
v1.1 / `driver_session` v1.3).

### Tareas
- [x] T-01 `session.ts`, `driverApi`, `LoginPage`, rutas diferidas y textos (commit 876f585)
- [x] T-02 `ServicePicker` y `ShiftPage` (commit 5c7ae41)
- [x] T-03 `useDriverPosition`: posición, permiso y `wakeLock` (commit e377203)
- [x] T-04 `useDriverSocket`, `newAlerts`, `tone` (commit 709d2e7)
- [x] T-05 `DemandView`, `StopCard`, `CapacityBanner`, `DriverStatus`, `EndShiftDialog`, silencio y cierre por el servidor (commit b8ddc3d)
- [x] T-06 E2E del flujo completo, axe y capturas (commits 03793e0 y 472a763)
- [x] T-07 Verificación completa (este fichero)

Tests escritos antes del código y vistos en rojo en T-01 a T-05. Los e2e de T-06 se escribieron con la
vista ya hecha y pasaron a la primera, así que no se vieron en rojo.

Ficheros de test por AC (`frontend/src/features/driver/__tests__/`): `session.test.ts`, `LoginPage.test.tsx`
(AC-01, AC-03, AC-10); `ServicePicker.test.tsx` (AC-02, AC-08); `ShiftPage.test.tsx` (AC-02, AC-03, AC-05,
AC-08, AC-10); `useDriverPosition.test.tsx` (AC-03, AC-04); `newAlerts.test.ts`, `tone.test.ts`,
`DemandView.tone.test.tsx` (AC-07); `useDriverSocket.test.tsx` (AC-03, AC-07, AC-09, AC-10);
`DemandView.test.tsx` (AC-04–AC-06, AC-08, AC-10); `CapacityBanner.test.tsx` (AC-06);
`DriverStatus.test.tsx` (AC-04, AC-08); `EndShiftDialog.test.tsx` (AC-10); `e2e/driver.spec.ts` (AC-11, AC-12).

Capturas para AC-12: `frontend/test-results/driver_ui/tablet-landscape/<nombre>-<es|ca>.png` (acceso,
eleccion-salida, sin-solicitudes, solicitud-nueva, alerta-capacidad, gps-desactualizado, fin-recorrido).
Revisadas contra `docs/design.md` §5.9; de ahí salió un fallo ya corregido: los iconos de "Silenciar tono"
y "Volver" no tenían tamaño y no se pintaban.

### Decisiones locales
Dentro de design §5 (maquetación no fijada y envolvente del tono):
- **Envolvente del tono:** ataque lineal de 20 ms hasta 0,3 de ganancia y caída lineal hasta los 300 ms.
- **`DriverLayout.tsx`** (no está en la lista de design §1): mismos landmarks que `Layout`, con columna de
  1200 px para las tres tarjetas. `Layout` es de `frontend_i18n` y su columna de 640 px no sirve aquí.
- **Tarjetas:** una columna por debajo de `md`, tres por encima; las paradas 4 y 5 en dos columnas.
- **Ficheros auxiliares:** `types.ts` (alias del esquema; `shared/api/types.ts` no estaba en las tareas),
  `icons/{NeedIcon,WarningIcon,BellIcon}.tsx`.

Interpretaciones de la spec, fuera de esa lista, para que las valide el reviewer o la persona:
- **`driverApi` devuelve** cualquier respuesta HTTP salvo el 401; así lo sugiere `{status, data, retryAfterS}`
  en design §2. Además exporta `subscribeDriverAuthLost` y `loseDriverAuth`: `useDriverPosition(enabled)` no
  puede avisar de un 401 con la firma fijada, y `ShiftPage` navega a `/driver` desde esa suscripción (AC-03).
- **La posición se sigue solo en la vista de demanda**, no en el selector: CU-08 pide el permiso después de
  elegir salida (paso 4) y AC-04 dice "LA VISTA".
- **"Volver" en el paso de línea** vuelve a `/driver` sin cerrar el turno; al entrar otra vez con el mismo
  código, `driver_session.AC-03` cierra el anterior.
- **Estados y franjas a la vez:** §5.9 dice "caja de §5.6 en lugar de las franjas", pero AC-06 no condiciona
  las franjas. Por `docs/design.md` §1 manda la spec en comportamiento: se muestran las dos, en el mismo sitio.
- **Cabecera sin indicador de GPS/conexión** (§5.9 "estado (GPS, conexión)"): no hay texto especificado para
  el estado correcto, y los problemas ya salen en las cajas con el texto de AC-08.
- **Texto de personas esperando:** se usa el de design §3 ("2 personas esperando"), no "esperando" a secas
  de §5.9; la cifra va a 64 px y el resto a 18 px. Las paradas 4 y 5 incluyen distancia y necesidades (AC-05).
- **Franjas anunciadas por el `Announcer`** (región `role="alert"`, `frontend_i18n.AC-12`) y no con `role`
  en la propia franja: así los cambios de cifras no las anuncian otra vez y dos franjas simultáneas salen en
  un solo mensaje (AC-06).
- **Claves i18n de design §3:** `driver.places` y `driver.places.unknown` (igual `driver.end` y
  `driver.end.confirm/yes/no`) no caben anidadas en JSON; las segundas van como claves con punto dentro de
  `driver`, que i18next resuelve. Los nombres de clave son los de la spec.
- **429 sin `Retry-After`:** 15 min, el bloqueo de `driver_session.AC-02`.
- **`DELETE` fallido al finalizar:** se borra el token y se vuelve a `/driver` igualmente; el servidor cierra
  el turno por inactividad.

### Bloqueos
Ninguno impide la revisión. Huecos de spec que quedan para decidir aparte (propuesta entre paréntesis):
1. **Errores y lista vacía sin texto en la spec.** Fallo de red o 5xx en el acceso y el selector reutiliza
   `stop.error.body`; un `422` al elegir salida refresca la lista con ese mismo aviso. La lista sin salidas usa
   un texto nuevo, `driver.pick.empty` ("No hay salidas en este momento"). También son redacción propia
   `driver.pick.line/direction/departure/lineLabel`, `driver.shift.title` y `driver.demand.departure`, que
   design §3 nombra sin texto o no lista por ser "extracto". (Añadirlos a la spec.)
2. **Autobús parado y GPS.** Cada posición se envía una sola vez porque el backend renueva `last_position_at`
   aunque `recorded_at` se repita (`application/driver_sessions.py:473-477`): reenviar la última ocultaría
   `STALE` (CU-09 1a), así que "enviar la última cada 5 s" se lee como "si hay una nueva". Si un dispositivo
   no da posiciones con el autobús parado, saldrá "Posición desactualizada" a los 30 s y el turno se cerraría
   a los 10 min. No se ha podido probar en una tablet real. (Comprobarlo en CP-6; si pasa, decidir en backend.)
3. **Plurales fijos en la spec:** salen "Esperan 1 personas y quedan 0 plazas" y "1 plazas libres · 1
   asientos"; design §3 no define el singular. También "2 más tiempo" y "2 visión". (Añadir `_one`.)
4. **Comentario desactualizado:** `shared/device/storage.ts` dice "The only keys" y no incluye
   `avisabus.driverMute`, permitida por `docs/conventions.md` §4. No se ha tocado por estar fuera de las
   tareas. (Añadirla en una tarea futura.)
5. **Valenciano:** las traducciones son propias, sin revisión de una persona hablante. (Revisarlas en CP-6.)

### Verificación
`CI=1 ./init.sh verify --e2e`, puerto 4173 libre: **todo en verde** (salida 0, sobre el commit 472a763).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 1846 passed, 12 deselected |
| frontend: format, lint, types | OK |
| frontend: tests | 651 passed, 2 skipped (68 ficheros) |
| frontend: build + bundle | OK (5 tests) |
| frontend: e2e + a11y | 130 passed |
| harness: feature_list.json, trazabilidad AC→test | OK |

La primera ejecución completa falló en un e2e (`Torn finalitzat`): el texto aparecía a la vez en la vista y en
la región de anuncios, según el momento. Era un fallo del test; se acotó a `main` (commit 472a763).
