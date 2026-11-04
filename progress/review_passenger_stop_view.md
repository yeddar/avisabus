# Revisión: passenger_stop_view — v1.3
Ciclo: 1 (v1.3) · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/passenger_stop_view/` v1.3 (APPROVED, PR #33) · Rama: `feat/passenger_stop_view-v1.3`
Alcance revisado: T-13 (`a417df7`) y T-10, su registro (`e862baf`) y los commits del orquestador
(`edbc394`, `08e524d`). Base: `origin/develop`.

## Veredicto: APPROVED

T-13 cumple AC-21 v1.3 y la nota del design §5. `npm run test` ya no lee `dist/`.
`npm run test:bundle` construye y después mide. `./init.sh verify` lo ejecuta tras el build, con
y sin `--e2e`. `npm run e2e` ya no lo encadena. He reproducido los tres escenarios de H-04 en una
copia: no hay falso rojo con un `dist/` antiguo manipulado ni falso verde con un `dist/` antiguo
bueno y una fuente que rompe el presupuesto. `CI=1 ./init.sh verify --e2e` está en verde. Hay tres
hallazgos no bloqueantes (N-1 a N-3) y una propuesta de CP-4 para `docs/verification.md`.

## Matriz AC → evidencia

Solo se detalla AC-21 (v1.3) y `passenger_map_view.AC-02`, cuya vía de ejecución cambia. El resto
de AC no se ha tocado (el diff de código se limita a `frontend/package.json`, `init.sh` y
`bundle-budget.test.ts`). Siguen en verde con los tests de las secciones v1.0 a v1.2.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-21 (cálculo) | `bundle-budget.test.ts:80` (`dist` sintético en un directorio temporal) | OK | Se ejecuta en `npm run test`. No lee `dist/`. Comprueba que se cuentan solo el `<script type="module">` y los `modulepreload`, con gzip. Sin cambios respecto a la v1.0. |
| AC-21 (v1.3, solo sobre un build recién hecho) | `bundle-budget.test.ts:122` (scripts de `package.json` y paso de `init.sh`) y `:150` (`it.runIf(BUNDLE_CHECK)`, ≤ 200 KB sobre el `dist/` real) | OK | `:150` solo corre con `AVISABUS_BUNDLE_CHECK=1`, que pone `test:bundle` después de `npm run build &&`. En `npm run test` aparece como omitido (↓) y con el aviso `[bundle-budget] dist/ checks skipped…` en stderr. Medido: `index-*.js` 448,27 kB, **141,49 kB gzip**. `:122` es útil: falla si `e2e` vuelve a encadenar `test:bundle` (mutación comprobada: 1 fallo). Pero no detecta que el paso se meta dentro de `if $e2e` (N-1). |
| `passenger_map_view.AC-02` (Leaflet bajo demanda) | `bundle-budget.test.ts:103` (sintético, en `npm run test`) y `:139` (`runIf`, `dist/` real) | OK | Se sigue ejecutando por la vía nueva: en "frontend: build + bundle" hay 5/5 (los 2 de `dist/` real incluidos). `:151` también cita AC-02. `MapPage-*.js` 50,21 KB gzip y Leaflet fuera del trozo inicial. El design de `passenger_map_view` (§5, AC-02) solo exige "`bundle-budget.test.ts` ampliado" y no fija cuándo se ejecuta, así que no hay conflicto. |

### Escenarios de H-04 (copia en el scratchpad)
Copia de `init.sh`, `frontend/`, `scripts/`, `specs/`, `docs/` y `feature_list.json` en el scratchpad
(`git archive HEAD`), con `node_modules` enlazado y sin `backend/`. Por eso "harness: trazabilidad"
falla en la copia: faltan los tests de backend. Es ajeno a lo que se prueba.

| Escenario | `npm run test` | `./init.sh verify` (pasos de frontend) |
|---|---|---|
| 1. `dist/` borrado | 408 passed, 2 skipped. Código 0 | "frontend: tests" OK. "frontend: build + bundle" construye y pasa 5/5 |
| 2. `dist/` antiguo manipulado (≈400 KB aleatorios y `leaflet-pane` añadidos a `index-*.js`, 544 984 B gzip; `MapPage-*.js` borrado) | 408 passed, 2 skipped. Código 0: **no lo lee** | Sin falso rojo: "build + bundle" OK. `vite build` vacía `dist/`, que vuelve a tener `index-*.js` de 448 275 B y `MapPage-*.js`. Para comprobar que la manipulación se habría detectado, he lanzado `AVISABUS_BUNDLE_CHECK=1 vitest run …bundle-budget…` sin construir: 2 fallos (544 966 > 204 800, y Leaflet en `index-*.js`) |
| 3. `dist/` antiguo bueno y fuente que rompe el presupuesto (`import 'leaflet'` y ~133 KB aleatorios en `src/main.tsx`) | 408 passed, 2 skipped. Código 0: no lee `dist/` | Sin falso verde: **"frontend: build + bundle" FAIL** (284 291 > 204 800, y Leaflet en el trozo inicial). "frontend: format" también falla por la línea larga del cambio temporal |

Mutaciones del test del arnés (`:122`), en la misma copia:
- `e2e` vuelve a ser `playwright test && npm run test:bundle` → 1 fallo (detectada).
- Paso "build + bundle" movido dentro de `if $e2e; then` → 3 passed, 2 skipped (**no** detectada, N-1).

La copia quedó restaurada: `init.sh`, `package.json` y `src/main.tsx` son idénticos a `HEAD`
(`diff` con `git show`). El repositorio no se ha tocado: `git status` está limpio y solo se ha
regenerado `frontend/dist/` (ignorado por git) durante la verificación.

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` en el repositorio, con el puerto 4173 libre (`lsof -i :4173` vacío
antes y después). Código de salida 0, "verify: todo en verde":
- backend: format, lint, mypy y lint-imports OK. pytest: 988 passed, 6 deselected, cobertura
  99,46 %. Los 2 avisos de pytest ya existían.
- frontend: format, lint y typecheck OK. Vitest: 44 ficheros, **408 passed | 2 skipped** (los dos
  tests que leen `dist/`).
- frontend: **build + bundle** OK. `vite build` (`index-*.js` 448,27 kB, 141,49 kB gzip;
  `MapPage-*.js` 50,21 kB gzip) y luego `bundle-budget.test.ts` 5/5.
- frontend: e2e + a11y: 87 passed, sin reintentos ni fallos. Axe sin violaciones. Después del e2e
  ya no aparece ninguna ejecución de Vitest: `e2e` no encadena `test:bundle`.
- harness: `feature_list.json` OK. Trazabilidad AC→test OK.

## Decisiones locales del implementer (v1.3)

1. **Variable `AVISABUS_BUNDLE_CHECK=1` en el propio script `test:bundle`.** Cabe en el design: la
   nota de §5 la propone como ejemplo y deja el mecanismo como decisión local. La sintaxis
   `VAR=1 cmd` es POSIX. Vale en macOS, Linux y la Raspberry Pi, que son los entornos del proyecto.
2. **No tocar `vite.config.ts` (no se usa `exclude`).** Cabe. El design §5 cita "variable,
   `exclude` de Vitest, etc." como alternativas. Que `tasks.md` liste el fichero no obliga a
   cambiarlo. Además, gracias a esto los dos tests sintéticos (`:80`, `:103`) siguen corriendo en
   `npm run test` y no leen `dist/`.
3. **Con la variable y sin `dist/`, el test falla en vez de omitirse** (`builtDist()`,
   `bundle-budget.test.ts:30-36`). Cabe en la nota v1.3, que dice que sin la variable se omite.
   Con `test:bundle`, `dist/` siempre existe o el `&&` ya ha cortado. Es razonable y más estricto.
   La tabla de §5 sigue diciendo "si no existe `dist/`, el test se omite con aviso" (N-2).
4. **`webServer` de Playwright sin cambios** (`npm run build && npm run preview`). Con `--e2e` se
   construye dos veces, una en `test:bundle` y otra en el `webServer`. No es incorrecto: el e2e
   también prueba un build recién hecho. Solo cuesta unos segundos.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-1 (test del arnés, "con y sin `--e2e`").** `frontend/src/__tests__/bundle-budget.test.ts:133-135`:
  la regex `/run_step "frontend: build \+ bundle"\s+"\$FRONTEND" npm run --silent test:bundle\n/`
  no está anclada a su posición en `cmd_verify`. Si el paso se mete dentro de `if $e2e; then`, el
  test sigue en verde (mutación comprobada). Hoy `init.sh:66-67` lo ejecuta fuera del `if`, como
  pide AC-21 v1.3: el comportamiento es correcto y se ve en la salida de `verify`. Mejora posible:
  comprobar que la línea aparece antes de `if $e2e` y que no está indentada como el cuerpo del
  `if`. Tampoco se comprueba que `test` vaya antes que `test:bundle`.
- **N-2 (problema de spec menor, no requiere CP-3).** `specs/passenger_stop_view/design.md:201`
  (tabla de §5, fila AC-21) conserva el texto de la v1.0: "si no existe `dist/`, el test se omite
  con aviso". La nota v1.3 (`:205-211`) y el código ligan la omisión a la variable, no a la
  existencia de `dist/`. En la próxima revisión de la spec conviene cambiar la fila a "sin
  `AVISABUS_BUNDLE_CHECK` se omite con aviso; con ella, la ausencia de `dist/` es un fallo".
- **N-3 (propuesta para `docs/`, CP-4).** Hace falta en `docs/verification.md` y no en
  `docs/conventions.md`:
  - `docs/verification.md:26` (§2, fila "Build"): dice `npm run build`, pero el paso de `verify`
    es ahora "frontend: build + bundle" = `npm run test:bundle` (build y presupuesto de bundle,
    AC-21). Conviene cambiarlo a `npm run test:bundle` (build + presupuesto de JS inicial). La
    línea 29 ("`--e2e` añade `npm run e2e`") sigue siendo correcta. No es una contradicción que
    deba resolverse con CP-3: la spec v1.3, aprobada por la persona, fija el cambio de `init.sh`.
    El documento simplemente se ha quedado desfasado.
  - `docs/conventions.md` §8: **no es necesario**. La tabla no tiene fila de build. La fila
    "E2E + a11y: `npm run e2e`" sigue siendo exacta. Añadir una fila "Presupuesto de bundle:
    `npm run test:bundle`" sería opcional.
  Lo decide la persona (CP-4). No bloquea la feature.

### Otras comprobaciones (§4 de `docs/verification.md`)
- Alcance: `git diff origin/develop..HEAD` solo toca `frontend/package.json`, `init.sh`,
  `bundle-budget.test.ts`, `progress/` y `feature_list.json`. El orquestador cambió los dos últimos
  y el implementer solo `progress/impl_passenger_stop_view.md`. No hay cambios fuera del alcance de
  T-13 ni en `specs/` o `docs/`.
- Arquitectura, privacidad, i18n y accesibilidad: no aplican (no hay código de producción ni
  textos nuevos). El aviso de consola está en inglés, como el resto del código.
- Tests: sin red ni reloj. Los tests sintéticos usan directorios temporales que se borran en
  `afterEach`.
- Commits: `test(passenger_stop_view): … (T-13)` cumple Conventional Commits con el ámbito de la
  feature y cita la tarea.

---

# Revisión: passenger_stop_view — v1.2
Ciclo: 1 (v1.2) · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/passenger_stop_view/` v1.2 (APPROVED, PR #29) · Rama: `feat/passenger_stop_view-v1.2`
Alcance revisado: T-12 (`e665d86`), su registro (`b0ad197`) y los commits del orquestador
(`27e4707`, `54bd2a9`). También se ha comprobado que no hay regresiones en el resto de AC.

## Veredicto: APPROVED

Las dos novedades de AC-24 v1.2 tienen tests que verifican de verdad el comportamiento: el foco
se comprueba con `document.activeElement` y la ausencia de anuncios con las regiones `aria-live`
del `Announcer`. Las 13 mutaciones aplicadas en una copia se detectan todas.
`CI=1 ./init.sh verify --e2e` está en verde. Las cuatro decisiones locales caben en la spec y en
el design. La decisión 2 cambia algo visible: un estado intermedio que ningún AC regula. No hace
falta CP-3, pero conviene recogerla en el design en la próxima revisión de la spec (N-9).

## Matriz AC → evidencia

Solo se detallan AC-24 (v1.2) y los AC relacionados (AC-16, AC-18). El resto de la matriz es el
de las secciones v1.1 y v1.0 de este fichero. Esos AC siguen en verde con los mismos tests. El
diff del fichero de tests solo **añade** casos (`StopPage.errors.test.tsx:337-544`) y no modifica
ninguno existente.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-24 (v1.2) 404 en acción manual | `StopPage.errors.test.tsx:341` (5 casos: "Actualizar"/"Actualitza"; "Reintentar" tras fallar las llegadas o la parada; "Reintenta" en `ca`) | OK | `press()` pone el foco en el botón antes del clic. Tras el 404 se comprueba que el `h1` es "Parada no encontrada"/"Parada no trobada", que `document.activeElement === h1` y que **todas** las regiones `aria-live` están vacías. El `Announcer` no borra los mensajes, así que esta última aserción es real: la mutación M6 (anunciar `stop.refreshFailed` antes de salir) la rompe. El caso de "Reintentar" tras fallar la parada pasa por `stop.refetch()` (AC-17). |
| AC-16 / AC-24 404 al cargar | `:388` | OK | El foco sigue en `body`. Con la mutación M2 (enfocar el `h1` siempre) el test falla. Sin token, `StopPage.tsx:60` monta `StopNotFound` sin `focusHeading`. Además, `usePageTitle` no mueve el foco porque la ubicación no cambia (`frontend_i18n.AC-11`, solo navegación). |
| AC-16 (regresión) | `:91` (es/ca, sin `stop_id` ni token), `:118` y siguientes; e2e `stop-not-found-*` | OK | El `h1` con `tabIndex=-1` no cambia el contenido ni el aspecto (captura `pixel/stop-not-found-es.png`). Axe sin violaciones. |
| AC-24 (v1.2) refresco automático con éxito | `:399` (es/ca), `:423` (tras un "Actualizar" fallido, sin "Datos actualizados"), `:442` (sin datos, petición automática en curso controlada con `deferred`), `:468` (sin datos y sin conexión), `:493` (2 casos: "Reintentar" desaparece antes de que exista "Actualizar"), `:528` (sin foco en "Reintentar" no se mueve) | OK | Se comprueba que "Reintentar" ya no existe, que el foco está en "Actualizar"/"Actualitza" y que las regiones vivas están vacías (sin anuncio, AC-15). `:442` comprueba que el aviso y el foco siguen **durante** la petición automática (4.ª llamada) y que pasan a "Actualizar" al resolverse. `:528` evita una implementación que mueva el foco siempre (mutación M11). |
| AC-24 (v1.1, regresión) | `:240`, `:261`, `:291`, `:323` (sin cambios) | OK | Siguen en verde. Tras un "Reintentar" con éxito llegan dos peticiones de foco a "Actualizar": la de `finish()` y la de `RetryAction` (`lost`). Las dos llevan al mismo sitio y la segunda se descarta porque el foco ya no está en `body`. |
| AC-18 (regresión y combinación) | `:468`, `:546` y siguientes (sin cambios); e2e `stop-offline-*` | OK | Sin conexión no hay peticiones: en `:468` la petición queda en pausa (`fetchStatus: 'paused'`). Ahora, si no hay datos y había un error, se ven a la vez "Sin conexión" (`role="status"`) y el aviso de error. Con datos antiguos ya era así. AC-18 no lo prohíbe. |
| AC-15 (regresión) | `:323`, `:399`, `:423`, `:442`, `:468` | OK | Ni el foco perdido ni el aviso que se mantiene generan anuncios. `finish()` sigue llamándose solo desde `refresh()`/`retry()`. |

La parte "manual (lector de pantalla en CP-6)" de AC-24 queda para la persona. Los dos guiones
están en `progress/impl_passenger_stop_view.md`, en "Observaciones".

### Mutaciones (copia en el scratchpad; el repositorio no se ha tocado)
Se ejecutaron `StopPage.test.tsx` y `StopPage.errors.test.tsx` (47 tests) con una mutación cada
vez. La línea base pasa 47/47.

| Mutación | Tests que fallan |
|---|---|
| M1 `StopNotFound` sin `focus()` | 5 (todos los de 404 manual) |
| M2 `StopNotFound` enfoca siempre | 1 (`:388`, 404 al cargar) |
| M3 `h1` sin `tabIndex={-1}` | 5 |
| M4 `refresh()` sin salida por 404 | 2 ("Actualizar"/"Actualitza") |
| M5 `retry()` sin salida por 404 | 3 |
| M6 404 manual anuncia `stop.refreshFailed` | 2 |
| M7 `showError` sin `isRetryingAfterError` | 2 (`:442`, `:468`) |
| M8 `RetryAction` no avisa al desmontarse | 6 |
| M9 `RetryAction` con `useEffect` en lugar de `useLayoutEffect` | 6 (la decisión 1 es necesaria: en la limpieza pasiva el nodo ya no está en el DOM) |
| M10 sin la salvaguarda de "foco movido" | 1 (`:493`, la persona movió el foco) |
| M11 `RetryAction` avisa sin comprobar el foco | 1 (`:528`) |
| M12 el foco perdido va a "Reintentar" | 6 |
| M13 404 en "Actualizar" llama a `onManualNotFound` pero sigue a `finish()` | 2 |

La copia se restauró y se comparó con `diff -r` contra `frontend/src`: son idénticas.

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` con el puerto 4173 libre (`lsof` vacío antes de empezar). Código de
salida 0, "verify: todo en verde":
- backend: format, lint, mypy y lint-imports OK. pytest: 969 passed, 6 deselected, cobertura
  99,39 %. Los 2 avisos de pytest ya existían y no son de esta feature.
- frontend: format, lint (con i18n) y typecheck OK. Vitest: 35 ficheros, **301 tests passed**
  (287 en la v1.1, +14 de T-12). Build OK (`index-*.js` 441,37 kB, **139,25 kB gzip**; el
  presupuesto de AC-21 es 200 KB).
- e2e + a11y: 60 passed, sin reintentos. Axe sin violaciones. `test:bundle`: 2 passed.
- harness: `feature_list.json` OK. Trazabilidad AC→test OK (AC-24 se cita en 12 bloques de test
  de `StopPage.errors.test.tsx`).

Otras comprobaciones:
- **Alcance:** `origin/develop` es ancestro de `HEAD`. `e665d86` solo toca los ficheros de T-12
  (`StopPage.tsx`, `StopNotFound.tsx`, `StopPage.errors.test.tsx`). `b0ad197` solo toca
  `progress/impl_passenger_stop_view.md`. `27e4707` y `54bd2a9` son del orquestador
  (`feature_list.json`, `progress/current.md`, `progress/history.md`). No hay cambios en
  `docs/`, `specs/`, `backend/` ni `e2e/`. Los commits siguen Conventional Commits con el ámbito
  de la feature y citan la tarea.
- **i18n:** no hay claves nuevas: el `h1` ya existía en es/ca. No hay literales, según el lint
  de i18n.
- **Privacidad:** no se registra nada y no hay anuncios con identificadores.
- **Accesibilidad:** el foco programático en un `h1` no interactivo sin contorno sigue el patrón
  ya aprobado en `frontend_i18n` (`index.css:50-51`, `usePageTitle.ts:32`). Los botones siguen
  con el foco visible de §5.5.
- **AC-23:** T-12 no cambia la maquetación. `RetryAction` pinta el mismo `<div className="flex">`
  que antes. Revisada la captura regenerada `frontend/test-results/passenger_stop_view/pixel/stop-not-found-es.png`
  (11:10): igual que en la v1.1.

## Decisiones locales del implementer (v1.2)

1. **`RetryAction` comprueba el foco en la limpieza de un `useLayoutEffect`**
   (`StopPage.tsx:91-107`). Cumple literalmente el design v1.2 ("se detecta con
   `document.activeElement` antes de desmontar el aviso"). React ejecuta las limpiezas de layout
   de un subárbol eliminado antes de quitar sus nodos del DOM. La mutación M9 lo demuestra: con
   `useEffect` fallan 6 tests. La comprobación se hace con `contains(document.activeElement)`, de
   modo que no se pide foco si "Reintentar" no lo tenía (M11). **Aceptada.**
2. **El aviso de error se mantiene durante los reintentos automáticos sin datos**
   (`StopPage.tsx:47-52,139-143`, `isPending && fetchStatus !== 'idle' && errorUpdateCount > 0`).
   - *Efecto visible:* sin datos y con error, antes el aviso desaparecía al **empezar** cada
     petición automática (cada 20 s, al reconectar o al volver el foco a la ventana). Durante
     unos 3 s (con los reintentos de 1 s y 2 s) se veía "Cargando las próximas llegadas…" y
     luego volvía el aviso. Ahora el aviso sigue hasta que llegan los datos. Sin conexión se ve
     junto a "Sin conexión".
   - *¿Cabe en la spec?* Sí:
     - Ningún AC ni el design regulan el texto de carga durante un reintento. "Cargando…" solo
       existe como estado de la carga inicial.
     - AC-17 pide mostrar el mensaje con "Reintentar" cuando hay un error, y el reintento
       automático no lo resuelve hasta que acierta.
     - AC-24 v1.2 equipara expresamente "el aviso de error desaparece" con que el refresco
       acierte, y el design dice "antes de desmontar el aviso". Con el comportamiento anterior,
       el botón enfocado se desmontaba al empezar la petición: el foco caía en `body` antes de
       conocer el resultado y, si fallaba, se quedaba allí. Así no se podía cumplir AC-24.
     - Es la misma solución que se aceptó en la v1.1 para el "Reintentar" manual (decisión 1
       de la v1.1), y coherente con el principio de AC-12 de no borrar lo que hay mientras llegan
       datos nuevos.
     - Se usa `errorUpdateCount > 0` porque, en TanStack Query v5, una consulta sin datos vuelve
       a `pending` sin `error` al pedirse de nuevo. Así la condición solo se cumple tras un fallo
       y no afecta a la carga inicial.
   - *Veredicto:* **aceptada, sin CP-3**. No contradice ningún nivel de la jerarquía y es la
     forma mínima de cumplir AC-24 v1.2. Como cambia algo que ve una persona vidente, propongo
     documentarlo en el design en la próxima revisión de la spec (N-9).
3. **El foco solo se mueve si sigue en `body`** (`StopPage.tsx:155-168`). La guarda solo actúa
   en las peticiones `lost`. En el caso normal no interviene: el aviso desaparece, el foco cae en
   `body` y el efecto lo lleva a "Actualizar" en el mismo ciclo. Solo actúa si "Actualizar" aún
   no existe (falló solo la parada y las llegadas siguen en camino) y la persona ha enfocado otra
   cosa mientras tanto. No quitarle el foco es coherente con la decisión 2 de la v1.1 y con el
   objetivo de AC-24 (no desorientar). Está probado en los dos sentidos (`:493`, M10).
   **Aceptada.**
4. **`h1` con `tabIndex={-1}`** (`StopNotFound.tsx:30`). Es literal del design v1.2 ("`h1` de
   `StopNotFound` (`tabIndex=-1`, `focus()` al montarse si venía de una acción manual)"). El
   `focus()` se hace en un `useEffect` sobre `focusHeading`, no solo al montarse. Así funciona
   aunque `StopNotFound` se monte (al notificar la consulta) antes de que se resuelva la promesa
   del `refetch()` que activa `manualNotFound`. Es equivalente al design y más robusto.
   **Aceptada.**

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-9 (nota para la próxima revisión de la spec, no es CP-3):** el design §2 (tabla v1.2) no
  dice que el aviso de error se mantiene durante los reintentos automáticos sin datos
  (`StopPage.tsx:136-143`). Es un cambio visible respecto a la v1.1: ya no aparece "Cargando…"
  durante el reintento y se ven a la vez el aviso de error y "Sin conexión". Propuesta: añadir una
  línea a la tabla de "Acciones manuales: anuncio y foco" o a la estructura de la vista, para que
  CP-6 lo valide con conocimiento de causa.
- **N-10 (hueco de spec menor, ya anotado por el implementer):** un 404 de un refresco
  **automático** con el foco en "Reintentar" deja el foco en `body` (`StopPage.tsx:71-73`
  sustituye la vista entera). AC-24 solo regula el 404 de las acciones manuales, así que el
  código cumple. Si se quiere cubrir, bastaría con extender el `focusHeading` a ese caso en una
  versión futura. El caso es muy raro: requiere reimportar el GTFS con la vista abierta.
- **N-11 (tests):** no hay caso `ca` para "Reintenta" tras fallar la parada con 404 (`:341`), y
  el caso del refresco automático en `ca` solo cubre el fallo de las llegadas. Son combinaciones
  redundantes: los textos y el camino de código ya se cubren en otros casos. No hace falta
  añadirlas.
- Siguen abiertas las observaciones de la v1.1 que no dependen de T-12 (por ejemplo, la propuesta
  de que `Button` acepte `ref` para quitar los envoltorios `div`).

---

# Revisión: passenger_stop_view — v1.1
Ciclo: 1 (v1.1) · Fecha: 2026-11-03 · Agente: reviewer
Spec: `specs/passenger_stop_view/` v1.1 (APPROVED, PR #24) · Rama: `feat/passenger_stop_view-v1.1`
Alcance revisado: T-11 (`fd1825d`) y su registro (`872bcc4`); comprobación de regresiones en el resto de AC.

## Veredicto: APPROVED

AC-17 (v1.1) y AC-24 tienen tests que verifican de verdad el comportamiento: anuncio educado
en la región `aria-live="polite"` del `Announcer` y foco comprobado con `document.activeElement`.
`CI=1 ./init.sh verify --e2e` está en verde y los demás AC no tienen regresiones. Las cuatro
decisiones locales caben dentro del design. Lo que pasa tras un 404 en una acción manual es un
hueco de la spec. No bloquea y no requiere CP-3: queda como nota para la siguiente revisión de
la spec.

## Matriz AC → evidencia

Solo se detallan los AC que cambian en la v1.1. El resto de la matriz (AC-01…AC-16, AC-18…AC-23)
sigue siendo la de la sección v1.0 de este fichero. Siguen en verde con los mismos tests, y
ninguno de esos tests se ha tocado salvo para cambiar el texto del mensaje de error.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-17 | `StopPage.errors.test.tsx:141` (503 y error de red al cargar las llegadas), `:166` (fallan parada y llegadas; "Reintentar" pide la parada otra vez: 4 llamadas), `:186` (datos conservados, es/ca), `:210` (**solo falla la parada**), `:231` (texto en `ca`), `:323`; e2e `stop-error-stale` | OK | En `:210` se ven las llegadas, el aviso dice "No se han podido cargar los datos." sin mencionar "las llegadas", y "Reintentar" pide `/stops/508` por cuarta vez y pinta el `h1` real. Sin `stop.refetch()` el test fallaría porque `useStop` tiene `staleTime: Infinity` y no se refresca solo. Textos es/ca hablan de "los datos"/"les dades". Cumple también el design ("Reintentar" pide siempre las llegadas y la parada solo si su error está activo, `StopPage.tsx:123-131`). |
| AC-24 | `StopPage.errors.test.tsx:240` ("Actualizar" con error, es/ca), `:261` ("Reintentar" con éxito tras fallo de llegadas, de parada o de un refresco), `:291` ("Reintentar" con error, llegadas o parada, con petición pendiente controlada por `deferred`), `:323` (refresco automático fallido sin anuncios) | OK | Las tres viñetas del AC están cubiertas. Las aserciones no son tautológicas: (1) tras "Actualizar" con error, `activeElement` es "Reintentar"/"Reintenta" y "Actualizar" ya no existe, así que sin `setFocusRequest` el foco quedaría en `body`; (2) tras "Reintentar" con éxito, `activeElement` es "Actualizar" (en el caso "parada", "Actualizar" ya estaba pintado y lo que se comprueba es el movimiento); (3) "Reintentar" con error: se compara con el botón **actual**, así que si el aviso se desmontara durante la petición (el problema de `pending` de TanStack Query v5) el foco caería en `body` y el test fallaría; además se comprueba el foco **durante** la petición. Los anuncios se leen en la región polite: "No se han podido actualizar los datos" / "No s'han pogut actualitzar les dades" / "Datos actualizados", y antes de la acción se comprueba que la región está vacía. La parte "manual (lector de pantalla en CP-6)" queda para la persona. |
| AC-14 (regresión) | `StopPage.test.tsx` (sin cambios) | OK | "Actualizar" con éxito sigue anunciando "Datos actualizados" solo al terminar (`finish('refresh', false)`). Según el design, el foco "se queda": no se llama a `focus()`. |
| AC-15 (regresión) | `useArrivingAnnouncements.test.tsx`, `StopPage.test.tsx`, `StopPage.errors.test.tsx:323` | OK | `finish()` solo se llama desde `refresh()`/`retry()`, que solo se ejecutan con un clic; los refrescos automáticos no pasan por ahí. |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre antes de empezar), código de salida 0, "verify: todo en verde":
- backend: format, lint, mypy y lint-imports OK (2 contratos respetados, 0 rotos); pytest 969 passed,
  6 deselected, cobertura 99,39 %.
- frontend: format, lint (con i18n) y typecheck OK; Vitest 35 ficheros, 287 tests passed; build OK
  (`index-*.js` 440,58 kB, **138,96 kB gzip**, presupuesto de AC-21: 200 KB).
- e2e + a11y: 60 passed, sin reintentos ni tests inestables; axe sin violaciones; `test:bundle` 2 passed.
- harness: `feature_list.json` OK; trazabilidad AC→test OK (AC-24 citado en 9 casos).

Otras comprobaciones:
- Paridad de claves es/ca-valencia (script sobre los dos `translation.json`): mismas claves en
  los dos idiomas. `stop.refreshFailed` es el literal de AC-24 en `es` y "No s'han pogut
  actualitzar les dades" en `ca`. `stop.error.body` es "**No se han podido cargar los datos.** …" /
  "**No s'han pogut carregar les dades.** …". No queda ninguna referencia al texto antiguo en
  `src/` ni en `e2e/`.
- `frontend/src/shared/device/storage.ts:1-6`: el comentario coincide con `docs/conventions.md` §4 v1.2
  (`device_id`, idioma, perfil de accesibilidad y última parada con `stop_id`, nombre y token del
  QR público; cita AC-19). N-3 de la v1.0 resuelto.
- Alcance (`git log origin/develop..HEAD`, `git show --stat` por commit): `fd1825d` solo toca los
  ficheros de T-11 (`StopPage.tsx`, `StopPage.errors.test.tsx`, los dos `translation.json` y
  `storage.ts`). `872bcc4` solo toca `progress/impl_passenger_stop_view.md`. `564c760` y `c97b7a3`
  son del orquestador (`feature_list.json`, `progress/current.md`, `history.md`). Los cambios de
  `docs/` y `specs/` vienen de `690a6a5` (rama `specs/ajustes-bloque-2`, PR #24). El merge
  `a43d57f` no añade nada fuera de `develop` y de esa rama (`git diff origin/develop..HEAD` solo
  muestra esos ficheros) y `origin/develop` es ancestro de `HEAD`. Commits en Conventional Commits
  con el ámbito de la feature y la tarea citada. Sin variables de configuración nuevas.
- Privacidad: no se registra nada; los anuncios no llevan identificadores.

### Revisión visual (AC-23)
Hay cambios de aspecto: el texto del aviso de error y el `<div className="flex">` que envuelve
los botones. Revisadas las capturas regeneradas a las 23:28 en
`frontend/test-results/passenger_stop_view/`: `pixel/stop-error-stale-es.png` y
`tablet-landscape/stop-realtime-es-refresh-focused.png`. El aviso de error sigue §5.6 (fondo
`accent-surface`, borde 2 px `accent`, icono de información, primera frase en negrita hasta el
punto, "Reintentar" como botón secundario con icono). "Actualizar" sigue alineado a la derecha
con el contorno de foco de §5.5. El envoltorio no cambia la maquetación ni el tamaño táctil y no
hay desbordamientos.

## Decisiones locales del implementer (v1.1)

1. **El aviso se mantiene durante "Reintentar"** (`StopPage.tsx:80`, `showError = failed ||
   manualAction === 'retry'`). Es necesario: en TanStack Query v5, una consulta sin datos vuelve a
   `status: 'pending'` sin `error` al pedirla otra vez. Sin esto, el botón enfocado se desmontaría
   y AC-24 ("el foco sigue en Reintentar", "nunca en `body`") no se cumpliría. Mientras tanto no
   se muestra "Cargando…", lo cual es coherente. El test `:291` lo cubre durante la petición.
   **Aceptada.**
2. **El foco solo se mueve si desaparece el botón enfocado** (`StopPage.tsx:92-100,111-112`).
   Coincide con la tabla del design ("se queda en …" para Actualizar con éxito y Reintentar con
   error) y respeta el foco si la persona lo ha movido mientras esperaba. El efecto depende de
   `showError`/`showRefresh` y se ejecuta una sola vez por petición (`focusDone`), así que
   aguanta que TanStack Query notifique el nuevo estado después de resolver la promesa.
   **Aceptada.**
3. **`ref` en un `div` envolvente**: `ButtonProps` extiende `ButtonHTMLAttributes`, que no
   incluye `ref`. En React 19 funcionaría en ejecución, pero no compila sin tocar
   `shared/ui/Button.tsx` (de `frontend_i18n`, fuera de los ficheros de T-11). La solución respeta
   el alcance y no cambia el aspecto (capturas). **Aceptada.** Propuesta no bloqueante para una
   tarea futura: aceptar `ref` en `Button` y quitar el envoltorio.
4. **Se ignoran los clics extra durante una acción manual** (`StopPage.tsx:116,124`). Es
   razonable: un segundo `refetch()` con `cancelRefetch` cancelaría el primero y podría anunciar
   "Datos actualizados" antes de tiempo. Hay un efecto secundario sin importancia: si fallan solo
   la parada y hay un "Actualizar" en curso, un clic en "Reintentar" se ignora sin aviso. Ningún
   AC lo cubre. **Aceptada.**

## Observación del implementer: 404 en una acción manual

Es un **problema de spec**, pero menor: no hace falta CP-3 ahora, basta una nota para la siguiente
revisión de la spec. Si "Actualizar" o "Reintentar" terminan en 404, AC-16 obliga a sustituir la
vista por "Parada no encontrada" (`StopPage.tsx:49` desmonta `StopContent`). Entonces no existe el
"Reintentar" al que AC-24 manda el foco y la regla "nunca en `body`" no se puede cumplir sin
inventar un destino. El implementer no ha inventado comportamiento: anuncia
`stop.refreshFailed`, que es la parte aplicable, y deja el foco donde lo deja el cambio de página.
No pido CP-3 porque el caso es muy raro (hace falta reimportar el GTFS con la vista abierta),
ningún flujo principal queda bloqueado y el código no contradice nada que se pueda cumplir.
Propuesta para la v1.2: tras un 404 en una acción manual, mover el foco al `h1` "Parada no
encontrada" (con `tabIndex=-1`) y quizá no anunciar `stop.refreshFailed`, porque la página nueva
ya lo explica.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-7 (problema de spec, accesibilidad)**: el 404 en una acción manual (ver arriba). Nota para la
  siguiente revisión de la spec (spec-writer), sin CP-3.
- **N-8 (hueco de spec, accesibilidad)**, `StopPage.tsx:80-81` y `useStopQueries.ts:45-48`: tras
  un "Actualizar" fallido el foco queda en "Reintentar". Si después un refresco **automático**
  acierta (el `refetchInterval` sigue activo con error ≠ 404, o al volver la conexión), el aviso se
  desmonta y el foco cae en `body` sin anuncio. Es más probable que el caso del 404. AC-24 solo
  regula el final de las acciones manuales, así que el código cumple la spec. Propuesta para la
  v1.2: si el control enfocado desaparece por un refresco automático, llevar el foco a
  "Actualizar". Conviene que la persona lo pruebe en CP-6 con lector de pantalla.
- **N-9**, `progress/impl_passenger_stop_view.md:148-170,174`: el registro del implementer tiene
  restos de la v1.0. "Desviaciones respecto al design" presenta como pendientes las 4 que ya
  resolvió la v1.1 (design §2, `docs/design.md` §4/§5.6 y conventions §4). "Textos nuevos para
  revisar" cita el `stop.error.body` antiguo ("…cargar las llegadas…") y no incluye
  `stop.refreshFailed` en `ca`. Solo es documentación, pero la persona usará esa lista en CP-6.
- **N-10**, `StopPage.tsx:69` + `shared/ui/Button.tsx`: decisión 3. Cuando una tarea lo permita,
  hacer que `Button` acepte `ref` y quitar los dos `div` envolventes.
- Pendientes de la v1.0 que T-11 no tocaba: N-5 y N-6 siguen abiertos. N-1, N-2, N-3 y N-4 quedan
  resueltos con la v1.1 (AC-24, AC-17, `storage.ts`, `docs/` en la PR #24).

---

# Revisión: passenger_stop_view — v1.0
Ciclo: 1 · Fecha: 2026-11-03 · Agente: reviewer
Spec: `specs/passenger_stop_view/` v1.0 (APPROVED) · Rama: `feat/passenger_stop_view` (11 commits sobre `develop`)

## Veredicto: APPROVED

Los 23 AC tienen tests que verifican el comportamiento descrito; `CI=1 ./init.sh verify --e2e`
está en verde; las capturas cumplen `docs/design.md`. Ningún hallazgo es bloqueante. Hay una
contradicción entre `docs/conventions.md` §4 y AC-19 que la propia conventions resuelve a favor
de la spec: no bloquea, pero la persona debe actualizar `docs/` (CP-4).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `backend/tests/integration/test_cli_openapi.py` (4 tests) | OK | URL de BD apuntando a un fichero que se comprueba que no existe; sockets bloqueados por pytest-socket; comprueba que no se importa `avisabus.main`; salida estable (`indent=2`, claves ordenadas, salto final); funciona con `AVISABUS_ENV=prod` sin secreto. |
| AC-02 | `backend/tests/integration/test_openapi_snapshot.py` (4 tests) | OK | Compara la copia real del frontend; con una copia desfasada o ausente falla pidiendo `npm run gen:api`. La comparación es por valor JSON porque Prettier reformatea el fichero; es razonable. |
| AC-03 | `frontend/src/shared/api/__tests__/client.test.ts` (8 tests) | OK | 200 tipado, problem+json 404/503 → `status`/`type`, cuerpo no problem → `type: null`, error de red y timeout de 8 s con temporizadores falsos (el 7 999 ms no resuelve) → `ApiError(0,'network')`. |
| AC-04 | `StopPage.test.tsx` (es/ca), `e2e/stop-view.spec.ts:123` | OK | `h1` con `lang="ca-ES-valencia"`, "Parada 508", líneas sin duplicar, título `… · AvisaBus`, URL pedida con el token. |
| AC-05 | `destination.test.ts` (3 casos), `ArrivalRow.test.tsx`, `ArrivalsList.test.tsx` | OK | Frase accesible exacta del AC; destino visible del SAE y hablado del GTFS; los tres casos de la spec (tiempo real con y sin sentido, horario programado); parte visual con `aria-hidden`; orden de la API. |
| AC-06 | `ArrivalTime.test.tsx` | OK | "N min" (1/4/25), "Llegando"/"Arribant" con 0, `HH:MM` en Europe/Madrid. |
| AC-07 | `OccupancyInfo.test.tsx`, `ArrivalRow.test.tsx` | OK | Texto e icono (1/2/3/0 siluetas rellenas) en es/ca, `null` → "Ocupación no disponible", colores de §4 solo como refuerzo. |
| AC-08 | `ArrivalRow.test.tsx:91` | OK | N4: hora, sin ocupación ni silueta, sin botones ni enlaces. |
| AC-09 | `SourceNotice.test.tsx`, `ArrivalTime.test.tsx:63`, `ArrivalsList.test.tsx:27`, e2e | OK | `role="status"` con el texto literal (es/ca); "programado" en pantalla y en la frase de cada llegada. |
| AC-10 | `ArrivalsList.test.tsx:40` (es/ca), e2e | OK | |
| AC-11 | `shared/color/__tests__/contrast.test.ts`, `LineBadge.test.tsx` | OK | WCAG con tokens de §4, `#FE0000`→`#e50000` (≥ 4,5:1), oscurecimiento por pasos, respaldo negro/blanco, neutro con color nulo o inválido. |
| AC-12 | `StopPage.test.tsx:134,158,170` | OK | Nueva petición a los 20 s (no a los 19,999 s), tope de 30 s, la lista se conserva mientras la petición está pendiente (deferred), pausa con la pestaña oculta, petición inmediata al volver y reanudación. |
| AC-13 | `useServerNow.test.tsx`, `ArrivalTime.test.tsx` (`currentMinutes`), `StopPage.test.tsx:188` | OK | El test integrado pone el reloj del dispositivo 2 min adelantado: sin la corrección mostraría "2 min" y fallaría. Tic de 15 s comprobado en el límite. |
| AC-14 | `StopPage.test.tsx:211,257` | OK | "Actualizado a las 08:40:00"; el botón lanza la petición; "Datos actualizados" solo se anuncia cuando llega la respuesta (no mientras está pendiente); los refrescos automáticos no se anuncian. |
| AC-15 | `useArrivingAnnouncements.test.tsx` (10), `StopPage.test.tsx:234,257`, `StopPage.errors.test.tsx:195` | OK | Un anuncio educado con el headsign, sin repetirlo; silencio en los refrescos rutinarios y en los fallidos; solo la primera llegada de cada grupo. |
| AC-16 | `StopPage.errors.test.tsx:81,104,116`, e2e `:185` | OK | 404 de la parada o de las llegadas (es/ca); `main` sin `stop_id` ni token; sin token no se llama a la API; un 404 no se reintenta. |
| AC-17 | `StopPage.errors.test.tsx:126,151,171`, e2e `:207` | OK | 503 y error de red con "Reintentar" (tras 2 reintentos); datos conservados con "Datos de las 08:40, pueden no estar actualizados" (es/ca). |
| AC-18 | `useOnline.test.tsx`, `StopPage.errors.test.tsx:209,230`, e2e `:231` | OK | `role="status"`, ninguna petición en 120 s sin conexión, petición al volver; si se abre sin conexión no se llama a la API. |
| AC-19 | `lastStop.test.ts`, `StopPage.test.tsx:109,123`, `HomePage.test.tsx:58-101`, e2e `:249` | OK | Guarda `stop_id`, nombre y token al cargar (no tras un 404); enlace "Tu última parada: …" (es/ca) con la URL codificada. |
| AC-20 | `NotFoundPage.test.tsx`, e2e `:267` | OK | `/no-existe`, `/p`, `/p/508/otra`; el enlace lleva a la portada. |
| AC-21 | `src/__tests__/bundle-budget.test.ts` | OK | Cálculo comprobado con un `dist` sintético; en `test:bundle`, encadenado a `e2e`, se midió el `dist/` real: 138,73 KB gzip de un máximo de 200 KB. |
| AC-22 | `e2e/stop-view.spec.ts` | OK | Tiempo real, horario programado, sin llegadas y no encontrada × es/ca × iPhone 14, Pixel 7 e iPad landscape; axe con las etiquetas WCAG 2.1 A/AA sin violaciones. Hay axe también en error, sin conexión, portada y 404 genérico. |
| AC-23 | Capturas `frontend/test-results/passenger_stop_view/{iphone,pixel,tablet-landscape}/` | OK | Ver "Revisión visual". |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre), código de salida 0, "verify: todo en verde":
- backend: format, lint, mypy y lint-imports OK (2 contratos respetados, 0 rotos); pytest 861 passed,
  6 deselected, cobertura 99,66 %.
- frontend: format, lint (con i18n) y typecheck OK; Vitest 35 ficheros y 278 tests passed; build OK
  (`index-*.js` 439,79 kB, 138,73 kB gzip).
- e2e + a11y: 60 passed y 0 reintentos (Playwright CI tiene `retries: 1`; no se usó ninguno).
  `test:bundle` 2 passed.
- harness: `feature_list.json` OK; trazabilidad AC→test OK.

Alcance (`git diff develop...HEAD --stat`): todo está dentro de los ficheros de `tasks.md` o es
soporte directo de los tests (`src/test/render.tsx`, `src/test/mockApi.ts`, fixtures). Los cambios de
`feature_list.json` y `progress/current.md`/`history.md` los hizo el orquestador. Los commits siguen
Conventional Commits con el ámbito de la feature y citan la tarea. No hay variables de configuración
nuevas.

### Revisión visual (AC-23)
Revisadas en los tres perfiles: `stop-realtime-es`, `stop-scheduled-ca`, `stop-error-stale-es`
(pixel), `stop-realtime-es-refresh-focused` (tablet), `stop-offline-es`, `stop-not-found-ca` y
`home-last-stop-es`. Comparadas con `docs/design.md`:
- §3: Atkinson Hyperlegible autoalojada (cero con barra). `h1` grande, `h2` "Próximas llegadas",
  rótulo "LÍNEAS" en mayúsculas `text-muted`, cifra del tiempo grande con "min" más pequeño,
  "hacia" en pequeño `text-muted` sobre el destino en negrita, "programado" pequeño bajo la hora.
- §4: insignias FREE, MEDIUM, FULL y `null` con sus fondos y textos. El rojo EMT está corregido; N4 lleva el
  estilo neutro.
- §5.2 y §5.3: distintivos con radio y tamaños de lista y tarjeta; tarjeta con borde, radio y la
  fila 1 (distintivo, destino, tiempo) y la fila 2 (insignia a todo el ancho); N4 sin fila 2.
- §5.4: icono de tres siluetas (relleno o contorno según el nivel) y "**Nivel** · asientos".
- §5.5: "Actualizar" y "Reintentar" como botones secundarios con icono a la izquierda y texto
  visible; foco de 3 px `accent` con separación.
- §5.6: avisos con fondo `accent-surface`, borde 2 px `accent`, icono de información y la primera
  frase en negrita.
- Principio 5: en la tablet el contenido se centra en una columna de unos 640 px.
- No vi desbordamientos ni texto cortado. "Ocupación media · hay asientos libres" pasa a dos
  líneas en el iPhone, lo cual es aceptable.

## Desviaciones declaradas por el implementer

1. **`openapi-typescript` 7.13 con TypeScript 6 mediante `overrides`**: cumple AC-03 y el design §2,
   que pide la generación con `openapi-typescript`. El override está limitado a ese paquete; los
   tipos generados están versionados, `tsc` los valida y el test de desfase protege el contrato.
   Es deuda técnica, no un problema de spec. **No bloqueante.** Recomendación: anotarlo en el
   design en la próxima revisión y quitar el override cuando haya una versión compatible con TS 6.
2. **Rojo EMT `#e50000` en vez de `#E40000`**: es lo que da el algoritmo del design §3 (pasos de
   5 puntos de L en HSL) y tiene 4,85:1 con blanco, por encima de 4,5:1. La guía §4 dice "en torno a
   `#E40000` (4,9:1)" y "no se fija ningún color de línea en el código". Cumple AC-11 y la guía.
   **No bloqueante**, no requiere CP-3. Si la persona quiere precisión, puede cambiar la guía a
   "`#E50000` (4,8:1)" (CP-4).
3. **Texto del aviso de horario programado**: el texto es comportamiento y en eso manda la spec
   (`docs/design.md` §1: "qué se muestra… con qué texto"), así que el literal de AC-09 es correcto.
   La negrita hasta los dos puntos respeta la intención de §5.6 (destacar el inicio). Cumple el AC y
   cabe en la guía. **No bloqueante.** Para que el ejemplo de §5.6 coincida con AC-09, se puede
   ajustar uno de los dos en una revisión futura; no hace falta CP-3.
4. **`avisabus.lastStop` en `localStorage` frente a `docs/conventions.md` §4**: **sí hay una
   contradicción** entre `docs/` y la spec. Conventions §4 dice que en `localStorage` solo se
   guardan `device_id`, idioma y perfil de accesibilidad. AC-19 obliga a guardar `stop_id`, nombre y
   token, y el design §3 fija la clave `avisabus.lastStop` y el uso de `safeStorage`. **No bloquea:**
   la cabecera de conventions establece que "si una convención entra en conflicto con una spec,
   manda la spec y se anota en `progress/`". El implementer lo anotó y la persona aprobó AC-19 en
   CP-1 con ese contenido explícito. Tampoco hay un problema de privacidad: el token de parada es
   el del QR público de la parada, no identifica al dispositivo ni a la persona, y no se registra en
   logs. **Basta con que la persona actualice `docs/conventions.md` §4 (CP-4).** Propuesta de
   texto: "solo `device_id`, idioma, perfil de accesibilidad y última parada consultada (`stop_id`,
   nombre y token), en `localStorage`, encapsulado en `shared/device`". No requiere CP-3.

## Decisiones locales revisadas

- **Anuncios de "llegando" (AC-15)**: interpretan "pase a" como una transición. (a) Solo se
  anuncian las llegadas `MINUTES`, coherente con AC-06. (b) No se anuncian los autobuses que ya
  llegaban cuando aparecen los primeros datos: no hay transición y la lista ya dice "está llegando".
  (c) Sin vehículo, si el grupo ya estaba llegando en la evaluación anterior no se repite, lo que
  cumple "una sola vez". Un mensaje con varias frases si llegan varios a la vez. Está dentro del AC
  y de la clave del design. Casos límite aceptables (no bloqueantes): sin `trip_id`, si un grupo
  oscila 0 → 1 → 0 entre respuestas se anunciaría dos veces, y si el autobús siguiente del mismo
  grupo pasa a primero ya a 0 min justo después, se callaría. Conviene que la persona valide (b)
  en CP-6 con lector de pantalla.
- **Cuenta atrás (AC-13)**: `ceil((arrival_at − ahora_servidor)/60 s)`, limitado a [0, `minutes` de la
  API]. Al recibir los datos se ve exactamente lo que dice la API y luego solo baja. Correcto.
  `useServerNow` recalcula el desfase con cada `generated_at` nuevo, como pide el design §3. El
  fichero se llama `useServerNow.ts` y no `useServerClock.ts` como en el árbol del design §2
  (tasks T-03 sí dice `useServerNow`). Diferencia de nombre sin impacto; **no bloqueante**.
- **Estado inicial de la conexión**: `onlineManager.setEventListener` toma `navigator.onLine` al
  arrancar (`shared/api/queryClient.ts:8-19`). Es necesario para AC-18 ("abierta sin conexión no
  llama a la API") porque TanStack Query v5 arranca siempre "en línea". El test la cubre.
  Correcto.
- **Dejar de refrescar tras un 404** (`useStopQueries.ts:45-48`): coherente con AC-16 (la parada no
  existe y la vista ya muestra "Parada no encontrada") y con `retry` del design. Evita peticiones
  inútiles. Correcto y cubierto (`StopPage.errors.test.tsx:104`).
- **El aviso de error no es región viva**: correcto. AC-15 prohíbe anunciar los refrescos
  automáticos, incluidos los fallidos, y ni AC-17 ni conventions §4 piden `role` para los errores.
  Ver el hallazgo N-1, un hueco de la spec relacionado.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-1 (hueco de spec, accesibilidad)**, `frontend/src/features/passenger/stop/StopPage.tsx:75-78,117-133`:
  si la persona pulsa "Actualizar" y la petición falla, no se anuncia nada (`refresh()` solo anuncia
  si acierta), y el botón enfocado desaparece porque se sustituye por "Datos de las…". El foco cae al
  `body`. Lo mismo pasa con "Reintentar" cuando acierta, porque el aviso se desmonta. La spec no dice
  qué hacer tras una acción manual fallida ni dónde dejar el foco, así que el implementer no debía
  inventarlo. Propuesta para la próxima revisión de la spec, sin CP-3 urgente: anunciar de forma
  educada el fallo de una acción **manual** y conservar el foco (p. ej. mantener el botón en su
  sitio o mover el foco al aviso o a "Reintentar"). Que la persona lo pruebe en CP-6.
- **N-2**, `StopPage.tsx:101-111`: si falla solo la petición de la parada (503) y las llegadas
  cargan, el aviso dice "No se han podido cargar **las llegadas**" mientras se ven las llegadas, y
  como `useStop` no se refresca solo, el aviso sigue hasta pulsar "Reintentar". Es un caso raro y
  AC-17 se cumple. Se puede mejorar el texto o refrescar la parada junto con las llegadas.
- **N-3**, `frontend/src/shared/device/storage.ts:2`: el comentario dice que en `localStorage` solo
  hay `device_id`, idioma y perfil; desde AC-19 no es cierto. Hay que actualizarlo cuando la persona
  cambie conventions §4 (desviación 4).
- **N-4 (CP-4, `docs/`)**: actualizar `docs/conventions.md` §4 (desviación 4) y, si se quiere,
  `docs/design.md` §4 (`#E50000`, 4,8:1) y el ejemplo de §5.6 (desviación 3).
- **N-5**, `frontend/src/app/routes/HomePage.tsx:31`: repite a mano la conversión de idioma
  (`i18n.language === 'ca' ? 'ca' : 'es'`) en lugar de usar `useUiLanguage()`; y `StopHeader.tsx:24`,
  `StopNotFound.tsx:16` y `NotFoundPage.tsx:13` repiten las clases del `h1` que `StopPage.tsx:26` define
  como constante. Detalles de estilo.
- **N-6**, `backend/src/avisabus/adapters/inbound/http/app.py:43-50`: el documento exportado sale de
  `create_app(schema_only=True)`, no de la app real de `avisabus.main`. Hoy son iguales (solo están
  los routers de salud y paradas), pero si una feature futura registra routers solo en `main.py`, el
  test de AC-02 no lo detectaría. Recomendación para futuras features: registrar los routers siempre
  en `create_app`.
