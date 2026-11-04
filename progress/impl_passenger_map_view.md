# Implementación: passenger_map_view
Spec: specs/passenger_map_view/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Rama: `feat/passenger_map_view`
Exploración: `progress/explore_map.md` (E-01), que no se repite.

## Estado: BLOQUEADO (CP-3) en T-02

T-01 está hecha porque no depende del hueco. T-02 a T-07 quedan paradas hasta que la persona
resuelva B-01 y B-02 (ver "Bloqueos"), porque los dos afectan al texto de `buildSummary` (T-02),
que usan `PositionSummary` (T-03) y `MapPage` (T-05).

## Tareas
- [x] T-01 Enlace "Ver en el mapa" en `ArrivalRow` (AC-01) (commit 9422a62)
- [ ] T-02 `usePosition`, `useShape`, `buildSummary`, `buildMapModel` — **bloqueada (B-01, B-02)**
- [ ] T-03 `PositionSummary` y `useProximityAnnouncements`
- [ ] T-04 `BusMap` y `useInitialFit`
- [ ] T-05 `MapPage` (ruta diferida)
- [ ] T-06 Presupuesto de bundle ampliado y E2E
- [ ] T-07 Verificación completa

### T-01: detalle
- Tests escritos primero en `ArrivalRow.test.tsx`: 4 en rojo antes de implementar (no había
  enlace) y 6 tests `[passenger_map_view.AC-01]` en verde después. Cubren: llegada en red con
  sentido (tiempo real y programada), nombre accesible es/ca, enlace fuera de la parte
  `aria-hidden`, sin enlace si `direction_id = null` o `in_network = false`, y codificación de
  parada, línea y token en la URL.
- `ArrivalRow` y `ArrivalsList` reciben `stopId` y `token` (props obligatorias). `StopPage` se los
  pasa. Los tests existentes de `ArrivalRow`/`ArrivalsList` se envuelven en `MemoryRouter`, porque
  el enlace necesita router. Sus aserciones no cambian.
- `npm run lint`, `typecheck`, `format:check` y `test` en verde: 35 ficheros y 293 tests.
  `e2e/stop-view.spec.ts` en verde: 36/36, axe sin violaciones con el enlace nuevo, en los tres
  perfiles. He revisado `test-results/passenger_stop_view/iphone/stop-realtime-es.png`: la fila 3
  de §5.3 aparece con botón secundario de 48 px a todo el ancho, y no se muestra ni en "Pl.
  Ajuntament" (sin sentido) ni en N4 (fuera de red).
- Hasta T-05 el enlace lleva a "Página no encontrada", porque la ruta del mapa aún no existe.

## Decisiones locales
- **T-01, textos nuevos** (redacción): `stop.viewOnMap` = "Ver en el mapa" / "Mostra en el
  mapa"; `stop.viewOnMapLabel` = "Ver en el mapa la línea {{line}} hacia {{destination}}" /
  "Mostra en el mapa la línia {{line}} cap a {{destination}}". En valenciano uso el imperativo,
  como los demás botones de `ca-valencia` ("Actualitza", "Reintenta"). El nombre accesible empieza
  por el texto visible (WCAG 2.5.3).
- **T-01, destino del nombre accesible:** `arrival.destination`, el headsign GTFS cuando hay
  sentido, por la misma regla de `passenger_stop_view.AC-05` para el texto accesible.
- **T-01, aspecto:** `LinkButton` secundario con icono nuevo `shared/ui/icons/MapIcon.tsx` (mapa
  plegado, trazo 2,2, `aria-hidden`; está en el conjunto mínimo de `docs/design.md` §6), 48 px de
  alto (§2.4) y ancho completo mientras sea la única acción (§5.3). El enlace va fuera del bloque
  `aria-hidden` de la tarjeta para que sea alcanzable con teclado y lector.

## Bloqueos

### B-01 (CP-3) — AC-04 `NOT_STARTED`: el dato "{primera parada}" no llega a `buildSummary`

- **AC-04:** "`NOT_STARTED`: «El autobús aún no ha salido de {primera parada}. Llega en
  {tiempo}.»"
- **Interfaz del design §3:** `buildSummary(p: PositionResponse, t, lang, now)`, que solo recibe la
  respuesta de posición.
- **Realidad:** `VehiclePositionResponse` no contiene la primera parada del viaje. Su
  `position.next_stop` en `NOT_STARTED` **no** es la primera parada, sino la siguiente que alcanzará
  el autobús, es decir, la **segunda**:
  `backend/src/avisabus/domain/services/position_estimator.py:57-66` fija `d = d_0` y toma
  `next_stop` = primera `j` con `d_j > d`. Esto es coherente con `position_estimation.AC-08`
  ("la próxima parada que alcanzará"). Si usara `next_stop`, el resumen diría una parada falsa.
- **Única fuente en el frontend:** `ShapeResponse.stops[0]` (ordenadas por `sequence`). Son las
  paradas del viaje **más frecuente** con esa forma, no necesariamente del viaje concreto, aunque
  normalmente coinciden. Usarla obliga a cambiar la firma de `buildSummary` y a decidir qué decir
  mientras el trazado no ha llegado o si su petición falla.
- **Propuesta A (recomendada, solo frontend):**
  `buildSummary(p, firstStop: string | null, t, lang, now)`, con
  `firstStop = shape.stops[0]?.name ?? null`. La spec debe fijar también el texto sin trazado,
  p. ej. "El autobús aún no ha salido de la cabecera de la línea. Llega en {tiempo}.", o bien que
  el resumen `NOT_STARTED` espere al trazado.
- **Propuesta B:** añadir `first_stop: {stop_id, name}` a la respuesta de posición. Es más
  exacto, pero cambia el contrato de `position_estimation` (feature en `done`): backend, OpenAPI y
  `gen:api`.

### B-02 (CP-3) — AC-04 "Llega en {tiempo}" con llegadas `CLOCK_TIME`

- **AC-04** fija literalmente "Llega en {tiempo}" en `EN_ROUTE` y `NOT_STARTED`.
- **Realidad:** las llegadas del horario programado, y las lejanas del SAE, llegan con
  `kind = "CLOCK_TIME"` y `minutes = null` (`stop_arrivals_api`; fixture
  `frontend/src/test/fixtures/api/arrivals-scheduled.json`). Con `source = "SCHEDULED"` es el caso
  normal, y `NOT_STARTED` es especialmente probable con horario programado. "Llega en 08:52" no es
  una frase correcta.
- Tampoco está fijado qué decir si la cuenta atrás (con `now`, como en
  `passenger_stop_view.AC-13`) llega a 0 antes del siguiente refresco en `EN_ROUTE`.
- **Propuesta:** aplicar la regla de `passenger_stop_view.AC-06`: `MINUTES` → "Llega en {N
  minutos}" (cuenta atrás con `now`); `CLOCK_TIME` → "Llega a las {HH:MM}" (Europe/Madrid); 0 min
  → "Está llegando.". Los textos los fija la spec en es y ca-valencia.

### Observaciones para la misma revisión de la spec (no bloquean; si no se dice nada, las aplicaré así como decisiones locales)

- **O-1 Altura del mapa:** `docs/design.md` §5.7 fija 360 px y el design §3 dice 60 dvh / 70 dvh
  (y §6 lo deja como decisión local). Usaré 360 px, porque en aspecto manda la guía.
- **O-2 Atribución en el pie:** `docs/design.md` §5.1 dice que el pie lleva "la del mapa en la
  vista de mapa". Ponerla exige tocar `app/Layout.tsx` (de `frontend_i18n`), que ninguna tarea
  incluye. Plan: atribución solo dentro del mapa, abajo a la derecha (AC-09, §5.7). Si la persona
  la quiere también en el pie, debe añadirse a una tarea.
- **O-3 Color del trazado:** `ShapeResponse` solo trae `color`, sin color de texto. Plan:
  `accessibleLineColors(color, 'FFFFFF').bg`, con contraste ≥ 4,5:1 frente a blanco (rojo EMT →
  `#E50000`, igual que el distintivo), y el neutro `#1f2937` si no hay color.
- **O-4 Casos no cubiertos:** `shape_id = null`, trazado con 404 o error, ruta sin `?t=` y
  `direction_id` no numérico. Plan: sin `shape_id` o con el trazado en 404, el mapa muestra solo la
  parada del pasajero y el autobús. Un error de red del trazado recibe el mismo tratamiento que la
  posición (AC-13). Sin token o con `direction_id` no numérico no se llama a la API y se muestra
  "No se encuentra esta línea en tu parada".

## Verificación
`./init.sh verify` (sin `--e2e`) tras T-01: todos los pasos en verde (backend: formato, lint,
tipos, arquitectura y tests; frontend: formato, lint, tipos, tests y build; esquema de
`feature_list.json`) **excepto** "harness: trazabilidad AC→test", que falla como se esperaba:
`passenger_map_view.AC-02` … `AC-14` sin tests, porque son las tareas bloqueadas (AC-15 se
verifica por revisión). E2E de la vista de parada: 36/36 en verde (ver "T-01: detalle").
