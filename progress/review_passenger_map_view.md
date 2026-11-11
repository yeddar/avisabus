# Revisión: passenger_map_view

## v1.3 · Ciclo 1
Ciclo: 1 (v1.3) · Fecha: 2026-11-11 · Agente: reviewer
Spec: `specs/passenger_map_view/` v1.3 (APPROVED, PR #60) · Rama: `feat/passenger_map_view-v1.3`
(HEAD 5ab1a11; tests y fixtures en 0c897c7) · Base: `origin/feat/driver_ui-v1.2` (PR #64),
diff `git diff origin/feat/driver_ui-v1.2...HEAD`

## Veredicto: APPROVED

T-09 cumple lo que pide. Las tres `position-*.json`, unitarias y e2e, son respuestas de la API
actual sin retoques. Las regeneré con el procedimiento documentado y salen **idénticas byte a
byte**. Una medición independiente sobre el trazado da distancias en metros reales, dentro del
margen de `position_estimation.AC-06` v1.4. Los tres cambios de escenario se justifican con el
horario del feed y ningún test se ha debilitado: con las fixtures antiguas fallan 10 tests y con
las nuevas pasan todos. No cambia código de producción. `CI=1 ./init.sh verify --e2e` está en
verde. No hay hallazgos bloqueantes. Hay un no bloqueante nuevo (N-10) y siguen abiertos N-02,
N-04, N-06, N-07, N-08 y N-09.

## Matriz AC → evidencia

La v1.3 solo cambia datos de prueba (T-09) y no modifica ningún AC. La matriz recoge los tests
que leen las fixtures regeneradas o cuyos textos esperados cambian. El resto sigue como en la
v1.2 y vuelve a pasar en este ciclo.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | Sin cambios: `ArrivalRow.test.tsx`, E2E `map-view.spec.ts:344` | OK | |
| AC-02 | Sin cambios: `bundle-budget.test.ts` (5/5), E2E `:344` | OK | `index-*.js` 85,80 KB gzip; `MapPage-*.js` 50,15 KB gzip, en un fragmento aparte |
| AC-03 | Sin cambios | OK | |
| AC-04 | `summary.test.ts:33` (es) y `:39` (ca): "844 m … a 2 paradas … Cid - Josep Maestre". `:97`: NOT_STARTED con "Llega a las 05:57" / "Arriba a les 05:57". `:151`: negritas `844 m` / `a 2 paradas`. `MapPage.test.tsx:144`, `:172`, `:333`, `:352` y `:385` (texto completo o `/^El autobús está a 844 m/`). `PositionSummary.test.tsx` (`Summary` literal). E2E `:211` (es/ca) y `:259` | **OK** | Los textos esperados salen de la API real. Con las fixtures antiguas fallan 10 tests (ver "Verificación") |
| AC-05 | Sin cambios en las aserciones (`summary.test.ts`, `MapPage.test.tsx:144,158`, `BusMap.test.tsx:110,118`, E2E `:259` "Posición según horario", `:280` sin insignia) | OK | `position-no-arrival` solo cambia `stop.lat`/`lon` (todos los decimales) |
| AC-06 | Sin cambios (`useProximityAnnouncements.test.tsx`, a partir de `POSITION_EN_ROUTE` con `stops_away` modificado) | OK | |
| AC-07 | `BusMap.test.tsx:94` y E2E `:211`: `rotate(100.94859961754514deg)` | **OK** | El rumbo es el que devuelve la API. Medí el rumbo del segmento 61 del trazado y da 100,9486°. La aserción es igual de estricta que antes (`90.9`, redondeado a mano) |
| AC-08 | Sin cambios (`useInitialFit.test.ts`, `mapModel.test.ts`) | OK | |
| AC-09 | Sin cambios: E2E `:211` y `:383` | OK | |
| AC-10 | Sin cambios: `BusMap.test.tsx`, E2E `:435` × 3 perfiles | OK | |
| AC-11 | Sin cambios | OK | |
| AC-12 | Sin cambios (`MapPage.test.tsx:235,250`, `usePositionQueries.test.tsx`) | OK | |
| AC-13 | `MapPage.test.tsx:333`, `:352` y `:385`: solo cambia el prefijo esperado del resumen conservado | OK | Las aserciones de reintento y de datos conservados no cambian |
| AC-14 | `e2e/map-view.spec.ts` × 3 perfiles: EN_ROUTE (es/ca), NOT_STARTED y NO_ARRIVAL, con axe | OK | 27/27 de `map-view.spec.ts`, sin reintentos ni *flaky* |
| AC-15 | Capturas regeneradas en esta verificación (`frontend/test-results/passenger_map_view/<perfil>/`, 22:33) | OK (revisión) | `iphone/map-en-route-es`: "844 m … a 2 paradas … Cid - Josep Maestre … 5 minutos", con 2 paradas entre "Estimada" y "Tu parada". `pixel/map-en-route-ca`: "844 m … a 2 parades … Arriba en 5 minuts". `tablet-landscape/map-not-started-es`: "aún no ha salido de Avinguda del Cid. Llega a las **05:57**", con "Según horario" en la cabecera y 5 paradas hasta "Tu parada". Ya no aparece "3,4 km". Se ajusta a `docs/design.md` §5.7 |

## Verificación ejecutada

- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre; árbol limpio salvo `qr/`, sin seguimiento y
  ajeno a la feature) → **`verify: todo en verde`** (EXIT=0).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 1915 passed, 9 deselected; cobertura 99,66 % |
| frontend: format, lint, types | OK |
| frontend: tests | 68 ficheros; 675 passed, 2 skipped |
| frontend: build + bundle | OK; `bundle-budget` 5/5 |
| frontend: e2e + a11y | 132 passed, 12 skipped (`driver.spec.ts` en perfiles de móvil, ajenos a la feature); `map-view.spec.ts` 27/27 |
| harness: feature_list.json, trazabilidad AC→test | OK (AC-01…AC-15 citados) |

### Reproducción de las fixtures (encargo: "salen de la API real y se pueden regenerar")
1. Copia de la base local con `sqlite3 -readonly data/avisabus.sqlite ".backup <scratchpad>/copy.sqlite"`.
   La copia tiene `feed_version` 2, "23-10-2026", activo, del 2026-10-16 al 2026-11-22. La base del
   repositorio no se tocó.
2. Extraje el script de `progress/impl_passenger_map_view.md` sin cambios y lo ejecuté desde
   `backend/` con `PYTHONPATH=. uv run python <scratchpad>/gen.py <copia> <out>`. Las peticiones
   van en proceso (`httpx.ASGITransport`), sin red, con `FakeClock` y el SAE en `replay`.
3. `cmp` y SHA-256 contra el repositorio:

| Fichero | `src/test/fixtures/api/` | `e2e/fixtures/` |
|---|---|---|
| `position-en-route.json` (`cd08433f…`) | **idéntico** | **idéntico** |
| `position-not-started.json` (`f200f1f8…`) | **idéntico** | **idéntico** |
| `position-no-arrival.json` (`74bdc301…`) | **idéntico** | **idéntico** |
| `shape-93.json` (fuera de T-09) | mismo JSON (`==`), otro formato | igual que el unitario |

   `shape-93.json` es semánticamente idéntico a la respuesta de la API, pero el del repositorio
   está formateado por Prettier, con los pares de coordenadas en una línea. Es coherente con lo
   que dice el progreso ("la API devuelve exactamente el mismo trazado") y T-09 no lo incluye.
4. Composición: `tests.support.position.position_client` reproduce `src/avisabus/main.py:80-84`
   (`build_stop_use_cases` + `build_position_use_cases` + `create_app`). Solo cambia que las
   anulaciones de sentido son `{}` en lugar de `config/direction_overrides.json`, que no incluye
   la línea 93, así que el resultado es equivalente.

### Medición independiente (coherencia con `position_estimation` v1.4)
Script propio (`<scratchpad>/measure.py`, sin código del backend). Acumula la distancia haversine
sobre las 294 coordenadas de `shape-93.json` y proyecta en el segmento más próximo la posición y la
parada 508. Así calcula la distancia sobre el trazado, el rumbo del segmento y las paradas que
quedan en medio.

| Fixture | API | Medido | Diferencia | Margen AC-06 (2 % o 10 m) | Rumbo API / segmento | `stops_away` / paradas en medio |
|---|---|---|---|---|---|---|
| `position-en-route` | 844 m | 840,5 m | +3,5 m | 16,8 m → **OK** | 100,9486° / 100,9486° | 2 / 506, 507; `next_stop` 506 ✓ |
| `position-not-started` | 1839 m | 1835,3 m | +3,7 m | 36,7 m → **OK** | 257,3559° / 257,3559° | 5 / 495, 496, 700, 506, 507 (sin contar la 488, donde está); `next_stop` 495, la segunda (design §3) ✓ |
| (antigua) en ruta | 3403 m | 1242,0 m | +2161 m | **FALLA** | | |
| (antigua) sin empezar | 4251 m | 1835,3 m | +2416 m | **FALLA** | | |

La posición está sobre el trazado (0,0 m) y la parada 508 queda a 4,4 m de él. Coincide con las
cifras del progreso.

### Legitimidad de los tres cambios de escenario (horario de la copia, `gtfs_stop_time`)
- **Otro viaje en ruta (`_122` → `_023`).** El viaje `_023` pasa por 700 a las 08:38:24, por 506
  a las 08:40:08 y por 508 a las 08:43:39. Con el SAE a "5 min" a las 08:40, el retraso es de 81 s
  y el instante desplazado, 08:38:39. Cae entre 700 y 506, así que la próxima es la 506 y quedan 2
  paradas (`position_estimation.AC-01/02/08`). El `_122` anterior venía de una grabación del
  lunes por la tarde con las fechas movidas a mano. Ahora es la respuesta real del miércoles a las
  08:40.
- **`not-started` a las 04:40Z (05:40 en València).** El `_001` sale a las 05:29 y pasa por la 508
  a las 05:36:40, así que ya ha pasado. El `_002` sale de la 488 a las 05:50 y llega a la 508 a las
  05:57:40, lo que da `arrival_at` 04:57:40Z, `CLOCK_TIME` y `SCHEDULED` (no hay grabación:
  `arrivals.fallback reason=no_recording`, sin identificadores). Es un `NOT_STARTED` legítimo
  (`position_estimation.AC-04/10`). La explicación de por qué no puede ser a las 08:40 (frecuencia
  de unos 7 min frente a un recorrido de unos 7 min) cuadra con el horario. "05:57" trunca los
  segundos, igual que `formatClockTime` (caso `07:09:30Z → 09:09` de `format.test.ts`).
- **Rumbo con todos los decimales.** Es el valor de la API (coincide con el segmento al
  `1e-4`). Las aserciones `rotate(100.94859961754514deg)` son exactas, igual que antes.

### ¿Se han debilitado los tests?
- Los cambios en los tests sustituyen literales uno por uno. No se quita ninguna aserción ni se
  relaja ninguna expresión: `/^El autobús está a 844 m/` sustituye a `/^El autobús está a 3,4 km/`.
- Lo comprobé en una copia del frontend (`git archive HEAD`, `node_modules` enlazado), con las tres
  `position-*.json` de la base. `vitest run src/features/passenger/map` da **10 failed | 95
  passed**: `BusMap.test.tsx:94`, `MapPage.test.tsx:144,172,333,352,385` y
  `summary.test.ts:33,39,97,151`. Con HEAD da 105/105.
- El formato en km (`1,2 km`) ya no aparece en ningún test de la feature, pero `formatDistance`
  lo sigue cubriendo en `src/shared/i18n/__tests__/format.test.ts:39-51` (ver N-10).

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-10 (nuevo) — Ningún test de la feature ejerce el resumen con distancias de 1 km o más.**
  `summary.test.ts:26` cambia el valor por defecto de `enRoute` de 3403 a 844, y el único caso
  explícito usa 850 (`:53`). AC-04 no fija el formato de `{distancia}`, y `formatDistance` está
  cubierto en `format.test.ts:39-51`, así que el riesgo es bajo. *Propuesta (opcional):* añadir a
  `summary.test.ts` un caso `enRoute(2, 1234)` que espere "1,2 km" (es/ca).
- **N-08 — Problema de spec menor (deuda documental), sigue abierto.** `design.md` §3 v1.3 sigue
  diciendo `badge: 'estimated' | 'scheduled'`, mientras que `summary.ts` devuelve `null` sin
  posición (AC-05 v1.2). No requiere CP-3. Se puede recoger en la próxima revisión de la spec.
- **N-09 — `docs/design.md` §5.7, punto 3, sigue abierto.** No dice que la insignia falta sin
  posición. Lo decide la persona (CP-6).
- **N-02, N-04, N-06 y N-07 siguen abiertos, sin cambios** (ver los ciclos anteriores más abajo).
  Son la elisión valenciana ante i/u semiconsonánticas, las costuras de las teselas simuladas, la
  preferencia de movimiento reducido leída al montar y la restauración de `panBy` sin test.
- *(Observación, sin acción)* Para repetir la regeneración hacen falta la base local completa,
  que no está versionada, y el script, que está en `progress/impl_passenger_map_view.md` y no como
  fichero del repositorio. Está documentado (`feed_version` 2 "23-10-2026", reloj, grabaciones y
  petición) y `src/test/fixtures/api/index.ts` remite al progreso. Si se reimporta otro feed, los
  valores cambiarán, como advierte el propio progreso.

### Alcance
`git diff --stat origin/feat/driver_ui-v1.2...HEAD` toca solo las tres `position-*.json` (×2), los
comentarios de origen de `src/test/fixtures/api/index.ts` y `e2e/fixtures/index.ts`, los textos
esperados de `summary.test.ts`, `MapPage.test.tsx`, `PositionSummary.test.tsx`, `BusMap.test.tsx`
y `e2e/map-view.spec.ts`, y los ficheros de orquestación y progreso (`feature_list.json`,
`progress/*`). **No cambia código de producción** (nada fuera de `__tests__`, `test/fixtures` y
`e2e`), ni el backend, `docs/` o `specs/`. No hay claves i18n nuevas ni variables de entorno. Los
commits siguen Conventional Commits con el ámbito de la feature y citan la tarea
(`test(passenger_map_view): … (T-09)`). Privacidad: sin cambios en registros. El aviso
`arrivals.fallback` del generador solo lleva `stop_id`.

---


## v1.2 · Ciclo 1
Ciclo: 1 (v1.2) · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/passenger_map_view/` v1.2 (APPROVED, PR #33) · Rama: `feat/passenger_map_view-v1.2` (HEAD eb371e8; código en 4fef5c7) · Base: `origin/develop` (tras `git fetch`)

## Veredicto: APPROVED

T-08 cumple AC-05 v1.2. Sin posición (`NO_ARRIVAL`, `NO_VEHICLE` o respuesta con `position = null`)
no se pinta la insignia, ni siquiera una caja vacía. Con posición, `AT_STOP` incluido, la insignia
depende de `source`. La espera fija `page.waitForTimeout(400)` ha desaparecido y la sustituyen
esperas a eventos de Leaflet que no usan reloj real. El test de AC-10 sigue detectando las
animaciones (ver "Mutaciones"). `CI=1 ./init.sh verify --e2e` está en verde, no hay regresiones y
no hay hallazgos bloqueantes. Quedan dos notas de documentación no bloqueantes (N-08 y N-09).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | Sin cambios: `ArrivalRow.test.tsx`, E2E `map-view.spec.ts:339` | OK | Verde en este ciclo |
| AC-02 | Sin cambios: `bundle-budget.test.ts`, `MapPage.test.tsx`, E2E `:339` | OK | `index-*.js` 141,48 KB gzip; `MapPage-*.js` 50,23 KB gzip. `test:bundle` 4/4 |
| AC-03 | Sin cambios | OK | |
| AC-04 | Sin cambios en los tests de texto. El test de `NO_ARRIVAL` de `summary.test.ts:181` comprueba además el texto "Posición no disponible…" | OK | |
| AC-05 | `summary.test.ts:168`: con posición, `EN_ROUTE`, `NOT_STARTED` y `AT_STOP` × `REALTIME`/`SCHEDULED` dan la insignia de su `source` (y el test exige que `position` no sea nula). `summary.test.ts:181` (v1.2): `NO_ARRIVAL`, `NO_VEHICLE` y `EN_ROUTE` con `position = null` dan `badge === null`, con las dos fuentes. `PositionSummary.test.tsx:72` (v1.2, es/ca): ningún texto de insignia y solo `H2` + `P` en la sección. `MapPage.test.tsx:158` (v1.2): `NO_ARRIVAL` de extremo a extremo sin insignia. Siguen en verde `MapPage.test.tsx:144` (insignia con posición), `PositionSummary.test.tsx:56` y los de `busIcon`/`BusMap` ("Estimada", "Según horario", "Tu parada", sin leyenda). E2E: `:275` `NO_ARRIVAL` sin insignia (`toHaveCount(0)`, `:288`) y `:254` `NOT_STARTED` con "Posición según horario" | **OK** | Discriminan: fallan M1 a M4 y E6 (ver "Mutaciones"). Coherente con `position_estimation` (`NO_ARRIVAL`/`NO_VEHICLE` ⇒ `position = null`) |
| AC-06 | Sin cambios | OK | |
| AC-07 | Sin cambios | OK | |
| AC-08 | Sin cambios | OK | |
| AC-09 | Sin cambios: E2E `:378` | OK | |
| AC-10 | Sin cambios en unit (`BusMap.test.tsx`). E2E `:430` × 3 perfiles: ahora espera `moveend` tras la flecha y `zoomend` tras `+` y tras "Alejar" (`:460-471`), sin `waitForTimeout` | **OK** | La espera no usa reloj real (§4 "sin sleeps reales"). Fallan E1, E3 y E4; con el gancho roto, el test falla en vez de pasar (E5) |
| AC-11 | Sin cambios | OK | |
| AC-12 | Sin cambios | OK | |
| AC-13 | Sin cambios | OK | |
| AC-14 | `e2e/map-view.spec.ts` × 3 perfiles | OK | 87 passed y ningún *flaky*. `expectNoNetworkLeaks` también en `:430` y `:275` |
| AC-15 | Capturas de `frontend/test-results/passenger_map_view/<perfil>/` regeneradas en esta verificación | OK (revisión) | En `iphone/map-no-arrival-es.png`, el resumen tiene solo el título y el texto, sin insignia ni hueco. En `iphone/map-en-route-es.png` siguen "Posición estimada", "Estimada" y "Tu parada". El resto del aspecto se ajusta a `docs/design.md` §5.7 |

## Verificación ejecutada

- `cd frontend && npm run build` → OK (`index-*.js` 141,48 KB gzip; `MapPage-*.js` 50,23 KB gzip).
- `CI=1 ./init.sh verify --e2e` (puerto 4173 libre; árbol limpio) → **`verify: todo en verde`** (EXIT=0).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 988 passed, 6 deselected; cobertura 99,46 % |
| frontend: format, lint, types | OK |
| frontend: tests | 44 ficheros, 414 tests OK |
| frontend: build | OK |
| frontend: e2e + a11y | 87 passed, sin *flaky* ni reintentos; `test:bundle` 4/4 |
| harness: feature_list.json, trazabilidad AC→test | OK |

`grep -rn waitForTimeout frontend/e2e/` no devuelve nada.

### Mutaciones

Las hice en una copia del frontend en el scratchpad (`git archive HEAD`, con `node_modules`
enlazado). Al terminar, la copia volvía a ser idéntica a HEAD y el árbol del repositorio sigue
limpio. Los e2e se lanzaron con `CI=1 … --retries=0 -g …`.

| Mutación | Unit (`passenger/map`, 105 tests) | E2E |
|---|---|---|
| Base (HEAD) | 105/105 | AC-10: 3/3 en verde |
| M1: `badge` según `source` siempre (código anterior) | **Fallan 3**: `summary.test.ts:181` ×2 y `MapPage.test.tsx:158` | E6: `NO_ARRIVAL` **falla** en los 3 perfiles (`Expected: 0, Received: 1`) |
| M2: `badge` siempre `null` | **Fallan 4**: `summary.test.ts:168` ×2, `MapPage.test.tsx:144` y el `NOT_STARTED` de `MapPage` | — |
| M3: `null` solo con `status === 'NO_ARRIVAL'` (no por posición) | **Fallan 2**: `summary.test.ts:181` ×2 (`NO_VEHICLE` y `EN_ROUTE` sin posición) | — |
| M4: `PositionSummary` pinta la caja de la insignia vacía | **Fallan 2**: `PositionSummary.test.tsx:72` es/ca | — |
| E1: sin `zoomAnimation: false` | — | AC-10 **falla** en los 3 perfiles, en 2 ejecuciones (12 `leaflet-zoom-anim` registradas) |
| E2: E1 sin las esperas de `zoomend` | — | También falla en los 3 perfiles en 2 ejecuciones, pero con menos registros (7). Sin espera, la detección depende del tiempo; con la espera, se recorre la animación entera |
| E3: `InstantPans` sin efecto | — | AC-10 **falla** en los 3 perfiles: el panel no se mueve tras la flecha |
| E4: `reducedMotion: 'no-preference'` en el test | — | AC-10 **falla** en los 3 perfiles (`leaflet-pan-anim` y `leaflet-zoom-anim`) |
| E5: sin `exposeLeafletMap` (gancho no instalado) | — | AC-10 **falla** en los 3 perfiles con `TypeError` en `nextMapEvent`: no se queda esperando ni pasa en silencio |

### Comprobación de la espera nueva (docs/verification.md §4)

- `exposeLeafletMap` (`e2e/map-view.spec.ts:158`) usa `page.addInitScript` para interceptar la
  asignación de `window.L` con un *setter* y registra `L.Map.addInitHook`, que es API pública de
  Leaflet. Comprobé que el build de producción asigna `window.L` (`leaflet` 1.9.4 resuelve a
  `dist/leaflet-src.js`, el UMD; en `dist/assets/MapPage-*.js` aparece `window.L=`). No cambia
  código de producción.
- `nextMapEvent` (`:177`) se suscribe con `map.once` **antes** de la acción, así que no hay
  carrera. Si el evento no llega, el test acaba por el *timeout* de Playwright, no por una espera
  fija. Con movimiento reducido, `moveend` y `zoomend` se emiten en el mismo ciclo y el test no se
  ralentiza (unos 0,7–1 s por perfil).
- No usa red: solo `addInitScript` y `evaluate` en la página. `mockNetwork` y
  `expectNoNetworkLeaks` no cambian.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-08 — Problema de spec menor (deuda documental): `Summary.badge` admite `null` y el design
  §3 no lo recoge.** Afecta a `frontend/src/features/passenger/map/summary.ts:18` frente a
  `specs/passenger_map_view/design.md` §3 (`badge: 'estimated' | 'scheduled'`).
  - *Valoración:* cabe y **no requiere CP-3**. Es un tipo interno de la feature, no un contrato
    con otras features ni con la API. AC-05 v1.2, que manda sobre el design, exige que la
    insignia pueda faltar. T-08 cita `summary.ts` entre los ficheros que hay que tocar, y la única
    razón para tocarlo es cambiar la insignia que devuelve. `null` es el cambio mínimo y coherente
    con la regla "MIENTRAS haya posición" de AC-05. La alternativa, pasar la posición a
    `PositionSummary`, sacaría la lógica de la función pura, en contra del §1 del design.
  - *Propuesta:* en la próxima revisión de la spec, el spec-writer actualiza el design §3:
    `badge: 'estimated' | 'scheduled' | null` (null sin posición, AC-05 v1.2). La decisión está
    documentada en `progress/impl_passenger_map_view.md`.
- **N-09 — `docs/design.md` §5.7, punto 3, no matiza que la insignia falta sin posición.** No hay
  contradicción, porque la guía describe el caso con posición, pero quien la lea puede esperar
  siempre la insignia. Corresponde a la persona (CP-6), que puede añadir "(solo si hay posición)".
- *(Observación, sin acción)* La espera de AC-10 depende de que Leaflet 1.x asigne `window.L`. Si
  una versión futura (Leaflet 2, solo ESM) deja de hacerlo, el test fallará con un `TypeError`
  claro (E5) y no dará un falso verde. Es aceptable.

### Alcance
`git diff origin/develop..HEAD` toca solo `summary.ts`, `PositionSummary.tsx`, sus tests,
`MapPage.test.tsx`, `e2e/map-view.spec.ts` y ficheros de progreso y orquestación
(`feature_list.json`, `progress/*`). Todo está dentro de T-08. No cambian el backend, `docs/` ni
`specs/`. No hay claves i18n nuevas (la paridad es/ca-valencia no cambia) ni variables de entorno.
El commit de código, `fix(passenger_map_view): …`, sigue Conventional Commits con el ámbito de la
feature. Privacidad: sin cambios en registros.

---

## v1.1 · Ciclo 2
Ciclo: 2 · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/passenger_map_view/` v1.1 (APPROVED, PR #29) · Rama: `feat/passenger_map_view` (HEAD 2707ce8) · Base: `origin/develop` (tras `git fetch`)

## Veredicto: APPROVED

B-01 (AC-10) está corregido. Con `prefers-reduced-motion: reduce` ya no se anima ningún movimiento
del mapa: flechas, `+`/`-`, botones de zoom, encuadre inicial y desplazamientos programáticos.
Los tests nuevos fallan con el código del ciclo 1 y con varias mutaciones. N-01 está resuelto. La
verificación completa con e2e está en verde, los demás AC no tienen regresiones y no hay hallazgos
bloqueantes.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | Sin cambios desde el ciclo 1: `ArrivalRow.test.tsx:131-163`, E2E `map-view.spec.ts:297` | OK | Verde en este ciclo |
| AC-02 | `bundle-budget.test.ts`, `MapPage.test.tsx:100`, E2E `:297` | OK | `index-*.js` 141,19 KB gzip (sin cambios); `MapPage-*.js` 50,21 KB gzip (+0,05 KB por `InstantPans`). `test:bundle` 4/4 |
| AC-03 | `MapPage.test.tsx:110,128`, E2E | OK | Sin cambios |
| AC-04 | `summary.test.ts`, `PositionSummary.test.tsx`, `MapPage.test.tsx:158,178`, E2E | OK | `PositionSummary.test.tsx` se adaptó a la retirada de `textId` (N-01). Busca el texto dentro de la región y sigue comprobando el texto completo y las negritas |
| AC-05 | Sin cambios | OK | |
| AC-06 | Sin cambios | OK | |
| AC-07 | Sin cambios | OK | |
| AC-08 | `useInitialFit.test.ts`, `mapModel.test.ts`, `MapPage.test.tsx:206` | OK | El encuadre usa `FIT_OPTIONS` con `animate: false` (`useInitialFit.ts:7`) |
| AC-09 | `BusMap.test.tsx`, E2E `:170`, `:336` | OK | Sin cambios. Flechas, `+`/`-` y botones con teclado siguen en verde sin la preferencia |
| AC-10 | `BusMap.test.tsx:210,222` (opciones), `:233` (flecha con movimiento reducido: panel sin `leaflet-pan-anim` y centro ya desplazado), `:244` (`panBy`/`panTo` programáticos), `:257` (control: sin la preferencia sí anima). E2E `map-view.spec.ts:388` × 3 perfiles con `reducedMotion: 'reduce'` (flecha, `+` y "Alejar" sin `leaflet-pan-anim` ni `leaflet-zoom-anim`; el panel salta en el acto) | **OK** | Discriminan: ver "Mutaciones". La sonda independiente confirma un único salto por desplazamiento y ningún zoom animado |
| AC-11 | `BusMap.test.tsx:64-78`, E2E con axe | OK | Sin cambios. La región sigue descrita por `map.regionDescription` |
| AC-12 | Sin cambios | OK | |
| AC-13 | Sin cambios | OK | |
| AC-14 | `e2e/map-view.spec.ts` × 3 perfiles | OK | El test nuevo también llama a `expectNoNetworkLeaks` |
| AC-15 | Capturas de `frontend/test-results/passenger_map_view/<perfil>/` | OK (revisión) | Regeneradas en esta verificación. Revisé `iphone/map-en-route-es` y `pixel/map-focused-es`, iguales a las del ciclo 1. El arreglo no toca el aspecto |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre; árbol limpio) → **`verify: todo en verde`** (EXIT=0).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 969 passed, 6 deselected; cobertura 99,39 % |
| frontend: format, lint, types | OK |
| frontend: tests | 44 ficheros, 395 tests OK (+3 de AC-10) |
| frontend: build | OK; `index-*.js` 141,19 KB gzip; `MapPage-*.js` 50,21 KB gzip |
| frontend: e2e + a11y | 87 passed (+3: AC-10 × 3 perfiles), sin *flaky* ni reintentos. `test:bundle` 4/4 |
| harness: feature_list.json, trazabilidad AC→test | OK |

### Mutaciones

Las hice en una copia del frontend en el scratchpad (`git archive HEAD`), fuera del repositorio,
con `node_modules` enlazado. El árbol del repo sigue limpio.

| Mutación | Unit `BusMap.test.tsx` | E2E AC-10 (3 perfiles) |
|---|---|---|
| Base (HEAD) | 18/18 en verde | — (verde en `verify`) |
| M1: sin `<InstantPans />` | **Fallan** `:233` y `:244` | — |
| `BusMap.tsx` del ciclo 1 (5d7cc2f) con los tests nuevos | (equivale a M1) | **Fallan** los 3. En iphone y pixel, el panel no se ha movido tras la flecha; en tablet, `["leaflet-pan-anim"]` |
| M2: `InstantPans` siempre montado | **Falla** `:257` (control) | — |
| M3: `panBy` sin forzar `animate: false` | **Fallan** `:233` y `:244` | — |
| M4: sin `zoomAnimation: false` | **Falla** `:210` | **Fallan** los 3 (`leaflet-zoom-anim` registrado) |

### Sonda independiente

Añadí un test temporal en la copia, con el perfil pixel y la build real. Un `MutationObserver`
registra los cambios de `transform` del panel y las clases `*-anim` con cada acción:

```
reduce         flechas →/↓/⇧←: 1 cambio de transform cada una, sin clases de animación;
               +, -, botones Acercar/Alejar: sin leaflet-zoom-anim; contenedor sin leaflet-fade-anim
no-preference  flechas: 16-17 fotogramas + leaflet-pan-anim; +/-/botones: leaflet-zoom-anim
```

### Cobertura de todo el movimiento (punto 1 del encargo)

Leí Leaflet 1.9.4 (`node_modules/leaflet/src`) y el código de la feature:
- **Flechas:** `Map.Keyboard.js:162` llama a `map.panBy(offset)`, que es la propiedad propia de la
  instancia, ya sustituida → `animate: false`.
- **`+`/`-`, botones de zoom, rueda, doble clic y zoom con caja:** `setZoom`, `zoomIn`/`zoomOut`
  y `setZoomAround` terminan en `setView`. Con `zoomAnimation: false`, `_tryAnimatedZoom`
  devuelve `false` y aplica `_resetView` en el acto. Si el zoom no cambia, el desplazamiento va
  por `_tryAnimatedPan`, que termina en `this.panBy`, también sustituido.
- **`panTo`, `setView`, `panInsideBounds` y autopan de popups:** acaban en `this.panBy` y quedan
  cubiertos.
- **`flyTo`/`flyToBounds`:** no se usan en `src/features/passenger/map/` (`grep`), y Leaflet no
  los llama internamente.
- **Encuadre inicial:** `MapContainer` aplica `bounds` antes de `_loaded`, sin animación. Después,
  `useInitialFit` llama a `fitBounds` con `FIT_OPTIONS` y `animate: false`.
- **Inercia de arrastre:** `inertia: false`. Si la hubiera, el `panBy` sustituido la anularía.
- **Teselas:** `fadeAnimation: false`; el contenedor no lleva `leaflet-fade-anim` (sonda).
- **Marcadores:** `markerZoomAnimation: false`, y `setLatLng` mueve el autobús sin animación al
  refrescar.
- **Restauración y fugas:** el *cleanup* de `forceInstantPans` (`BusMap.tsx:69-71`) devuelve el
  `panBy` original. Con el doble montaje de StrictMode no se encadenan envolturas, porque al
  restaurar queda la función del prototipo. El cierre solo retiene la propia instancia del mapa,
  que se destruye a la vez, así que no hay referencias globales ni *listeners* sin liberar.

### Alcance y convenciones

- `git diff 5d7cc2f..HEAD` solo toca `BusMap.tsx`, `MapPage.tsx`, `PositionSummary.tsx`, sus tests,
  `e2e/map-view.spec.ts` y los ficheros de `progress/` y `feature_list.json` del orquestador.
  Todos los cambios son de B-01 o N-01, sin refactorizaciones ajenas.
- El commit 516197e sigue Conventional Commits con el ámbito `passenger_map_view` y cita el
  hallazgo.
- No hay textos nuevos (nada de i18n). La privacidad no se ve afectada: no hay `console.*` ni
  registros.

## Hallazgos

### Bloqueantes

Ninguno. **B-01 (ciclo 1): resuelto** (commit 516197e; evidencia arriba).

### No bloqueantes

- **N-01 (ciclo 1): resuelto.** Se eliminaron `textId` y `SUMMARY_TEXT_ID`. La propuesta de
  alinear el fragmento del design §3 (`aria-describedby="summary-id"`) con
  `map.regionDescription` sigue pendiente para una futura revisión de la spec.
- **N-02, N-03 y N-04 (ciclo 1):** siguen abiertos, sin cambios. Son decisiones de la persona o de
  la spec (CP-6), no defectos del código.
- **N-05 — Espera fija en el e2e.** `frontend/e2e/map-view.spec.ts:422` usa
  `page.waitForTimeout(400)`, y es la única espera fija de la suite e2e (`docs/verification.md` §4,
  "sin sleeps reales"). No provoca intermitencias: solo podría relajar la comprobación. Además
  sobra, porque Leaflet añade `leaflet-pan-anim`/`leaflet-zoom-anim` de forma síncrona y el
  `MutationObserver` las registra antes del `page.evaluate` siguiente. Se puede quitar o cambiar
  por una espera a un evento (`moveend`/`zoomend`).
- **N-06 — La preferencia se lee una vez al montar.** En `BusMap.tsx:131`, si la persona activa
  "reducir movimiento" con el mapa abierto, no se aplica hasta volver a entrar en la vista. AC-10
  dice "MIENTRAS el sistema tenga activada…". Leaflet solo lee esas opciones al crear el mapa y la
  decisión está documentada en `progress/impl_passenger_map_view.md`, así que es aceptable. Si se
  quiere cubrir, basta con escuchar el `change` de `matchMedia` y remontar el mapa con un `key`.
- **N-07 — La restauración de `panBy` al desmontar no tiene test.** Afecta a
  `BusMap.tsx:69-71`. Es solo higiene: el mapa se destruye con el componente y `reduceMotion` no
  cambia durante la vida del mapa, así que hoy no tiene efecto observable.

---

## Ciclo 1
Ciclo: 1 · Fecha: 2026-11-04 · Agente: reviewer
Spec: `specs/passenger_map_view/` v1.1 (APPROVED, PR #29) · Rama: `feat/passenger_map_view` · Base: `origin/develop` (tras `git fetch`)

## Veredicto: CHANGES_REQUESTED

Un hallazgo bloqueante: **B-01, AC-10**. Con `prefers-reduced-motion: reduce`, el desplazamiento
con las flechas del teclado sigue animado. Todo lo demás cumple la spec: verificación completa en
verde, matriz AC → test completa, E2E sin red y capturas conformes con `docs/design.md` §5.7.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `stop/__tests__/ArrivalRow.test.tsx:131-163` (con enlace en tiempo real y programado, en ca, sin sentido, fuera de red y URL codificada). E2E `map-view.spec.ts:297` (2 enlaces del 93; ni el 70 sin sentido ni el N4) | OK | Nombre accesible y `href` exactos. El enlace queda fuera de la parte `aria-hidden` |
| AC-02 | `bundle-budget.test.ts` (Leaflet solo en `MapPage-*.js` y nunca en el JS inicial; ≤ 200 KB). `MapPage.test.tsx:100` (fallback `role="status"`). E2E `:297` (fragmento retenido y "Cargando mapa…" visible) | OK | Medido: inicial `index-*.js` 141,19 KB gzip; `MapPage-*.js` 50,16 KB gzip. `test:bundle` 4/4 tras la build |
| AC-03 | `MapPage.test.tsx:110,128`. E2E `:170,:297` | OK | `h1` con `arrival.destination` o `headsign`, título del documento, "Volver a la parada" con token y `lang` del destino |
| AC-04 | `summary.test.ts` (todos los estados; MINUTES, CLOCK_TIME y 0 min; n = 1 / 0; NOT_STARTED con y sin trazado; es/ca; negritas). `PositionSummary.test.tsx`. `MapPage.test.tsx:158` (primera parada al llegar el trazado) y `:178` (cuenta atrás con el reloj del servidor). E2E EN_ROUTE es/ca, NOT_STARTED y NO_ARRIVAL | OK | Textos idénticos a los de la spec en los dos idiomas. NOT_STARTED usa `shape.stops[0]` y no `next_stop` (la fixture lo distingue: "Avinguda del Cid" frente a "Cid - Marconi") |
| AC-05 | `summary.test.ts:164`, `PositionSummary.test.tsx:52`, `busIcon.test.ts:30`, `BusMap.test.tsx:96-114` | OK | "Posición estimada"/"Posición según horario", "Estimada"/"Según horario", "Tu parada" y sin leyenda |
| AC-06 | `useProximityAnnouncements.test.tsx` (8 casos), `PositionSummary.test.tsx:45` (no es región viva), `MapPage.test.tsx:250,338` | OK | Un anuncio por hito y viaje, `polite`. Los datos iniciales no se anuncian (el AC habla de transición, "pase a") |
| AC-07 | `mapModel.test.ts` (coordenadas `[lat, lon]`, `#e50000` ≥ 4,5:1, neutro `#1f2937`, parada añadida, autobús, sin trazado), `busIcon.test.ts`, `BusMap.test.tsx:80-143`, `MapPage.test.tsx:194,392,405`. E2E (trazado `#e50000`, 28 paradas, flecha a 90,9°) | OK | Trazado 404 o sin `shape_id`: solo la parada y el autobús |
| AC-08 | `useInitialFit.test.ts`, `mapModel.test.ts:75-128`, `MapPage.test.tsx:206` | OK | Encuadra una sola vez. Sin posición, espera al trazado |
| AC-09 | `BusMap.test.tsx:145-194`. E2E `:170` (atribución, zoom 44 × 44 px) y `:336` (flechas, `+`/`-`, botones con teclado) | OK | URL por defecto y `VITE_MAP_TILE_URL` (documentada en `frontend/.env.example`) |
| AC-10 | `BusMap.test.tsx:196-217` | **FALLA** | El test solo comprueba las opciones del design. Las flechas siguen animando el desplazamiento con movimiento reducido (B-01) |
| AC-11 | `BusMap.test.tsx:64-78`. E2E con axe | OK | Región "Mapa del recorrido" con descripción que remite al resumen (ver N-01) |
| AC-12 | `usePositionQueries.test.tsx` (7 casos), `MapPage.test.tsx:221,236` | OK | Mismas opciones de consulta que `useStopArrivals`. Trazado con `staleTime: Infinity` |
| AC-13 | `MapPage.test.tsx:262-403`. E2E `:257,:277` | OK | 404 de posición; sin token o con sentido `abc`/`-1`/`1.5` no llama a la API; 503 y error de red de posición y trazado |
| AC-14 | `e2e/map-view.spec.ts` × 3 perfiles (iphone, pixel, tablet-landscape) | OK | `page.route('**/*')`: API desde fixtures, teselas OSM → PNG local y cualquier otro origen abortado y registrado. Cada test comprueba `external == []` y `unexpected == []`. axe WCAG 2.1 A/AA excluye solo `.leaflet-tile-pane`. Service workers bloqueados |
| AC-15 | Capturas de `frontend/test-results/passenger_map_view/<perfil>/` | OK (revisión) | Ver "Conformidad visual". La persona lo revisa en CP-6 |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre; árbol limpio) → **`verify: todo en verde`** (EXIT=0).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | 969 passed, 6 deselected; cobertura 99,39 % |
| frontend: format, lint (incluye i18n/no-literal-string y jsx-a11y), types | OK |
| frontend: tests | 44 ficheros, 392 tests OK |
| frontend: build | OK; `index-*.js` 141,19 KB gzip; `MapPage-*.js` 50,16 KB gzip; `MapPage-*.css` 6,80 KB gzip |
| frontend: e2e + a11y | 84 passed (24 del mapa: 8 × 3 perfiles), sin *flaky* ni reintentos. `test:bundle` 4/4 |
| harness: feature_list.json, trazabilidad AC→test | OK |

Comprobación adicional para AC-10. Hice una sonda con Playwright desde el scratchpad, fuera del
repositorio, sobre la build real servida con `vite preview`, con el perfil Pixel 7, API simulada
y cualquier otro origen abortado. Tras enfocar el mapa y pulsar `ArrowRight`:

```
reduce         pan-anim class seen: true  intermediate transforms: 16
no-preference  pan-anim class seen: true  intermediate transforms: 16
```

Además leí `git diff origin/develop...HEAD`, las capturas y el código fuente de Leaflet
(`node_modules/leaflet/src/map/Map.js:313-350` y `handler/Map.Keyboard.js:140-162`).

## Conformidad visual (AC-15, `docs/design.md` §5.7)

Revisé estas capturas:
- `iphone/map-en-route-es`, `iphone/map-en-route-ca`, `iphone/map-no-arrival-es` e `iphone/map-error-es`;
- `tablet-landscape/map-not-started-es` y `tablet-landscape/map-zoom-focused-es`;
- `pixel/map-focused-es`.

Todas se ajustan a §5.7:
1. Orden de arriba abajo: volver con flecha, `h1` de 22 px, resumen y mapa.
2. Resumen: caja `accent-surface` con borde de 2 px `accent`, radio de 14 px, insignia y cifras en negrita.
3. Mapa: 360 px, radio de 14 px y borde `control-border`. Trazado en el rojo accesible y paradas
   como círculos blancos con borde. "Tu parada" destacada con etiqueta oscura y letra blanca.
4. Autobús: disco con flecha orientada y etiqueta "Estimada"/"Según horario". Con horario, el
   borde es discontinuo.
5. Zoom: "+"/"−" de 44 px arriba a la derecha.
6. Atribución: abajo a la derecha, sobre blanco, con enlace.
7. Sin leyenda.
8. El pie no cambia.
9. Foco visible: 3 px `accent` en la caja del mapa y en "+".

En NOT_STARTED, el autobús apunta a 257,4°. Lo comprobé: coincide con el rumbo del primer
segmento real de la forma `994_488_2271`, que arranca hacia el suroeste. Es coherente con el
backend.

## Comprobaciones especiales

- **Sin red:** cumple (AC-14, arriba). Los tests unitarios usan `mockApi` y `FakeTimers`.
  `MapPage.test.tsx` lanza un error ante cualquier URL no prevista.
- **Bundle:** cumple. Leaflet, react-leaflet y su CSS van solo en el fragmento `MapPage`, cargado
  con `React.lazy`. `MapLoading` va en el inicial y no importa Leaflet.
- **Textos es/ca-valencia:** paridad de claves completa, incluido `map.notStarted_elided`, que en
  es es igual a `notStarted`. Los literales de la spec coinciden: AC-01, 02, 03, 04, 05, 06, 09,
  11 y 13. La elisión "d'Avinguda del Cid" está probada en `summary.test.ts:103`.
- **Decisiones locales:** caben en el design:
  - `Summary.text` como `string` con marcas `<strong>`/`<name>`, generadas por las traducciones
    (`escapeValue: false`, sin `dangerouslySetInnerHTML`; se pinta como nodos React);
  - no anunciar el estado inicial (coherente con `passenger_stop_view.AC-15`);
  - encuadre con `padding` 40 y `maxZoom` 17, sin animación;
  - `aria-describedby` hacia una descripción oculta (ver N-01);
  - foco al `h1` tras un "Reintentar" con éxito (el botón desaparece; si falla, se queda en él).
- **Fixtures:** `position-en-route.json` y `shape-93.json` vienen del backend sobre `gtfs_mini` y
  `stop_508_peak`, con las fechas desplazadas. El origen está documentado en
  `src/test/fixtures/api/index.ts:6-9`. Las dos derivadas difieren solo en los campos esperados
  (`diff` revisado). En NOT_STARTED, `stops_away = 5` y `next_stop = 495` son coherentes con la
  forma. Las copias de `src/test` y `e2e/` son idénticas (`cmp`).
- **Alcance:** fuera de `map/` solo hay cambios necesarios o de tipado:
  - enlace en `ArrivalRow`/`ArrivalsList`/`StopPage`;
  - alias en `shared/api/types.ts`;
  - `currentMinutes` con `Pick<…>`, sin cambio de comportamiento;
  - dos iconos;
  - `.env.example`;
  - dependencias `leaflet`, `react-leaflet` y `@types/leaflet`.

  También hay ficheros de `progress/` del orquestador y del explorer. No hay refactorizaciones
  ajenas.
- **Privacidad:** no registra nada. No hay `console.*` en `map/`, y el token solo va en la URL de
  la API y de "Volver".
- **Commits:** Conventional Commits con el ámbito `passenger_map_view` y la tarea citada.

## Hallazgos

### Bloqueantes

- **B-01 — AC-10: el desplazamiento con teclado se anima con movimiento reducido.**
  `frontend/src/features/passenger/map/BusMap.tsx:42-48` solo fija `zoomAnimation`,
  `fadeAnimation`, `markerZoomAnimation` e `inertia`. Pero el manejador de teclado de Leaflet
  desplaza con `map.panBy(offset)` (`Map.Keyboard.js:162`), y `panBy` anima 0,25 s salvo que
  reciba `animate: false` (`Map.js:342-346`). Ninguna opción del mapa lo desactiva, y la regla
  global de `index.css:56` no le afecta porque la animación es por JS (`PosAnimation`). La sonda
  lo confirma: 16 fotogramas intermedios con `reducedMotion: 'reduce'`.

  AC-10 exige desactivar las animaciones "de zoom, desplazamiento y marcadores". El test
  `BusMap.test.tsx:196-206` solo comprueba las opciones y no detecta el fallo, así que el AC no
  tiene un test válido.

  *No es un problema de spec:* el design §3 enumera las opciones mínimas, pero no impide completar
  el comportamiento. Es una decisión local. Por ejemplo, con movimiento reducido se puede envolver
  `panBy`/`panTo` del mapa para forzar `animate: false`, o sustituir el manejador de flechas por
  uno que lo pase.

  *Cómo corregirlo:* añade un test que falle hoy. Puede ser unitario (`keydown` de flecha sobre el
  contenedor con `matchMedia` simulado: `panBy` se llama con `animate: false`, o
  `.leaflet-map-pane` no recibe `leaflet-pan-anim`) o e2e con `test.use({ reducedMotion: 'reduce' })`.

### No bloqueantes

- **N-01 — Id del resumen sin uso y diferencia con el fragmento del design.**
  `MapPage.tsx:25,225` y `PositionSummary.tsx:10,34` pasan `textId` "so the map can refer to it",
  pero `BusMap.tsx:134-139` usa su propia descripción oculta (`map.regionDescription`). El id queda
  sin usar: elimínalo o úsalo.

  La decisión cumple AC-11 ("una descripción que remita al resumen") y es mejor que apuntar al
  texto, porque no lo lee dos veces. Pero el design §3 dice
  `aria-describedby="summary-id"`, y su §4 lista `map.regionDescription`: el design es
  internamente ambiguo. Propuesta para una futura revisión de la spec, que no requiere CP-3:
  alinear el fragmento con `map.regionDescription`.
- **N-02 — Elisión valenciana sin el caso de i/u semiconsonánticas.** `summary.ts:42` elide ante
  cualquier vocal o h + vocal. No contempla las i/u semiconsonánticas iniciales seguidas de vocal
  ("de Iaia", "de Huit"), que no eliden. Hoy ninguna cabecera del GTFS mini lo provoca. Si se
  quiere, se añade la excepción `^h?[iu][aeiouàèéíòóú]`.
- **N-03 — Insignia "Posición estimada" sin posición (para CP-6).** En NO_ARRIVAL/NO_VEHICLE se
  muestra junto a "Posición no disponible…" (`iphone/map-no-arrival-es`). Cumple AC-05 ("siempre"),
  pero puede resultar contradictorio. Es una observación de spec para que la persona decida en
  CP-6, no un defecto del código.
- **N-04 — Artefactos de las capturas, no de la app.** Se ven costuras finas entre teselas
  (`pixel/map-focused-es`, `tablet-landscape/map-zoom-focused-es`), que vienen del PNG de 1 × 1 px
  simulado. No afectan a la app real.
