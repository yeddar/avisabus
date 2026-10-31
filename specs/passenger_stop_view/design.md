# Vista de parada del pasajero — design

> Feature: `passenger_stop_view` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-06, RF-10, RF-15, RF-32, RNF-01, RNF-03, RNF-04, RNF-05, RNF-14 · Casos de uso: CU-01 · Depende de: stop_arrivals_api, frontend_i18n

## 1. Resumen

```
backend: avisabus openapi export ──▶ frontend/src/shared/api/openapi.json ──▶ openapi-typescript ──▶ schema.d.ts
frontend: StopPage ── useStop / useStopArrivals (TanStack Query) ── apiGet<T>() ── /api/v1/stops/...
```

## 2. Componentes

### Backend

| Módulo | Contenido |
|---|---|
| `adapters/inbound/cli/openapi.py` | `avisabus openapi export --out PATH` |
| `adapters/inbound/http/app.py` | Permitir construir la app solo para obtener el esquema (sin BD ni red) |
| `tests/integration/test_openapi_snapshot.py` | Compara `app.openapi()` con `frontend/src/shared/api/openapi.json` |

Cómo construir la app sin efectos secundarios es **decisión local permitida** (p. ej.
`create_app(settings, container=None)` que registra las rutas sin resolver dependencias). El
JSON se escribe con `indent=2`, claves ordenadas y salto de línea final, para que el diff sea
estable.

### Frontend

```
frontend/src/
├── shared/api/
│   ├── openapi.json          # generado (versionado)
│   ├── schema.d.ts           # generado (versionado)
│   ├── types.ts              # alias: StopResponse, StopArrivalsResponse, Arrival, Occupancy…
│   ├── client.ts             # apiGet<T>(path, { signal }) → T | throw ApiError
│   └── queryClient.ts        # QueryClient con defaults
├── shared/color/contrast.ts  # contrastRatio(), accessibleLineColors()
├── shared/hooks/
│   ├── useOnline.ts
│   └── useServerClock.ts     # offset entre servidor y dispositivo
├── features/passenger/stop/
│   ├── StopPage.tsx          # ruta /p/:stopId
│   ├── StopHeader.tsx
│   ├── LineBadge.tsx
│   ├── ArrivalsList.tsx
│   ├── ArrivalRow.tsx
│   ├── ArrivalTime.tsx
│   ├── OccupancyInfo.tsx
│   ├── SourceNotice.tsx
│   ├── StopNotFound.tsx
│   ├── useStopQueries.ts     # useStop, useStopArrivals
│   ├── useArrivingAnnouncements.ts
│   └── lastStop.ts           # get/setLastStop (safeStorage)
└── app/routes/NotFoundPage.tsx
```

Scripts nuevos en `package.json`:

| Script | Comando |
|---|---|
| `gen:api` | `cd ../backend && uv run avisabus openapi export --out ../frontend/src/shared/api/openapi.json && cd ../frontend && openapi-typescript src/shared/api/openapi.json -o src/shared/api/schema.d.ts && prettier --write src/shared/api` |

Dependencias: `@tanstack/react-query`; dev: `openapi-typescript`.

## 3. Interfaces

```ts
// shared/api/client.ts
export class ApiError extends Error {
  constructor(readonly status: number, readonly type: string | null) { super(`API ${status}`); }
}
export async function apiGet<T>(path: string, init?: { signal?: AbortSignal }): Promise<T>;
// fetch(`/api/v1${path}`, { headers: { Accept: 'application/json' }, signal })
// timeout de 8 s con AbortController combinado; !ok → lee problem+json si lo hay → ApiError(status, type)
// error de red / timeout → ApiError(0, 'network')

// features/passenger/stop/useStopQueries.ts
export function useStop(stopId: string, token: string): UseQueryResult<StopResponse, ApiError>;
export function useStopArrivals(stopId: string, token: string): UseQueryResult<StopArrivalsResponse, ApiError>;
// queryKey: ['stop', stopId, token] / ['arrivals', stopId, token]
// arrivals: refetchInterval = (q) => min(q.state.data?.refresh_after_s ?? 20, 30) * 1000
//           refetchIntervalInBackground: false; refetchOnWindowFocus: true;
//           placeholderData: keepPreviousData; retry: (n, e) => e.status !== 404 && n < 2
//           networkMode: 'online' (no reintenta sin conexión)

// shared/hooks/useServerClock.ts
export function useServerNow(generatedAt: string | undefined, tickMs = 15_000): Date;
// offset = Date.parse(generatedAt) − Date.now() en el momento de recibir la respuesta;
// devuelve new Date(Date.now() + offset), re-renderizando cada tickMs.

// shared/color/contrast.ts
export function contrastRatio(hexA: string, hexB: string): number;            // WCAG 2.x
export function accessibleLineColors(bg: string | null, fg: string | null): { bg: string; fg: string };
// null → neutro ('#1f2937' / '#ffffff'); si ratio < 4.5 oscurece bg en pasos del 5 % (HSL L)
// hasta ≥ 4.5 (máx. 20 pasos; si no, '#000000'/'#ffffff').

// features/passenger/stop/useArrivingAnnouncements.ts
export function useArrivingAnnouncements(arrivals: Arrival[], now: Date): void;
// Para cada (line, destination), toma la primera llegada; si pasa a 0 min (o arrival_at ≤ now)
// y su clave `${line}|${destination}|${vehicle?.trip_id ?? arrival_at}` no se ha anunciado, anuncia
// t('stop.arriving', {line, destination}) con useAnnounce('polite') y la marca como anunciada.

// features/passenger/stop/lastStop.ts
export type LastStop = { stopId: string; name: string; token: string };
export function getLastStop(): LastStop | null;
export function setLastStop(s: LastStop): void;          // clave 'avisabus.lastStop'
```

### Ruta y token

`/p/:stopId` lee `t` de `useSearchParams()`. Si falta `t`, se muestra directamente
`StopNotFound` (sin llamar a la API). El token **nunca** se muestra en pantalla ni se registra
en consola.

### Estructura accesible de la vista

```html
<main id="main">
  <h1><GtfsText>Parc de l'Oest - Enguera</GtfsText></h1>
  <p>Parada 508</p>
  <section aria-labelledby="lines-h"><h2 id="lines-h">Líneas</h2> … LineBadge …</section>
  <section aria-labelledby="arrivals-h">
    <h2 id="arrivals-h">Próximas llegadas</h2>
    <p>Actualizado a las 07:40:12</p> <Button>Actualizar</Button>
    <SourceNotice/> (role="status", solo si SCHEDULED)
    <ul> <li> ArrivalRow </li> … </ul>
  </section>
</main>
```

`ArrivalRow`: contenido visual (badge, destino, tiempo grande, ocupación con icono SVG
`aria-hidden`) + un texto `VisuallyHidden` con la frase completa de AC-05; el contenido visual
lleva `aria-hidden="true"` para que el lector no lo lea dos veces.

Iconos de ocupación: tres SVG propios (una, dos o tres siluetas), `aria-hidden`. Colores:
verde/ámbar/rojo con contraste ≥ 3:1 contra el fondo, siempre acompañados de texto (AC-07).

## 4. Datos (claves i18n nuevas, extracto)

```
stop.title, stop.code ("Parada {{code}}"), stop.lines, stop.arrivals, stop.updatedAt,
stop.refresh, stop.refreshed, stop.empty, stop.scheduledNotice, stop.scheduledSuffix,
stop.arriving ("Línea {{line}} hacia {{destination}} está llegando"),
stop.rowLabel ("Línea {{line}}, hacia {{destination}}, {{time}}, {{occupancy}}"),
stop.arrivesIn ("llega en {{duration}}"), stop.arrivesAt ("llega a las {{time}}"),
stop.notFound.title, stop.notFound.body, stop.error.body, stop.error.retry, stop.stale,
occupancy.FREE, occupancy.MEDIUM, occupancy.FULL, occupancy.seatsYes, occupancy.seatsNo,
occupancy.unavailable, network.offline, home.lastStop, notFound.title, notFound.home
```

## 5. Estrategia de test

| AC | Test |
|---|---|
| AC-01, AC-02 | `backend/tests/integration/test_openapi_snapshot.py`, `test_cli_openapi.py` |
| AC-03 | `client.test.ts` (fetch simulado: 200, problem+json 404/503, error de red, timeout con temporizadores falsos) |
| AC-04–AC-11 | Tests de componentes con `renderWithProviders` y respuestas tipadas de `src/test/fixtures/api/*.json` |
| AC-12–AC-15 | `StopPage.test.tsx` con `vi.useFakeTimers()`, `fetch` simulado y `document.visibilityState` simulado |
| AC-16–AC-18 | `StopPage.errors.test.tsx` |
| AC-19, AC-20 | `lastStop.test.ts`, `HomePage.test.tsx`, `NotFoundPage.test.tsx` |
| AC-21 | `src/__tests__/bundle-budget.test.ts`: suma el tamaño gzip del `<script type="module">` inicial de `dist/index.html` y de sus `modulepreload`; si no existe `dist/`, el test se omite con aviso (ver nota) |
| AC-22 | `e2e/stop-view.spec.ts` con `page.route('**/api/v1/**', …)` sirviendo `e2e/fixtures/*.json` |

*Nota AC-21:* en `./init.sh verify` el paso `test` va antes de `build`. Para no depender del
orden, el script `test:bundle` (`npm run build && vitest run src/__tests__/bundle-budget.test.ts`)
se añade al final de `npm run e2e` (`"e2e": "playwright test && npm run test:bundle"`), que ya
construye la app. Así el presupuesto se verifica con `./init.sh verify --e2e`.

Las fixtures de API del frontend (`src/test/fixtures/api/`, `e2e/fixtures/`) se escriben con los
ejemplos de `specs/stop_arrivals_api/design.md` §3 y se tipan con `types.ts` (si el contrato
cambia, `tsc` las rompe).

## 6. Decisiones locales permitidas

- Maquetación y estilos (respetando contraste, tamaños y foco).
- Diseño de los iconos de ocupación.
- Redacción de textos (manteniendo claves y sentido).

## 7. Preguntas abiertas

Ninguna.
