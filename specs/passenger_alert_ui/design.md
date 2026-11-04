# Interfaz de la solicitud de parada — design

> Feature: `passenger_alert_ui` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-16, RF-17, RF-18, RF-19, RF-22, RF-23, RNF-02, RNF-03, RNF-04, RNF-05, RNF-06 · Casos de uso: CU-03, CU-04, CU-05, CU-07 · Depende de: passenger_stop_view, alert_create, alert_cancel, alert_expiry

## 1. Resumen

```
StopPage ── AlertsProvider (estado de las solicitudes del dispositivo)
              ├─ usePassengerSocket (/ws/passenger: hello → snapshot → eventos; reconexión)
              ├─ respaldo: GET /alerts/mine cada 30 s mientras está desconectado
              └─ acciones: createAlert (POST) · cancelAlert (DELETE)
ArrivalRow ── AlertAction: "Solicitar" | estado + "Cancelar solicitud" | "Ya has solicitado…"
RequestDialog (<dialog>) ── NeedsFieldset · "Recordar…" · "Solicitar parada" / "Volver"
NeedsPage (/necesidades)
```

## 2. Componentes

```
frontend/src/
├── shared/device/
│   ├── deviceId.ts            # getDeviceId() (AC-01)
│   └── needsProfile.ts        # get/set/clearNeedsProfile()
├── shared/api/client.ts       # + apiSend<T>(method, path, body?) con X-Device-Id (ampliación)
├── shared/ws/
│   ├── reconnect.ts           # nextDelay(attempt, random) (puro)
│   └── usePassengerSocket.ts
├── features/passenger/alerts/
│   ├── AlertsProvider.tsx     # contexto: alerts, create, cancel, estado de conexión
│   ├── alertsReducer.ts       # snapshot / registered / delivered / expired / cancelled (puro)
│   ├── alertMessages.ts       # textos de anuncio por evento (puro)
│   ├── AlertAction.tsx        # en ArrivalRow (AC-03, AC-07)
│   ├── AlertStatus.tsx        # estado + necesidades + "Cancelar solicitud"
│   ├── OrphanAlerts.tsx       # solicitudes cuyo autobús no está en la lista (AC-08)
│   ├── RequestDialog.tsx      # AC-04 … AC-06
│   ├── NeedsFieldset.tsx      # cuatro casillas (reutilizado en NeedsPage)
│   └── NeedsPage.tsx          # /necesidades (AC-02)
└── shared/ui/icons/HandIcon.tsx   # icono de "Solicitar" (docs/design.md §6)
```

Cambios en código existente: `ArrivalRow` (fila de acciones con `AlertAction`), `StopPage`
(`AlertsProvider`, `OrphanAlerts`, foco al `h2`), `HomePage` (enlace "Mis necesidades"),
`routes.tsx` (`/necesidades`), `client.ts` (`apiSend`), `storage.ts` (comentario de claves).

## 3. Interfaces

```ts
// shared/device/deviceId.ts
export function getDeviceId(): string;   // 'avisabus.deviceId'; si no hay almacenamiento, uno en memoria

// shared/device/needsProfile.ts
export type Need = 'RAMP' | 'EXTRA_TIME' | 'SEAT' | 'VISUAL';   // de los tipos generados
export function getNeedsProfile(): Need[];                     // 'avisabus.needsProfile' (JSON); inválido → []
export function setNeedsProfile(needs: Need[]): void;
export function clearNeedsProfile(): void;

// shared/api/client.ts (ampliación)
export async function apiSend<T>(method: 'POST' | 'DELETE', path: string,
  body?: unknown, init?: { signal?: AbortSignal }): Promise<{ status: number; data: T | null; retryAfterS: number | null }>;
// Añade X-Device-Id (getDeviceId) y Content-Type JSON; mismos errores que apiGet (ApiError con
// status y type); para 429 rellena retryAfterS desde Retry-After.

// shared/ws/reconnect.ts
export const RECONNECT_STEPS_S = [1, 2, 4, 8, 16, 30];
export function nextDelayMs(attempt: number, random: () => number = Math.random): number;
// base = RECONNECT_STEPS_S[min(attempt, 5)] · 1000 · (0,8 + 0,4 · random())

// shared/ws/usePassengerSocket.ts
export function usePassengerSocket(onMessage: (m: PassengerMessage) => void): { connected: boolean };
// URL: `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/passenger`
// al abrir: send({type:'hello', device_id: getDeviceId()}); 'ping' → send({type:'pong'});
// cierre → reconexión con nextDelayMs (pausada con useOnline() = false); reset del contador tras snapshot.

// features/passenger/alerts/alertsReducer.ts
export type AlertsState = { alerts: Record<string, Alert> };
export type PassengerMessage =
  | { type: 'alerts.snapshot'; alerts: Alert[] }
  | { type: 'alert.registered' | 'alert.delivered'; alert: Alert }
  | { type: 'alert.expired'; alert_id: string; reason: 'PASSED' | 'NEXT_STOP' | 'TIMEOUT' }
  | { type: 'alert.cancelled'; alert_id: string }
  | { type: 'ping' };
export function alertsReducer(state: AlertsState, m: PassengerMessage | { type: 'local.created'; alert: Alert }
  | { type: 'local.removed'; alert_id: string }): AlertsState;

// features/passenger/alerts/AlertsProvider.tsx
export function useAlerts(): {
  alertFor(stopId: string, line: string): Alert | null;          // RF-19
  alertsAt(stopId: string): Alert[];
  create(input: CreateAlertInput): Promise<CreateOutcome>;      // 'ok' | {error:'gone'|'rate'|'notFound'|'network', retryAfterS?}
  cancel(alertId: string): Promise<'ok' | 'gone' | 'network'>;
};
```

Correspondencia tarjeta ↔ solicitud: `alert.trip_id === arrival.vehicle?.trip_id &&
alert.service_date === arrival.vehicle?.service_date`.

### Diálogo (AC-04)

`<dialog aria-labelledby="req-title">` abierto con `showModal()` (el navegador gestiona el foco
atrapado y Escape). Al abrir, foco en `h2#req-title` (`tabIndex=-1`). Al cerrar sin solicitar
(`close` o `cancel`), foco al botón "Solicitar" que lo abrió. Casillas en un `<fieldset>` con
`<legend>` "¿Necesitas algo al subir?". El mensaje de error (AC-06) es un `<p role="alert"
tabIndex=-1>` que recibe el foco.

### Gestión del foco cuando desaparece un control (AC-11)

Antes de aplicar un mensaje que quita una solicitud, se comprueba si `document.activeElement`
está dentro de su `AlertStatus`; si es así, tras pintar se enfoca el "Solicitar" de la tarjeta
(`ref` registrado por `trip_id`) o el `h2` "Próximas llegadas".

## 4. Datos (claves i18n nuevas, extracto)

```
alert.request ("Solicitar"), alert.requestLabel ("Solicitar parada a la línea {{line}} hacia {{destination}}"),
alert.dialogTitle, alert.arrivalInfo, alert.needsLegend ("¿Necesitas algo al subir?"),
alert.remember ("Recordar mis necesidades en este dispositivo"), alert.confirm ("Solicitar parada"),
alert.back ("Volver"), alert.sending ("Enviando…"), alert.requested ("Parada solicitada para la línea {{line}}"),
alert.pending, alert.delivered, alert.youIndicated ("Has indicado: {{needs}}"), alert.cancel ("Cancelar solicitud"),
alert.cancelled, alert.alreadyGone, alert.cancelFailed, alert.otherBus ("Ya has solicitado otro autobús de esta línea"),
alert.error.gone, alert.error.rate_one/_other, alert.error.notFound, alert.error.network,
alert.event.delivered, alert.event.expired, alert.event.reason.PASSED|NEXT_STOP|TIMEOUT,
needs.RAMP ("Necesito la rampa"), needs.EXTRA_TIME ("Necesito más tiempo para subir"), needs.SEAT ("Necesito un asiento"),
needs.VISUAL ("Tengo discapacidad visual"), needs.short.RAMP ("rampa") … ("más tiempo", "asiento", "discapacidad visual"),
needsPage.title ("Mis necesidades"), needsPage.intro, needsPage.save ("Guardar"), needsPage.clear ("Borrar mis necesidades"),
needsPage.saved ("Necesidades guardadas"), needsPage.cleared ("Necesidades borradas"), home.needsLink ("Mis necesidades")
```

Valenciano (referencia; redacción final del implementer, revisada en CP-6): "Sol·licita",
"Sol·licita parada a la línia {{line}} cap a {{destination}}", "Necessites alguna cosa en pujar?",
"Recorda les meues necessitats en este dispositiu", "Sol·licita la parada", "Torna", "Enviant…",
"Parada sol·licitada. Encara no hi ha cap conductor connectat en esta línia.", "El conductor ha
rebut la teua sol·licitud.", "Cancel·la la sol·licitud", "Necessite la rampa", "Necessite més
temps per a pujar", "Necessite un seient", "Tinc discapacitat visual", "Les meues necessitats".

La lista de necesidades en "Has indicado:" usa `Intl.ListFormat` del idioma activo
("rampa y asiento" / "rampa i seient").

## 5. Estrategia de test

| AC | Test |
|---|---|
| AC-01, AC-02 | `deviceId.test.ts`, `needsProfile.test.ts`, `NeedsPage.test.tsx`, `HomePage.test.tsx` |
| AC-03, AC-07 | `AlertAction.test.tsx` |
| AC-04–AC-06 | `RequestDialog.test.tsx` (jsdom: `HTMLDialogElement.showModal` simulado en `src/test/setup.ts` si falta) + e2e de teclado |
| AC-08, AC-09, AC-11 | `StopPage.alerts.test.tsx` con API y WebSocket simulados (clase `FakeWebSocket` en `src/test/`) |
| AC-10 | `reconnect.test.ts`, `usePassengerSocket.test.tsx` (temporizadores falsos, `online`/`offline`) |
| AC-11 | `alertsReducer.test.ts`, `alertMessages.test.ts` |
| AC-12 | `e2e/alerts.spec.ts` con `page.route('**/api/v1/**')` y `page.routeWebSocket('**/ws/passenger')` |
| AC-13 | Revisión de capturas de `e2e/alerts.spec.ts` (tarjeta con y sin solicitud, diálogo abierto, error 429, aviso de solicitud huérfana, "Mis necesidades") |

## 6. Decisiones locales permitidas

- Maquetación no fijada por `docs/design.md`.
- Redacción de los textos (manteniendo claves y sentido).
- Implementación del WebSocket simulado de los tests.

## 7. Preguntas abiertas

Ninguna.
