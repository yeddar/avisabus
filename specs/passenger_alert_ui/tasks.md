# Interfaz de la solicitud de parada — tasks

> Feature: `passenger_alert_ui` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-16, RF-17, RF-18, RF-19, RF-22, RF-23, RNF-02, RNF-03, RNF-04, RNF-05, RNF-06 · Casos de uso: CU-03, CU-04, CU-05, CU-07 · Depende de: passenger_stop_view, alert_create, alert_cancel, alert_expiry

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — `getDeviceId`, perfil de necesidades, `apiSend` con `X-Device-Id` y
  `Retry-After`; comentario de claves de `storage.ts`.
  - AC: passenger_alert_ui.AC-01
  - Ficheros: `src/shared/device/{deviceId,needsProfile,storage}.ts`, `src/shared/api/client.ts`, tests
  - Verificación: `cd frontend && npm run test -- deviceId needsProfile client`

- [ ] **T-02** — `NeedsFieldset`, `NeedsPage` (`/necesidades`) y enlace en la portada.
  - AC: passenger_alert_ui.AC-02
  - Ficheros: `src/features/passenger/alerts/{NeedsFieldset,NeedsPage}.tsx`, `src/app/routes.tsx`, `src/app/routes/HomePage.tsx`, `src/locales/**`, tests
  - Verificación: `cd frontend && npm run test -- NeedsPage HomePage`

- [ ] **T-03** — Reconexión, `usePassengerSocket`, `alertsReducer`, `alertMessages` y
  `AlertsProvider` (con respaldo `GET /alerts/mine`).
  - AC: passenger_alert_ui.AC-10, AC-11
  - Ficheros: `src/shared/ws/*`, `src/features/passenger/alerts/{alertsReducer,alertMessages,AlertsProvider}.ts(x)`, `src/test/FakeWebSocket.ts`, tests
  - Verificación: `cd frontend && npm run test -- reconnect usePassengerSocket alertsReducer alertMessages`

- [ ] **T-04** — `AlertAction`, `AlertStatus`, `HandIcon` y fila de acciones de `ArrivalRow`.
  - AC: passenger_alert_ui.AC-03, AC-07
  - Ficheros: `src/features/passenger/alerts/{AlertAction,AlertStatus}.tsx`, `src/shared/ui/icons/HandIcon.tsx`, `src/features/passenger/stop/ArrivalRow.tsx`, `src/locales/**`, tests
  - Verificación: `cd frontend && npm run test -- AlertAction ArrivalRow`

- [ ] **T-05** — `RequestDialog` (diálogo, envío, errores, foco).
  - AC: passenger_alert_ui.AC-04, AC-05, AC-06
  - Ficheros: `src/features/passenger/alerts/RequestDialog.tsx`, `src/test/setup.ts`, `src/locales/**`, tests
  - Verificación: `cd frontend && npm run test -- RequestDialog`

- [ ] **T-06** — Integración en `StopPage`: `AlertsProvider`, `OrphanAlerts`, cancelación,
  anuncios y foco cuando desaparece un control.
  - AC: passenger_alert_ui.AC-08, AC-09, AC-11
  - Ficheros: `src/features/passenger/alerts/OrphanAlerts.tsx`, `src/features/passenger/stop/StopPage.tsx`, `StopPage.alerts.test.tsx`
  - Verificación: `cd frontend && npm run test -- StopPage`

- [ ] **T-07** — E2E con API y WebSocket simulados, axe y capturas para la revisión visual.
  - AC: passenger_alert_ui.AC-04, AC-12, AC-13
  - Ficheros: `e2e/alerts.spec.ts`, `e2e/fixtures/*`
  - Verificación: `cd frontend && npm run e2e`

- [ ] **T-08** — Verificación completa.
  - Verificación: `./init.sh verify --e2e`
