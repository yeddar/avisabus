# Mapa del autobús — design

> Feature: `passenger_map_view` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-13, RNF-01, RNF-03, RNF-05, RNF-14 · Casos de uso: CU-02 · Depende de: passenger_stop_view, position_estimation

## 1. Resumen

`MapPage` (cargada con `React.lazy`) pide la posición cada 20–30 s y el trazado una vez. Muestra
primero `PositionSummary` (texto) y después `BusMap` (react-leaflet). La lógica de qué dibujar y
qué decir está en funciones puras testables sin Leaflet; los componentes de Leaflet son una capa
fina.

## 2. Componentes

```
frontend/src/features/passenger/map/
├── MapPage.tsx              # ruta lazy; h1, volver, resumen, mapa
├── PositionSummary.tsx      # texto según estado (AC-04, AC-05)
├── summary.ts               # buildSummary(position, lang) → { text, badge } (puro)
├── BusMap.tsx               # MapContainer, TileLayer, Polyline, CircleMarker, Marker
├── mapModel.ts              # buildMapModel(shape, position) → capas a dibujar (puro)
├── busIcon.ts               # L.divIcon con SVG rotado por bearing_deg
├── useInitialFit.ts         # encuadre solo en la primera carga (AC-08)
├── usePositionQueries.ts    # usePosition, useShape
├── useProximityAnnouncements.ts
└── MapLegend.tsx
```

Cambios en `features/passenger/stop/ArrivalRow.tsx`: enlace "Ver en el mapa" (AC-01).

Ruta en `app/routes.tsx`:

```ts
{ path: '/p/:stopId/map/:line/:directionId', lazy: () => import('../features/passenger/map/MapPage') }
```

(o `React.lazy` + `Suspense` con el fallback "Cargando mapa…" — decisión local permitida; en
ambos casos el fallback lleva `role="status"`).

Dependencias: `leaflet`, `react-leaflet`; dev: `@types/leaflet`. El CSS de Leaflet se importa
dentro de `BusMap.tsx` (fragmento diferido).

Variable de entorno: `VITE_MAP_TILE_URL` (por defecto
`https://tile.openstreetmap.org/{z}/{x}/{y}.png`), documentada en `frontend/.env.example`.

## 3. Interfaces

```ts
// usePositionQueries.ts
export function usePosition(stopId: string, token: string, line: string, directionId: number):
  UseQueryResult<PositionResponse, ApiError>;          // mismas opciones de refresco que useStopArrivals
export function useShape(shapeId: string | null):
  UseQueryResult<ShapeResponse, ApiError>;              // enabled: shapeId !== null; staleTime: Infinity

// summary.ts
export type Summary = { text: string; badge: 'estimated' | 'scheduled' };
export function buildSummary(p: PositionResponse, t: TFunction, lang: Language, now: Date): Summary;

// mapModel.ts
export type MapModel = {
  line: { coords: [number, number][]; color: string };   // [lat, lon] para Leaflet
  stops: { id: string; name: string; latLng: [number, number]; isTarget: boolean }[];
  bus: { latLng: [number, number]; bearing: number | null; scheduled: boolean } | null;
  fitBounds: [[number, number], [number, number]];       // bus+parada o trazado completo
};
export function buildMapModel(shape: ShapeResponse, position: PositionResponse): MapModel;
```

### Mapa (react-leaflet)

- `MapContainer` con `keyboard`, `zoomControl` (títulos traducidos vía `L.Control.Zoom` con
  `zoomInTitle`/`zoomOutTitle`), `attributionControl`.
- Con `prefers-reduced-motion: reduce`: `zoomAnimation`, `fadeAnimation`, `markerZoomAnimation`
  a `false` e `inertia: false` (AC-10).
- Contenedor: `<section role="region" aria-label={t('map.region')} aria-describedby="summary-id">`.
  Altura: 60 dvh en móvil, 70 dvh en tablet.
- Paradas: `CircleMarker` radio 5 (la del pasajero: radio 9, borde grueso, `Tooltip` permanente
  con su nombre). El autobús: `Marker` con `divIcon` (SVG de autobús, flecha rotada con
  `bearing_deg`, texto visible "Estimada"/"Según horario" bajo el icono; borde discontinuo si
  `scheduled`).
- Ningún marcador es enfocable con teclado (la información está en el resumen); el mapa sí lo es
  para desplazarse.

### Anuncios (AC-06)

`useProximityAnnouncements(position)` recuerda por `vehicle.trip_id` qué hitos ya anunció
(`ONE_STOP`, `ARRIVING`).

## 4. Datos (claves i18n nuevas, extracto)

```
stop.viewOnMap ("Ver en el mapa"), stop.viewOnMapLabel ("Ver en el mapa la línea {{line}} hacia {{destination}}"),
map.title ("Línea {{line}} hacia {{destination}}"), map.back, map.loading, map.region, map.regionDescription,
map.estimated, map.scheduled, map.enRoute, map.stopsAway_one, map.stopsAway_other, map.nextIsYours,
map.atStop, map.notStarted, map.unavailable, map.reasonNoArrival, map.reasonNoVehicle,
map.notFound, map.zoomIn, map.zoomOut, map.osmAttribution, map.announceOneStop, map.announceArriving
```

## 5. Estrategia de test

| AC | Test |
|---|---|
| AC-01 | `ArrivalRow.test.tsx` (con y sin enlace) |
| AC-02 | Presupuesto de bundle de `passenger_stop_view` (sigue en verde) + test de que `leaflet` no aparece en el fragmento inicial (`bundle-budget.test.ts` ampliado) + e2e del fallback |
| AC-03, AC-13 | `MapPage.test.tsx` (con `BusMap` simulado por `vi.mock`) |
| AC-04, AC-05 | `summary.test.ts` (tabla por estado y plurales en `es` y `ca`) |
| AC-06 | `useProximityAnnouncements.test.ts` |
| AC-07 | `mapModel.test.ts` + e2e (comprueba trazado y marcador del autobús en el DOM de Leaflet) |
| AC-08 | `useInitialFit.test.ts` |
| AC-09, AC-10, AC-11 | `BusMap.test.tsx` (opciones pasadas a `MapContainer`, `matchMedia` simulado) + e2e (teclado: `+`/`-` y flechas) |
| AC-12 | `MapPage.test.tsx` con temporizadores falsos (una sola petición de trazado) |
| AC-14 | `e2e/map-view.spec.ts`: `page.route('**/api/v1/**')` con fixtures y `page.route('**/tile.openstreetmap.org/**')` → PNG 1×1 local |

## 6. Decisiones locales permitidas

- `lazy` del router frente a `React.lazy`.
- Estilo de los marcadores e iconos (manteniendo texto visible y contraste).
- Altura del mapa.

## 7. Preguntas abiertas

- Delegada a exploración E-01 (compatibilidad de versiones y política de teselas).
