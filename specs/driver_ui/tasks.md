# Interfaz del conductor — tasks

> Feature: `driver_ui` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-24, RF-25, RF-26, RF-27, RF-28, RF-29, RF-30, RF-31, RNF-03, RNF-05 · Casos de uso: CU-08, CU-09, CU-10 · Depende de: frontend_i18n, driver_demand

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — `session.ts`, `driverApi`, `LoginPage` y rutas diferidas.
  - AC: driver_ui.AC-01, AC-03
  - Ficheros: `src/features/driver/{session.ts,LoginPage.tsx}`, `src/app/routes.tsx`, `src/locales/**`, tests
  - Verificación: `cd frontend && npm run test -- LoginPage session`

- [ ] **T-02** — `ServicePicker` y `ShiftPage` (sin vista de demanda todavía).
  - AC: driver_ui.AC-02, AC-03
  - Ficheros: `src/features/driver/{ServicePicker,ShiftPage}.tsx`, `src/locales/**`, tests
  - Verificación: `cd frontend && npm run test -- ServicePicker ShiftPage`

- [ ] **T-03** — `useDriverPosition` (posición, permiso, `wakeLock`).
  - AC: driver_ui.AC-04
  - Ficheros: `src/features/driver/useDriverPosition.ts`, tests
  - Verificación: `cd frontend && npm run test -- useDriverPosition`

- [ ] **T-04** — `useDriverSocket`, `newAlerts`, `tone`.
  - AC: driver_ui.AC-07, AC-09
  - Ficheros: `src/features/driver/{useDriverSocket,newAlerts,tone}.ts`, tests
  - Verificación: `cd frontend && npm run test -- useDriverSocket newAlerts`

- [ ] **T-05** — `DemandView`, `StopCard`, `CapacityBanner`, `DriverStatus`, `EndShiftDialog`,
  silencio y cierre por el servidor.
  - AC: driver_ui.AC-05, AC-06, AC-07, AC-08, AC-10
  - Ficheros: `src/features/driver/*.tsx`, `src/locales/**`, tests
  - Verificación: `cd frontend && npm run test -- driver`

- [ ] **T-06** — E2E del flujo completo, axe y capturas.
  - AC: driver_ui.AC-11, AC-12
  - Ficheros: `e2e/driver.spec.ts`, `e2e/fixtures/driver/*`
  - Verificación: `cd frontend && npm run e2e`

- [ ] **T-07** — Verificación completa.
  - Verificación: `./init.sh verify --e2e`
