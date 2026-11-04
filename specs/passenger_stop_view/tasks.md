# Vista de parada del pasajero — tasks

> Feature: `passenger_stop_view` · Versión: 1.3 · Estado: APPROVED
> Requisitos: RF-06, RF-10, RF-15, RF-32, RNF-01, RNF-03, RNF-04, RNF-05, RNF-14 · Casos de uso: CU-01 · Depende de: stop_arrivals_api, frontend_i18n

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Backend: comando `avisabus openapi export` (sin BD ni red) y test de desfase
  contra `frontend/src/shared/api/openapi.json`.
  - AC: passenger_stop_view.AC-01, AC-02
  - Ficheros: `backend/src/avisabus/adapters/inbound/cli/openapi.py`, `backend/src/avisabus/adapters/inbound/http/app.py`, `backend/tests/integration/test_cli_openapi.py`, `backend/tests/integration/test_openapi_snapshot.py`
  - Verificación: `cd backend && uv run pytest tests/integration/test_cli_openapi.py tests/integration/test_openapi_snapshot.py`

- [ ] **T-02** — Frontend: script `gen:api`, `openapi.json` y `schema.d.ts` generados, `types.ts`,
  `client.ts` con `ApiError` y timeout, `QueryClient` en `App`.
  - AC: passenger_stop_view.AC-03
  - Ficheros: `frontend/package.json`, `frontend/src/shared/api/**`, `frontend/src/app/App.tsx`
  - Verificación: `cd frontend && npm run gen:api && npm run typecheck && npm run test -- client`

- [ ] **T-03** — Utilidades: `contrastRatio` / `accessibleLineColors`, `useOnline`,
  `useServerNow`, `lastStop`.
  - AC: passenger_stop_view.AC-11, AC-13, AC-18, AC-19
  - Ficheros: `src/shared/color/contrast.ts`, `src/shared/hooks/*`, `src/features/passenger/stop/lastStop.ts`, tests
  - Verificación: `cd frontend && npm run test -- contrast useServerNow useOnline lastStop`

- [ ] **T-04** — Componentes de presentación: `LineBadge`, `ArrivalTime`, `OccupancyInfo` (iconos),
  `ArrivalRow` (texto accesible; destino visible y hablado con `destination.ts`), `ArrivalsList`,
  `SourceNotice`, estado vacío; claves i18n en ambos idiomas; estilos según `docs/design.md`.
  - AC: passenger_stop_view.AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11
  - Ficheros: `src/features/passenger/stop/*.tsx`, `src/features/passenger/stop/destination.ts`, `src/locales/**`, `src/test/fixtures/api/*.json`, tests
  - Verificación: `cd frontend && npm run test -- passenger/stop`

- [ ] **T-05** — `useStopQueries` y `StopPage` (ruta `/p/:stopId`, cabecera, título, refresco con
  pausa en segundo plano, cuenta atrás, botón Actualizar, "Actualizado a las…").
  - AC: passenger_stop_view.AC-04, AC-12, AC-13, AC-14
  - Ficheros: `src/features/passenger/stop/{StopPage,StopHeader,useStopQueries}.ts(x)`, `src/app/routes.tsx`, tests
  - Verificación: `cd frontend && npm run test -- StopPage`

- [ ] **T-06** — Anuncios de "llegando" (`useArrivingAnnouncements`) sin anuncios en refrescos
  rutinarios.
  - AC: passenger_stop_view.AC-15
  - Ficheros: `src/features/passenger/stop/useArrivingAnnouncements.ts`, tests
  - Verificación: `cd frontend && npm run test -- useArrivingAnnouncements`

- [ ] **T-07** — Errores y conectividad: `StopNotFound` (404 y sin token), error con reintento y
  datos conservados, aviso sin conexión.
  - AC: passenger_stop_view.AC-16, AC-17, AC-18
  - Ficheros: `src/features/passenger/stop/{StopNotFound,StopPage}.tsx`, `StopPage.errors.test.tsx`
  - Verificación: `cd frontend && npm run test -- StopPage.errors`

- [ ] **T-08** — Última parada en la portada y `NotFoundPage` para rutas desconocidas.
  - AC: passenger_stop_view.AC-19, AC-20
  - Ficheros: `src/app/routes/{HomePage,NotFoundPage}.tsx`, `src/app/routes.tsx`, tests
  - Verificación: `cd frontend && npm run test -- HomePage NotFoundPage`

- [ ] **T-09** — E2E con API simulada (tiempo real, programado, vacío, no encontrada) en `es` y
  `ca`, con axe y capturas para la revisión visual; presupuesto de bundle (`test:bundle`
  encadenado a `e2e`).
  - AC: passenger_stop_view.AC-04, AC-16, AC-21, AC-22, AC-23
  - Ficheros: `e2e/stop-view.spec.ts`, `e2e/fixtures/*.json`, `src/__tests__/bundle-budget.test.ts`, `package.json`
  - Verificación: `cd frontend && npm run e2e`

- [ ] **T-11** — (v1.1) Anuncio y foco tras "Actualizar"/"Reintentar" (AC-24); mensaje de error
  sobre "los datos" y "Reintentar" que repite también la petición de la parada (AC-17); clave
  `stop.refreshFailed` en ambos idiomas; corregir el comentario de `shared/device/storage.ts` con
  la lista de `docs/conventions.md` §4.
  - AC: passenger_stop_view.AC-17, AC-24
  - Ficheros: `src/features/passenger/stop/StopPage.tsx`, `src/shared/device/storage.ts`, `src/locales/**`, `StopPage.errors.test.tsx`
  - Verificación: `cd frontend && npm run test -- StopPage`

- [ ] **T-12** — (v1.2) Foco tras acción manual con `404` (al `h1` de "Parada no encontrada") y
  tras un refresco automático que acierta con el foco en "Reintentar" (a "Actualizar").
  - AC: passenger_stop_view.AC-24
  - Ficheros: `src/features/passenger/stop/{StopPage,StopNotFound}.tsx`, `StopPage.errors.test.tsx`
  - Verificación: `cd frontend && npm run test -- StopPage`

- [ ] **T-13** — (v1.3) Presupuesto de bundle solo sobre un `dist/` recién construido: `npm run test`
  lo omite, `npm run test:bundle` construye y lo ejecuta, `./init.sh verify` lo ejecuta tras el
  build con y sin `--e2e`, y `npm run e2e` deja de encadenarlo.
  - AC: passenger_stop_view.AC-21
  - Ficheros: `frontend/package.json`, `frontend/vite.config.ts`, `src/__tests__/bundle-budget.test.ts`, `init.sh`
  - Verificación: `rm -rf frontend/dist && ./init.sh verify` en verde; con un `dist/` manipulado, `npm run test` no lo lee

- [ ] **T-10** — Verificación completa.
  - Verificación: `./init.sh verify --e2e`
