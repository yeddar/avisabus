# Interfaz del conductor — design

> Feature: `driver_ui` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-24, RF-25, RF-26, RF-27, RF-28, RF-29, RF-30, RF-31, RNF-03, RNF-05 · Casos de uso: CU-08, CU-09, CU-10 · Depende de: frontend_i18n, driver_demand

## 1. Componentes

```
frontend/src/features/driver/
├── session.ts               # token en sessionStorage; driverApi (Authorization: Bearer)
├── LoginPage.tsx            # /driver (AC-01)
├── ShiftPage.tsx            # /driver/shift: ServicePicker o DemandView (AC-02, AC-03)
├── ServicePicker.tsx        # línea → sentido → salida
├── useDriverPosition.ts     # watchPosition + envío cada 5 s + wakeLock (AC-04)
├── useDriverSocket.ts       # /ws/driver (reutiliza shared/ws/reconnect.ts) + respaldo GET view (AC-09)
├── newAlerts.ts             # alert_ids vistos / nuevos (puro, AC-07)
├── tone.ts                  # playTone(): oscilador 880 Hz, 300 ms, envolvente suave (Web Audio)
├── DemandView.tsx           # cabecera de salida, estados, franjas, paradas, plazas, silencio, fin
├── StopCard.tsx             # tarjeta grande / compacta
├── CapacityBanner.tsx       # capacity_alert / seat_alert (AC-06)
├── DriverStatus.tsx         # gps / off_route / conexión / finished (AC-08)
└── EndShiftDialog.tsx       # confirmación (AC-10)
```

Rutas en `src/app/routes.tsx`: `/driver` y `/driver/shift`, cargadas de forma diferida (no
entran en el JavaScript inicial del pasajero; presupuesto de `passenger_stop_view.AC-21`).

## 2. Interfaces

```ts
// features/driver/session.ts
export function getDriverToken(): string | null;          // sessionStorage 'avisabus.driverSession'
export function setDriverToken(token: string): void;
export function clearDriverToken(): void;
export async function driverApi<T>(method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string,
  body?: unknown): Promise<{ status: number; data: T | null; retryAfterS: number | null }>;
// 401 → clearDriverToken() y DriverAuthError (las páginas navegan a /driver, AC-03)

// features/driver/newAlerts.ts
export function diffAlerts(seen: ReadonlySet<string>, view: DriverView, initial: boolean):
  { seen: Set<string>; fresh: { alertId: string; stopId: string }[] };   // initial → fresh = []

// features/driver/useDriverPosition.ts
export function useDriverPosition(enabled: boolean): { permission: 'prompt' | 'granted' | 'denied'; retry(): void };
// envía { lat, lon, accuracy_m: coords.accuracy, recorded_at: new Date(position.timestamp).toISOString() }
```

## 3. Datos (claves i18n, extracto)

```
driver.login.title ("Acceso de conductor"), driver.login.code ("Código de acceso"), driver.login.enter ("Entrar"),
driver.login.invalid ("Código no válido"), driver.login.locked_one/_other,
driver.pick.line, driver.pick.direction, driver.pick.departure, driver.pick.taken ("Ya en servicio"),
driver.pick.back, driver.pick.takenNow,
driver.demand.waiting_one/_other ("{{count}} persona esperando" / "personas esperando"),
driver.demand.none ("Sin solicitudes en las próximas paradas"), driver.demand.new ("Nueva"),
driver.needs.RAMP_one/_other ("{{count}} rampa"/"rampas"), …EXTRA_TIME ("más tiempo"), …SEAT ("asiento"), …VISUAL ("visión"),
driver.places ("{{places}} plazas libres · {{seats}} asientos"), driver.places.unknown,
driver.capacity ("Esperan {{waiting}} personas y quedan {{places}} plazas"),
driver.seats ("Piden asiento {{requests}} personas y quedan {{seats}} asientos"),
driver.gps.waiting, driver.gps.stale, driver.gps.denied, driver.offRoute, driver.offline,
driver.finished ("Fin del recorrido"), driver.nextDeparture ("Elegir la siguiente salida"),
driver.mute ("Silenciar tono"), driver.unmute ("Activar tono"),
driver.end ("Finalizar turno"), driver.end.confirm ("¿Finalizar el turno?"), driver.end.yes ("Finalizar"), driver.end.no ("Seguir"),
driver.closed.ENDED ("Turno finalizado"), .IDLE ("Turno cerrado por inactividad"), .REVOKED ("Código revocado"),
.REPLACED ("Has iniciado otro turno con este código")
```

## 4. Estrategia de test

| AC | Test |
|---|---|
| AC-01–AC-03 | `LoginPage.test.tsx`, `ServicePicker.test.tsx`, `ShiftPage.test.tsx` |
| AC-04 | `useDriverPosition.test.tsx` (geolocalización y `wakeLock` simulados) |
| AC-05, AC-06, AC-08 | `DemandView.test.tsx`, `CapacityBanner.test.tsx`, `DriverStatus.test.tsx` |
| AC-07 | `newAlerts.test.ts`, `DemandView.tone.test.tsx` (`AudioContext` simulado) |
| AC-09, AC-10 | `useDriverSocket.test.tsx`, `EndShiftDialog.test.tsx`, `ShiftPage.test.tsx` |
| AC-11 | `e2e/driver.spec.ts` (`page.route`, `page.routeWebSocket`, `context.setGeolocation`, `grantPermissions(['geolocation'])`), perfil `tablet-landscape` |
| AC-12 | Revisión de capturas de `e2e/driver.spec.ts` (acceso, elección de salida, vista sin solicitudes, con solicitud nueva, con alerta de capacidad, GPS desactualizado, fin del recorrido) |

## 5. Decisiones locales permitidas

- Maquetación no fijada por `docs/design.md` §5.9; envolvente del tono.

## 6. Preguntas abiertas

Ninguna.
