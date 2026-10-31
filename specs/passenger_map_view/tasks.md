# Mapa del autobús — tasks

> Feature: `passenger_map_view` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-13, RNF-01, RNF-03, RNF-05, RNF-14 · Casos de uso: CU-02 · Depende de: passenger_stop_view, position_estimation

## Exploración

- **E-01** — Compatibilidad de `react-leaflet` y `leaflet` (últimas estables) con React 19.3, Vite 8
  y el modo estricto; si `react-leaflet` no es compatible, evaluar usar Leaflet directamente con un
  componente propio (`useEffect` + `ref`). Revisar la política de uso de teselas de OpenStreetMap
  (requisitos de `Referer`/atribución, volumen aceptable para una demo de TFM) y anotar si conviene
  un proveedor alternativo para el despliegue. → `progress/explore_map.md`

> Si hay que prescindir de `react-leaflet`, la interfaz de `BusMap` y los AC no cambian (decisión
> local); si la política de teselas impide usar OSM en la demo → CP-3.

## Tareas

- [ ] **T-01** — Enlace "Ver en el mapa" en `ArrivalRow` (condiciones de AC-01).
  - AC: passenger_map_view.AC-01
  - Ficheros: `src/features/passenger/stop/ArrivalRow.tsx`, `src/locales/**`, tests
  - Verificación: `cd frontend && npm run test -- ArrivalRow`

- [ ] **T-02** — `usePosition`, `useShape` y funciones puras `buildSummary` y `buildMapModel`.
  - AC: passenger_map_view.AC-04, AC-05, AC-07, AC-12
  - Ficheros: `src/features/passenger/map/{usePositionQueries,summary,mapModel}.ts`, tests
  - Verificación: `cd frontend && npm run test -- passenger/map`

- [ ] **T-03** — `PositionSummary`, `MapLegend` y `useProximityAnnouncements`.
  - AC: passenger_map_view.AC-04, AC-05, AC-06
  - Ficheros: `src/features/passenger/map/{PositionSummary,MapLegend}.tsx`, `useProximityAnnouncements.ts`, tests
  - Verificación: `cd frontend && npm run test -- PositionSummary useProximityAnnouncements`

- [ ] **T-04** — `BusMap` (Leaflet: teselas configurables, atribución, trazado, paradas, autobús
  orientado, teclado, zoom traducido, movimiento reducido, región accesible) y `useInitialFit`.
  - AC: passenger_map_view.AC-07, AC-08, AC-09, AC-10, AC-11
  - Ficheros: `src/features/passenger/map/{BusMap.tsx,busIcon.ts,useInitialFit.ts}`, `frontend/.env.example`, tests
  - Verificación: `cd frontend && npm run test -- BusMap useInitialFit`

- [ ] **T-05** — `MapPage` (ruta diferida, fallback "Cargando mapa…", `h1`, volver, errores).
  - AC: passenger_map_view.AC-02, AC-03, AC-12, AC-13
  - Ficheros: `src/features/passenger/map/MapPage.tsx`, `src/app/routes.tsx`, tests
  - Verificación: `cd frontend && npm run test -- MapPage`

- [ ] **T-06** — Presupuesto de bundle ampliado (Leaflet fuera del fragmento inicial) y E2E con
  API y teselas simuladas, estados `EN_ROUTE`/`NOT_STARTED`/`NO_ARRIVAL`, teclado y axe.
  - AC: passenger_map_view.AC-02, AC-07, AC-09, AC-11, AC-14
  - Ficheros: `src/__tests__/bundle-budget.test.ts`, `e2e/map-view.spec.ts`, `e2e/fixtures/*`
  - Verificación: `cd frontend && npm run e2e`

- [ ] **T-07** — Verificación completa.
  - Verificación: `./init.sh verify --e2e`
