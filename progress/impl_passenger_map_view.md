# Implementación: passenger_map_view
Spec: specs/passenger_map_view/ (v1.3, APPROVED, PR #60) · Ciclo de revisión: 0 (v1.3) · Rama: `feat/passenger_map_view-v1.3`
Versiones anteriores: v1.2 (PR #33), ciclo 0, rama `feat/passenger_map_view-v1.2`; v1.1 (PR #29),
ciclo de revisión 2, rama `feat/passenger_map_view`.
Exploración: `progress/explore_map.md` (E-01), que no se repite.

## Estado
v1.3: T-09 terminada (commit 0c897c7). `CI=1 ./init.sh verify --e2e` en verde (ver "Verificación").
v1.2: T-08 terminada (commit 4fef5c7). `CI=1 ./init.sh verify --e2e` en verde (ver "Verificación").
v1.1: T-01 a T-07 terminadas.
El CP-3 (B-01, B-02, O-1…O-4) quedó resuelto en la spec v1.1 (ver "Bloqueos").
Ciclo 2: corregido el hallazgo bloqueante B-01 (AC-10) de `progress/review_passenger_map_view.md`
(ciclo 1) y el no bloqueante N-01 (ver "Ciclo 2").

## v1.3: T-09 (fixtures de posición en metros reales)
Corrige N-01 de la revisión de `position_estimation` v1.4: las fixtures de posición del frontend
tenían `distance_to_stop_m` inflado por `shape_dist_traveled` (3403 m y 4251 m), y las capturas
mostraban "3,4 km". No cambia código de producción.

- **Ficheros regenerados** (idénticos en las dos carpetas): `position-en-route.json`,
  `position-not-started.json` y `position-no-arrival.json` de `frontend/src/test/fixtures/api/` y
  de `frontend/e2e/fixtures/`. Son las respuestas de la API **tal cual**, sin retoques a mano
  (formato JSON con 2 espacios, que Prettier acepta). `shape-93.json` no cambia: la API devuelve
  exactamente el mismo trazado (comprobado con el mismo script; T-09 no lo incluye).
- **Valores nuevos:**

| Fixture | `generated_at` (València) | Respuesta |
|---|---|---|
| `position-en-route` | 2026-11-04 08:40 | `REALTIME`, `EN_ROUTE`, 5 min (07:45Z), viaje `…_2_023`; **844 m**, a 2 paradas, próxima "Cid - Josep Maestre", rumbo 100,95° |
| `position-not-started` | 2026-11-04 05:40 | `SCHEDULED`, `NOT_STARTED`, `CLOCK_TIME` 04:57:40Z (05:57), viaje `…_2_002` en la cabecera; **1839 m**, a 5 paradas, próxima "Cid - Marconi", rumbo 257,36° |
| `position-no-arrival` | 2026-11-04 08:40 | `REALTIME`, `NO_ARRIVAL`, sin posición (como antes) |

  Antes: 3403 m / 3 paradas / "Cid - Hospital General" / 90,9° (viaje del lunes por la tarde con
  las fechas movidas a mano) y 4251 m / 08:58. Además, `stop.lat`/`stop.lon` salen ahora con todos
  sus decimales (`39.4679406744483`, `-0.395681359902679`), que es lo que devuelve la API.
- **Textos esperados actualizados (tests primero, vistos en rojo):**
  - `summary.test.ts` (es/ca, negritas `844 m`/`a 2 paradas`, nombre "Cid - Josep Maestre",
    "Llega a las 05:57"/"Arriba a les 05:57"), `MapPage.test.tsx` (resumen, `NOT_STARTED` y las
    tres expresiones `/^El autobús está a 844 m/`), `BusMap.test.tsx` (`rotate(100.94859961754514deg)`)
    y `e2e/map-view.spec.ts` (`EN_ROUTE` es/ca, rumbo y `NOT_STARTED`).
  - `PositionSummary.test.tsx` usa un `Summary` literal y no lee fixtures: lo actualicé igual para
    que no quede la frase con la distancia inflada.
  - Con las fixtures antiguas fallaban 10 tests unitarios de `passenger/map` y, en e2e (iphone),
    `EN_ROUTE` es/ca y `NOT_STARTED` (3/3). Con las nuevas: 105/105 y 27/27.
  - Comentarios de origen en `src/test/fixtures/api/index.ts` y `e2e/fixtures/index.ts`.
- **Coherencia con `position_estimation` v1.4 (metros reales),** comprobada sin usar el código del
  backend: haversine a lo largo de las coordenadas de `shape-93.json`, desde la proyección de la
  posición hasta la de la parada 508:

| Fixture | API | Medido | Diferencia | Margen de AC-06 (2 % o 10 m) |
|---|---|---|---|---|
| `position-en-route` | 844 m | 840,5 m | +3,5 m | OK |
| `position-not-started` | 1839 m | 1835,3 m | +3,7 m | OK |
| (antiguas) | 3403 / 4251 m | 1242,0 / 1835,3 m | +2161 / +2416 m | fallan |

  La posición está sobre el trazado (0,0 m) y la parada 508, a 4,4 m. Control: con el reloj en el
  instante real de la grabación (lunes 2026-11-02, desfase 1300 s), la API da 1243 m para el viaje
  `…_2_124`: es la "~1,24 km" de N-01, que antes salía como 3403 m.
- **Capturas revisadas** (`frontend/test-results/passenger_map_view/`, no versionadas):
  `iphone/map-en-route-es`, `pixel/map-en-route-ca` y `tablet-landscape/map-not-started-es`. Los
  resúmenes dicen "844 m … a 2 paradas … Cid - Josep Maestre" (y en ca, "844 m … a 2 parades"),
  y "Avinguda del Cid. Llega a las 05:57". En el mapa del EN_ROUTE quedan dos paradas entre el
  autobús y "Tu parada". En el NOT_STARTED, el autobús "Según horario" está en la cabecera.

### Cómo se generaron (para repetirlo)
- **Base de datos:** copia de solo lectura de la base local, `data/avisabus.sqlite`, con el feed
  completo de EMT importado: `feed_version` 2, "23-10-2026", válido del 2026-10-16 al 2026-11-22.
  La copia se hizo con `sqlite3 -readonly data/avisabus.sqlite ".backup <copia>"`, para no tocar
  la base local.
- **Composición real:** `tests.support.position.position_client`, el mismo cableado que
  `avisabus.main` (`build_stop_use_cases` + `build_position_use_cases` + `create_app`), detrás de
  la caché del SAE. Peticiones en proceso con `httpx.ASGITransport`, sin red ni servidor.
- **SAE en modo `replay`** (`SaeReplayArrivalsSource`), con `FakeClock` fijo. Así no depende de
  la hora real:
  - `en-route`: reloj a 2026-11-04 07:40Z y `stop_508_peak` con `start` 1300 s antes. Es la
    respuesta del desfase 1300 s, "93 Pass. Marítim - 5 min.", la misma de la fixture anterior.
  - `not-started`: reloj a 2026-11-04 04:40Z, antes de que salga el viaje `…_2_002`. El replay
    empieza 1 h después, así que no hay grabación (`no_recording`, el backend registra
    `arrivals.fallback`) y la llegada sale del horario (RF-09). A las 08:40 no hay ningún
    `NOT_STARTED` por horario: probé minuto a minuto de 06:30Z a 08:30Z y todo es `EN_ROUTE`,
    porque la frecuencia es de ~7 min y el recorrido desde la cabecera es de ~7 min. Por eso este
    caso tiene otra hora. Es `NOT_STARTED` de 03:07Z a 04:28Z y de 04:37Z en adelante.
  - `no-arrival`: reloj a 2026-11-04 07:40Z y la grabación derivada `samples/derived_no_arrivals`
    (la 508 sin llegadas).
- **Petición:** `GET /api/v1/stops/508/lines/93/position?direction_id=0&t=<token de la 508>`.
- **Comando** (desde `backend/`, con el script de abajo guardado fuera del repositorio):
  `PYTHONPATH=. uv run python gen.py <copia.sqlite> <carpeta de salida>`. Después se copian los
  tres `position-*.json` a `frontend/src/test/fixtures/api/` y a `frontend/e2e/fixtures/`.
  Reimportar otro feed puede cambiar los viajes y los valores: hay que volver a revisar los
  textos esperados.

```python
"""Regenerate the position fixtures of the frontend (passenger_map_view T-09, v1.3).

Real backend composition (`tests.support.position.position_client`, the same wiring as
`avisabus.main`) over a copy of the local database, with the SAE in replay mode and a fixed
clock (FakeClock). The JSON bodies are written verbatim, as the API returns them.

Usage, from backend/:
    PYTHONPATH=. uv run python gen.py <copy of data/avisabus.sqlite> <out dir>
"""
import asyncio, json, sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from avisabus.adapters.outbound.persistence.db import create_engine
from tests.support.fake_clock import FakeClock
from tests.support.position import position_client
from tests.support.sae import DERIVED_NO_ARRIVALS, STOP_508_PEAK
from tests.support.stops import API, replay, stops_settings, token

AT = datetime(2026, 11, 4, 7, 40, tzinfo=UTC)  # Wednesday, 08:40 in València
BEFORE_SERVICE = datetime(2026, 11, 4, 4, 40, tzinfo=UTC)  # 05:40: trip _002 not started yet
EN_ROUTE_OFFSET_S = 1300  # stop_508_peak at 508, offset 1300 s: "93 Pass. Marítim - 5 min."
CASES = {
    # REALTIME: the replay is at offset 1300 s of stop_508_peak at AT.
    "position-en-route.json": (AT, STOP_508_PEAK, AT - timedelta(seconds=EN_ROUTE_OFFSET_S)),
    # The replay starts 1 h after the clock: no recording yet (`no_recording`), so the arrivals
    # come from the timetable (RF-09) and the first trip of the line is still at its first stop.
    "position-not-started.json": (BEFORE_SERVICE, STOP_508_PEAK, BEFORE_SERVICE + timedelta(hours=1)),
    # REALTIME without arrivals at 508 (recording `samples/derived_no_arrivals`).
    "position-no-arrival.json": (AT, DERIVED_NO_ARRIVALS, AT),
}


async def get(engine, now: datetime, session: Path, start: datetime, path: str, **params) -> dict:
    clock = FakeClock(now)
    source, _ = replay(session, clock, start=start)
    async with position_client(engine, clock, source) as (client, _):
        response = await client.get(f"{API}{path}", params=params)
        assert response.status_code == 200, response.text
        return response.json()


def write(path: Path, body: dict) -> None:
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> None:
    engine = create_engine(stops_settings(database_url=f"sqlite:///{sys.argv[1]}"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, (now, session, start) in CASES.items():
        body = await get(engine, now, session, start, "/stops/508/lines/93/position",
                         direction_id=0, t=token("508"))
        write(out / name, body)
        print(name, json.dumps({k: body[k] for k in ("source", "status", "generated_at", "arrival",
                                                     "vehicle", "shape_id", "position")},
                               ensure_ascii=False))
    # Only to compare with the committed shape-93.json (not part of T-09).
    write(out / "shape-93.json", await get(engine, AT, STOP_508_PEAK, AT, "/shapes/994_488_2271"))


asyncio.run(main())
```

## v1.2 (CP-6 del bloque 2): T-08
- **AC-05: sin insignia si no hay posición** (N-03, decisión de la persona en el CP-6).
  - `buildSummary` devuelve `badge: null` cuando `position` es `null` (`NO_ARRIVAL`, `NO_VEHICLE`
    y la respuesta incoherente `EN_ROUTE`/`NOT_STARTED` sin posición). Con posición (también
    `AT_STOP`), la insignia sigue según `source`. `PositionSummary` no pinta la insignia (ni la
    caja vacía) si es `null`: en la sección quedan solo el `h2` y el texto.
  - *Tests nuevos, escritos antes y vistos en rojo (5 unitarios y 3 e2e):*
    - `summary.test.ts` `[passenger_map_view.AC-05] (v1.2) without a position there is no badge
      (source REALTIME/SCHEDULED)`: `NO_ARRIVAL`, `NO_VEHICLE` y `EN_ROUTE` sin posición. El test
      anterior de la insignia por `source` usaba `NO_ARRIVAL`; ahora recorre `EN_ROUTE`,
      `NOT_STARTED` y `AT_STOP`, todos con posición.
    - `PositionSummary.test.tsx` `[passenger_map_view.AC-05] (v1.2, es/ca) without a position
      there is no badge`: ningún texto de insignia en es ni en ca, y solo `H2` y `P` en la sección.
    - `MapPage.test.tsx` `[passenger_map_view.AC-05] (v1.2) NO_ARRIVAL: no badge next to
      "Posición no disponible"`.
    - `e2e/map-view.spec.ts`, el test `NO_ARRIVAL` (ahora cita AC-05) comprueba que no hay
      "Posición estimada" ni "Posición según horario" en el resumen. Con el `PositionSummary`
      anterior fallaba en los tres perfiles (`Expected: 0, Received: 1`).
  - i18n: no hay claves nuevas ni cambiadas (se deja de usar `map.estimated`/`map.scheduled` en
    ese caso); la paridad es/ca-valencia no cambia.
- **Espera fija del e2e (N-05):** `page.waitForTimeout(400)` sustituida por esperas a eventos de
  Leaflet en `[passenger_map_view.AC-10] the arrow keys and the zoom move the map without
  animation`: `moveend` tras la flecha derecha y `zoomend` tras `+` y tras "Alejar".
  - La espera es necesaria y no basta con "nada": `leaflet-pan-anim` se añade de forma síncrona,
    pero un zoom animado añade `leaflet-zoom-anim` en el siguiente `requestAnimationFrame`
    (`_tryAnimatedZoom` de Leaflet 1.9.4). Sin espera, una regresión del zoom podría pasar.
  - Cómo: Leaflet 1.9.4 asigna siempre `window.L` al cargarse. Un `page.addInitScript`
    (`exposeLeafletMap`) intercepta esa asignación y registra con `L.Map.addInitHook` (API pública)
    un gancho que guarda el mapa en `window.leafletMap`. `nextMapEvent(page, 'moveend' |
    'zoomend')` se suscribe con `map.once` **antes** de la acción y devuelve la función que espera
    el evento. No cambia código de producción.
  - Mutación temporal, ya revertida: el mismo test con `reducedMotion: 'no-preference'` falla en
    los tres perfiles (`leaflet-pan-anim` y diez `leaflet-zoom-anim` registradas). Las esperas
    llegan hasta el final de las animaciones.
  - Ya no queda ningún `waitForTimeout` en `frontend/e2e/`.

## Ciclo 2 (respuesta a la revisión del ciclo 1)
- **B-01, AC-10: el desplazamiento con flechas se animaba con movimiento reducido** (commit
  516197e).
  - *Causa:* el manejador de teclado de Leaflet desplaza con `map.panBy(offset)`, y `panBy`
    (también detrás de `panTo` y `setView`) anima 0,25 s salvo con `animate: false`. Ninguna
    opción del mapa lo desactiva.
  - *Corrección (decisión local):* con `prefers-reduced-motion: reduce`, `BusMap` monta
    `InstantPans`, que sustituye el `panBy` de **esa** instancia del mapa por uno que siempre pasa
    `animate: false`, y lo restaura al desmontarse. Así las flechas, `panTo` y `setView` saltan
    en el acto. Se mantienen las cuatro opciones del design (`zoomAnimation`, `fadeAnimation`,
    `markerZoomAnimation`, `inertia`); `useInitialFit` ya encuadraba con `animate: false`. La
    preferencia se lee una vez al crear el mapa, igual que las opciones.
  - *Tests nuevos, escritos antes y vistos en rojo:*
    - `BusMap.test.tsx` `[passenger_map_view.AC-10] … arrow keys pan the map at once, without
      animation`: con `matchMedia` simulado, foco en el mapa, `keydown` de flecha derecha y un
      tamaño de mapa real (en jsdom mide 0 × 0 y Leaflet salta sin animar). Antes de la
      corrección fallaba con `.leaflet-map-pane` en `leaflet-pan-anim`.
    - `BusMap.test.tsx` `… programmatic pans are not animated either` (`panBy` y `panTo`): antes
      fallaba por el mismo motivo.
    - `BusMap.test.tsx` `… without the preference the arrow keys keep Leaflet's pan animation`:
      control, en verde antes y después. Demuestra que el test sí recorre el camino animado.
    - `e2e/map-view.spec.ts` `[passenger_map_view.AC-10] the arrow keys and the zoom move the map
      without animation`, con `reducedMotion: 'reduce'`. Un `MutationObserver` apunta las clases
      `leaflet-pan-anim`/`leaflet-zoom-anim` del panel mientras se pulsan la flecha derecha, `+`
      y "Alejar", y además comprueba que el panel se mueve en el acto. Antes de la corrección
      fallaba en los tres perfiles (`["leaflet-pan-anim"]` y panel sin mover).
- **N-01:** eliminado el id del texto del resumen que no se usaba (`textId` de
  `PositionSummary` y `SUMMARY_TEXT_ID` de `MapPage`). La región del mapa sigue descrita por
  `map.regionDescription`. N-02…N-04 quedan para la persona o la spec, sin cambios.

## Tareas
- [x] T-01 Enlace "Ver en el mapa" en `ArrivalRow` (AC-01) (commit 9422a62)
- [x] T-02 `usePosition`, `useShape`, `buildSummary` (v1.1: `firstStop` y regla de {llegada}) y `buildMapModel` (v1.1: sin trazado y color sobre blanco) (commit e56eceb)
- [x] T-03 `PositionSummary` y `useProximityAnnouncements` (commit e774828)
- [x] T-04 `BusMap`, `busIcon`, `useInitialFit` y `frontend/.env.example` (commit 00dce45)
- [x] T-05 `MapPage`: ruta diferida, "Cargando mapa…", `h1`, volver y errores (v1.1: trazado, sin token, sentido no numérico) (commit 9c6e06d)
- [x] T-06 Presupuesto de bundle ampliado y `e2e/map-view.spec.ts` con capturas (commit 9a9a9dd)
- [x] T-07 Verificación completa: `CI=1 ./init.sh verify --e2e` en verde
- [x] T-08 (v1.2) Sin insignia "Posición estimada" sin posición (AC-05) y sin la espera fija en `e2e/map-view.spec.ts` (commit 4fef5c7)
- [x] T-09 (v1.3) Fixtures de posición (unitarias y e2e) regeneradas con la API actual (`distance_to_stop_m` en metros reales) y textos esperados actualizados (commit 0c897c7)
- [x] T-07 (v1.3) Verificación completa: `CI=1 ./init.sh verify --e2e` en verde

En cada tarea escribí los tests primero y los vi en rojo: fallo de importación (módulo
inexistente) o de aserción, como los 4 de T-01. Para comprobar que los tests fallan si se rompe
el comportamiento, hice dos mutaciones temporales, ya revertidas:
- importar `MapPage` de forma estática en `routes.tsx` → falla el test
  `[passenger_map_view.AC-02] Leaflet … not in the initial JavaScript`;
- en `NOT_STARTED`, el texto exige "Avinguda del Cid" (la primera parada del trazado). Si se
  usara `next_stop` ("Cid - Marconi"), el test fallaría.

### Matriz AC → test
| AC | Evidencia |
|---|---|
| AC-01 | `stop/__tests__/ArrivalRow.test.tsx`: con y sin enlace, tiempo real y programado, es/ca, fuera de `aria-hidden` y URL codificada. E2E: stop → mapa ("Ver en el mapa" solo en las dos llegadas del 93) |
| AC-02 | `src/__tests__/bundle-budget.test.ts` (Leaflet solo en el fragmento `MapPage-*.js`, nunca en el JS inicial; JS inicial ≤ 200 KB). `MapPage.test.tsx` (fallback `role="status"`). E2E: el fragmento se retiene y "Cargando mapa…" se ve |
| AC-03 | `MapPage.test.tsx`: `h1` con `arrival.destination` (`lang`) o `headsign`, título, "Volver a la parada" con token, es/ca. E2E: título, enlace y foco en el `h1` tras navegar |
| AC-04 | `summary.test.ts`: cada estado; `MINUTES`/`CLOCK_TIME`/0 min; cuenta atrás; n = 1 / 0; `NOT_STARTED` con y sin trazado; es/ca; negritas y nombres GTFS. `PositionSummary.test.tsx`. `MapPage.test.tsx`: primera parada al llegar el trazado; cuenta atrás con el reloj del servidor. E2E: `EN_ROUTE` es/ca, `NOT_STARTED`, `NO_ARRIVAL` |
| AC-05 | `summary.test.ts` (insignia por `source` con posición; v1.2: `null` sin posición), `PositionSummary.test.tsx` (es/ca; v1.2: sin insignia), `MapPage.test.tsx` (v1.2: `NO_ARRIVAL` sin insignia), `busIcon.test.ts` y `BusMap.test.tsx` ("Estimada"/"Según horario", "Tu parada"/"La teua parada", sin leyenda). E2E: `NO_ARRIVAL` sin insignia (v1.2) |
| AC-06 | `useProximityAnnouncements.test.tsx` (8 casos), `PositionSummary.test.tsx` (sin región viva), `MapPage.test.tsx` (un anuncio al pasar a `AT_STOP`; un refresco fallido no anuncia) |
| AC-07 | `mapModel.test.ts` (coordenadas `[lat, lon]`, `#e50000` y contraste ≥ 4,5:1, neutro, paradas, parada añadida, autobús, sin trazado), `busIcon.test.ts`, `BusMap.test.tsx` (trazado bajo las paradas, flecha a 90,9°, sin posición, sin trazado, ningún marcador enfocable), `MapPage.test.tsx` (trazado 404, sin `shape_id`). E2E: trazado, 28 paradas y flecha en el DOM de Leaflet |
| AC-08 | `useInitialFit.test.ts` (encuadra una vez, al estar listo; no reencuadra), `mapModel.test.ts` (límites), `MapPage.test.tsx` (sin posición espera al trazado) |
| AC-09 | `BusMap.test.tsx`: atribución con enlace abajo a la derecha, OSM por defecto y `VITE_MAP_TILE_URL`, zoom arriba a la derecha traducido y cambio de idioma, `keyboard` y `tabIndex=0`. E2E: 44 × 44 px; flechas, `+`/`-` y botones con el teclado |
| AC-10 | `BusMap.test.tsx`: `map.options` mediante `ref`, con y sin `prefers-reduced-motion`; (ciclo 2) flechas y `panBy`/`panTo` sin `leaflet-pan-anim` con movimiento reducido, y control sin la preferencia. E2E con `reducedMotion: 'reduce'`: ni desplazamiento ni zoom animados |
| AC-11 | `BusMap.test.tsx`: región "Mapa del recorrido"/"Mapa del recorregut" con descripción. E2E con axe |
| AC-12 | `usePositionQueries.test.tsx` (URL, `min(refresh_after_s, 30)`, pausa oculta, datos conservados, trazado una vez, sin `shape_id`, 404 sin reintentos), `MapPage.test.tsx` (4 refrescos y 1 trazado; pausa) |
| AC-13 | `MapPage.test.tsx`: 404 `line-not-at-stop`/`stop-not-found` (es/ca, sin refrescos); sin token, token vacío y sentido `abc`/`-1`/`1.5` sin llamar a la API; 503 → 2 reintentos y "Reintentar" con anuncio; error de red en un refresco → datos marcados como antiguos; "Reintentar" fallido; trazado 503 → mismo tratamiento; trazado 404 no es error. E2E: 404 y 503 → "Reintentar" |
| AC-14 | `e2e/map-view.spec.ts`: API y teselas simuladas, cualquier otro origen abortado y comprobado vacío; `EN_ROUTE` (es/ca), `NOT_STARTED`, `NO_ARRIVAL`, 404 y 503 × iPhone 14 / Pixel 7 / iPad horizontal; axe WCAG 2.1 A/AA excluyendo solo `.leaflet-tile-pane` |
| AC-15 | Revisión con capturas (ver abajo) |

### Capturas para la revisión visual (AC-15)
`npm run e2e` (o `CI=1 ./init.sh verify --e2e`) las regenera en cada ejecución en
`frontend/test-results/passenger_map_view/<perfil>/<nombre>.png`, con el mismo mecanismo que
`passenger_stop_view`. `<perfil>` es `iphone`, `pixel` o `tablet-landscape`. Son de página
completa, con las animaciones desactivadas y tomadas tras `document.fonts.ready`. No se versionan:
`test-results/` está en `.gitignore`.

| Fichero | Contenido |
|---|---|
| `map-en-route-es.png` / `-ca.png` | Resumen con insignia "Posición estimada", trazado, paradas, "Tu parada", autobús "Estimada" con flecha, zoom y atribución |
| `map-not-started-es.png` | "Posición según horario", "Llega a las 08:58", autobús "Según horario" con borde discontinuo en la cabecera |
| `map-no-arrival-es.png` | "Posición no disponible…" sin insignia (v1.2), solo trazado y paradas |
| `map-line-not-found-es.png` | "No se encuentra esta línea en tu parada" |
| `map-error-es.png` | Aviso de error con "Reintentar" |
| `map-focused-es.png` | Mapa con el foco del teclado (contorno de 3 px en la caja del mapa) |
| `map-zoom-focused-es.png` | Botón "+" con el foco |

Las teselas son un PNG gris de 1 × 1 px: en las capturas el mapa tiene un fondo liso. He revisado
`iphone/map-en-route-es`, `tablet-landscape/map-not-started-es` y `pixel/map-focused-es` frente a
§5.7. Comprobé el orden (volver, `h1` de 22 px, resumen, mapa), la caja del resumen
(`accent-surface`, borde de 2 px y radio de 14 px), las cifras en negrita, el mapa de 360 px con
radio de 14 px y borde `control-border`, los botones de zoom de 44 px arriba a la derecha, la
atribución de 12 px abajo a la derecha y las etiquetas sobre fondo `text` con letra blanca de
13 px, sin leyenda.

## Decisiones locales
Dentro del design §6 (marcadores e iconos, `lazy` frente a `React.lazy`), de la redacción que la
v1.1 deja al implementer y de detalles internos no contractuales.

- **(v1.2) Insignia sin posición:** `Summary.badge` admite `null` (`'estimated' | 'scheduled' |
  null`) y la decisión se toma en la función pura `buildSummary` (design §1: "la lógica de qué
  dibujar y qué decir está en funciones puras"), como indican los ficheros de T-08 (`summary.ts`,
  `PositionSummary.tsx`). La condición es `position === null`, la de AC-05 v1.2 ("MIENTRAS haya
  posición (`position` no nula)"). **Observación para la spec:** el tipo `Summary` del design §3
  sigue diciendo `badge: 'estimated' | 'scheduled'`; conviene añadir `| null` en la próxima
  revisión (no bloquea: AC-05 v1.2 lo exige y T-08 apunta a `summary.ts`).
- **(v1.2) Esperas del e2e:** a `moveend`/`zoomend` mediante el gancho de pruebas
  `exposeLeafletMap` (ver "v1.2"), solo en `e2e/map-view.spec.ts`.
- **Dependencias:** `leaflet@^1.9.4`, `react-leaflet@^5.0.0` y `@types/leaflet@^1.9.22` (E-01). Se
  instalaron con `npm install --offline` desde la caché de npm, sin red.
- **Ruta diferida:** `React.lazy` + `Suspense` en `app/routes.tsx`, con el fallback `MapLoading`
  (`<p role="status">Cargando mapa…</p>`), que va en el fragmento inicial y no importa Leaflet. El
  fragmento `MapPage` contiene `MapPage`, `BusMap`, Leaflet, react-leaflet y su CSS.
- **Tamaños medidos** (`npm run build`): JS inicial 141,2 KB gzip (antes 138,7; el aumento es el
  enlace, el fallback y los textos nuevos); `MapPage-*.js` 50,2 KB gzip; `MapPage-*.css` 6,8 KB gzip.
- **Texto del resumen con marcas:** `Summary.text` es un `string` (interfaz del design) con
  `<strong>…</strong>` (distancia, paradas y tiempo en negrita, §5.7) y `<name>…</name>` (nombres
  GTFS con `lang="ca-ES-valencia"`, `frontend_i18n.AC-06`). `summaryParts` los separa para pintar
  y `summaryPlainText` los quita. Las marcas salen de las traducciones.
- **Elisión en valenciano:** "d'Avinguda del Cid" frente a "de Cid - Marconi". Si la primera
  parada empieza por vocal o por h + vocal, se usa el contexto i18next `map.notStarted_elided`. En
  castellano esa clave es igual a `map.notStarted`, por la paridad de claves.
- **`NO_VEHICLE` y datos incoherentes:** si un estado `EN_ROUTE`/`NOT_STARTED` viniera sin
  `position` o sin `arrival`, el resumen dice "Posición no disponible…" con el motivo de
  `NO_VEHICLE`.
- **Anuncios (AC-06):** lo que ya muestran los primeros datos no se anuncia (el resumen ya lo
  dice), igual que en `passenger_stop_view.AC-15`. Al llegar a `AT_STOP` se da también por hecho
  "en la siguiente", para que no se anuncie después. Si la estimación retrocede, no se repite el
  hito. Sin `vehicle.trip_id` no se anuncia.
- **Descripción de la región (AC-11):** `aria-describedby` apunta a un `<p hidden>` con
  `map.regionDescription`, que remite al resumen ("La misma información está en texto en el
  resumen «Dónde está el autobús», antes del mapa"). No apunta al texto del resumen, para no
  leerlo dos veces. Se usa `<section aria-label>`, que ya es región implícita, porque
  `role="region"` explícito es redundante para `jsx-a11y`.
- **Encuadre (AC-08):** `MapContainer` necesita una vista al crearse, y toma los límites del
  primer modelo. `useInitialFit(map, bounds, ready)` encuadra una sola vez cuando `ready` es
  verdadero, sin animación, con `padding` de 40 px y `maxZoom` 17 (autobús y parada pueden
  coincidir). `ready` es verdadero si hay posición, si no hay `shape_id` o si el trazado ya
  respondió (bien o con error). Sin posición, se espera al trazado para encuadrarlo entero.
- **Recuadro sin trazado ni posición:** 300 m de lado (± 150 m) alrededor de la parada.
- **Marcadores (§5.7, design §6):**
  - Paradas: círculos blancos de radio 5 con borde de 2 px del color de la línea. La del pasajero
    tiene radio 9 y borde de 4 px `text`, con un `Tooltip` permanente "Tu parada".
  - Autobús: `divIcon` con disco del color de la línea (texto blanco ≥ 4,5:1), pictograma de
    autobús de §6, flecha `text` sobre un anillo de 48 px girada `bearing_deg` (sin flecha si es
    `null`) y etiqueta "Estimada"/"Según horario" sobre `text` con letra blanca de 13 px. Con
    horario, el borde del disco es discontinuo.
  - Ningún marcador es interactivo ni enfocable (`keyboard={false}`, `interactive={false}`).
  - Claves estables por id de parada y aparición: con el índice, "Tu parada" se volvía a montar al
    llegar el trazado y dejaba 200 ms un tooltip vacío que axe detectaba.
- **Trazado bajo las paradas:** panel propio `routePane` (z-index 390, por debajo de
  `overlayPane`, 400). Sin él, el trazado que llega después se pintaba encima de "Tu parada".
- **Controles:** `zoomControl={false}` + `<ZoomControl position="topright" key={idioma}>` con
  "Acercar"/"Alejar" ("Acosta"/"Allunya") (E-01). Atribución con un `control.attribution` propio,
  abajo a la derecha, sin el prefijo "Leaflet" y regenerado al cambiar de idioma: enlace a
  `https://www.openstreetmap.org/copyright`.
- **CSS del mapa** (`map/busMap.css`, en el fragmento diferido): botones de 44 × 44 px con borde
  `control-border`, atribución de 12 px sobre blanco al 92 % con enlace `accent`, etiquetas
  `text`/blanco de 13 px. El foco del teclado del mapa se dibuja en su caja
  (`.bus-map:has(.leaflet-container:focus-visible)`, 3 px `accent` separado 2 px), porque los
  paneles de Leaflet tapaban un contorno dibujado sobre el propio mapa.
- **Movimiento reducido (AC-10, ciclo 2):** además de las opciones del design, el `panBy` de la
  instancia del mapa fuerza `animate: false` (`InstantPans` en `BusMap.tsx`). Ver "Ciclo 2".
- **Errores (AC-13):**
  - Reutilizan los textos y componentes de la vista de parada: aviso `stop.error.body` con
    "Reintentar", "Datos de las HH:MM, pueden no estar actualizados" y aviso "Sin conexión".
  - "Reintentar" vuelve a pedir lo que falló (posición y/o trazado) y anuncia "Datos
    actualizados" o "No se han podido actualizar los datos". Mientras está en curso, el aviso se
    mantiene.
  - Si acierta y el botón tenía el foco, el foco pasa al `h1` (no hay botón "Actualizar" en esta
    vista). Si falla, el foco sigue en "Reintentar".
  - Un 404 del trazado no es error.
  - El 404 de la posición, y la URL sin token o con sentido no válido, muestran el `h1` "No se
    encuentra esta línea en tu parada" con "Volver a la parada". Sin token, el enlace lleva a
    `/p/{stop_id}`, que muestra "Parada no encontrada".
- **Mientras cargan los datos:** `h1` "Línea 93" (`stop.lineName`) y "Cargando mapa…".
- **`h1` y título:** `map.title` lleva la marca `<destination>` para el `lang` del destino. El
  título del documento usa el mismo texto sin marcas.
- **Fuera de `map/`** (todo tipado o reutilización, sin cambio de comportamiento):
  - `shared/api/types.ts`: alias `PositionResponse`, `PositionArrival`, `PositionStatus` y
    `ShapeResponse`.
  - `stop/countdown.ts`: `currentMinutes` acepta `Pick<Arrival, 'kind' | 'minutes' |
    'arrival_at'>` para usarlo con la llegada de la posición.
  - Iconos nuevos `shared/ui/icons/ArrowLeftIcon.tsx` y `MapIcon.tsx`.
- **Fixtures:**
  - `shape-93.json` (`src/test/fixtures/api/` y `e2e/fixtures/`) es la respuesta del backend real
    sobre `gtfs_mini` (línea 93, sentido 0, forma `994_488_2271`, 294 puntos y 28 paradas). Con la
    base local completa sale idéntica.
  - (v1.3) Las tres `position-*.json` son respuestas del backend real sin retoques, con la base
    local, el SAE en `replay` y el reloj fijo (ver "v1.3"). En la v1.1 se derivaban a mano de una
    respuesta con las fechas movidas y la distancia inflada.
  - `line-not-at-stop.json` es el problema 404 del design de `position_estimation`.
- **E2E sin red (AC-14):**
  - Un único `page.route('**/*')`: la API sale de las fixtures, cada tesela de
    `tile.openstreetmap.org` es un PNG local de 1 × 1 px, el resto del origen local se sirve
    tal cual, y cualquier otro origen se aborta y se apunta. Cada test comprueba que esa lista
    está vacía.
  - El zoom se lee de las teselas del DOM y no de las peticiones, porque el navegador reutiliza
    teselas en caché.

## Bloqueos
Ninguno abierto.

- **B-01 y B-02 (CP-3), resueltos en la spec v1.1 (PR #29):** la persona eligió la opción A para
  la primera parada (`shape.stops[0]`, con texto alternativo sin trazado) y la regla de
  `passenger_stop_view.AC-06` para {llegada}. Implementados en T-02 con los textos de la v1.1.
- **O-1…O-4, incorporadas a la v1.1:** mapa de 360 px, atribución solo dentro del mapa (guía
  1.2), color del trazado sobre blanco y casos sin trazado, sin token o con sentido no numérico.
- Detalle del bloqueo original: commit cff0e84, versión anterior de este fichero.

## Verificación
### v1.3 (T-09), ciclo 0
`CI=1 ./init.sh verify --e2e` con el puerto 4173 libre, tras el commit 0c897c7: **"verify: todo
en verde"** (salida de 0).

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | OK: 1915 passed, 9 deselected; cobertura 99,66 % |
| frontend: format, lint, types | OK |
| frontend: tests | OK: 68 ficheros, 675 passed, 2 skipped |
| frontend: build + bundle | OK (`bundle-budget` 5/5) |
| frontend: e2e + a11y | OK: 132 passed (27 de `map-view.spec.ts`) |
| harness: feature_list.json, trazabilidad AC→test | OK |

Antes, por separado: `npm run test -- passenger/map` 105/105, y `npx playwright test
e2e/map-view.spec.ts --retries=0` 27/27 dos veces, la segunda para regenerar las capturas.

### v1.2 (T-08), ciclo 0
`npm run build` en `frontend/` y después `CI=1 ./init.sh verify --e2e` con el puerto 4173 libre,
tras el commit 4fef5c7: **"verify: todo en verde"**.

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | OK: 988 passed, 6 deselected; cobertura 99,46 % |
| frontend: format, lint, types | OK |
| frontend: tests | OK: 44 ficheros, 414 tests (5 nuevos de AC-05 v1.2) |
| frontend: build | OK |
| frontend: e2e + a11y | OK: 87 passed (27 del mapa); `test:bundle` 4/4 |
| harness: feature_list.json, trazabilidad AC→test | OK |

Estabilidad sin la espera fija: `e2e/map-view.spec.ts` con `--retries=0 --repeat-each=2`, dos
veces: 54/54 y 54/54 (más una ejecución suelta de 27/27 y la de la verificación completa).
`cd frontend && npm run test -- PositionSummary summary`: 29/29.

### Ciclo 2
`CI=1 ./init.sh verify --e2e` con el puerto 4173 libre, tras el commit 516197e: **"verify: todo
en verde"**.

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | OK: 969 passed, 6 deselected; cobertura 99,39 % |
| frontend: format, lint, types | OK |
| frontend: tests | OK: 44 ficheros, 395 tests (3 nuevos de AC-10) |
| frontend: build | OK |
| frontend: e2e + a11y | OK: 87 passed (27 del mapa, 3 de ellos de AC-10 con movimiento reducido); `test:bundle` 4/4 |
| harness: feature_list.json, trazabilidad AC→test | OK |

`e2e/map-view.spec.ts` repetido dos veces sin reintentos: 54/54.

### Ciclo 0
`CI=1 ./init.sh verify --e2e` con el puerto 4173 libre, tras T-06: **"verify: todo en verde"**.

| Paso | Resultado |
|---|---|
| backend: format, lint, types, architecture | OK |
| backend: tests | OK: 969 passed, 6 deselected; cobertura 99,39 % (≥ 80 %) |
| frontend: format, lint, types | OK |
| frontend: tests | OK: 44 ficheros, 392 tests |
| frontend: build | OK |
| frontend: e2e + a11y | OK: 84 passed (Playwright, 3 perfiles: 24 del mapa + 60 existentes); `test:bundle` 4/4 |
| harness: feature_list.json, trazabilidad AC→test | OK |

`e2e/map-view.spec.ts` repetido tres veces sin reintentos (`--repeat-each=3 --retries=0`):
72/72, antes de los dos últimos ajustes de CSS (foco del mapa y etiqueta "Según horario"); después,
24/24 por separado y dentro de la verificación completa.
