# Implementación: passenger_stop_view
Spec: specs/passenger_stop_view/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Rama: `feat/passenger_stop_view`

## Tareas
- [x] T-01 Backend: `avisabus openapi export` y test de desfase (commit 75f6a97)
- [x] T-02 Frontend: `gen:api`, tipos generados, `client.ts`, `QueryClient` (commit ff2196a)
- [x] T-03 Utilidades: contraste, `useOnline`, `useServerNow`, `lastStop` (commit 5b5de9b)
- [x] T-04 Componentes de presentación (commit b324eb6)
- [x] T-05 `useStopQueries` y `StopPage` (commit b8d5534)
- [x] T-06 Anuncios de "llegando" (commit f541dd3)
- [x] T-07 Errores y conectividad (commit c2950cb)
- [x] T-08 Última parada y `NotFoundPage` (commit 544cb50)
- [x] T-09 E2E, axe, capturas y presupuesto de bundle (commit 2114105)
- [x] T-10 Verificación completa: `CI=1 ./init.sh verify --e2e` en verde (ver "Verificación")

Cada test se escribió antes que el código y se vio en rojo (fallo de importación o de aserción).
Además, se comprobó con mutaciones temporales (revertidas) que los tests de AC-12
(`refetchIntervalInBackground`/`refetchOnWindowFocus`), AC-13 (sin corrección del reloj) y AC-18
(`networkMode: 'always'` / sin sincronizar `onlineManager`) fallan si se rompe el comportamiento.

### Matriz AC → test
| AC | Evidencia |
|---|---|
| AC-01 | `backend/tests/integration/test_cli_openapi.py` (sin BD: la URL apunta a un fichero que no se crea; sockets bloqueados; sin importar `avisabus.main`; salida estable `indent=2`, claves ordenadas, salto final; funciona con `AVISABUS_ENV=prod` sin secreto) |
| AC-02 | `backend/tests/integration/test_openapi_snapshot.py` (copia real del frontend + copia desfasada / ausente → fallo con "run `npm run gen:api` in frontend/"; las diferencias solo de formato no cuentan) |
| AC-03 | `src/shared/api/__tests__/client.test.ts` (200, problem+json 404/503, error sin problem+json, problem+json mal formado, error de red, timeout de 8 s con temporizadores falsos, aborto del llamante, cuerpo ilegible) |
| AC-04 | `StopPage.test.tsx` (h1 con `lang`, "Parada 508", líneas sin duplicar, título, URL pedida; también en `ca`) + e2e |
| AC-05 | `destination.test.ts` (3 casos), `ArrivalRow.test.tsx` (tiempo real con y sin sentido, programado, valenciano, `aria-hidden` y `lang`), `ArrivalsList.test.tsx` (orden de la API) |
| AC-06 | `ArrivalTime.test.tsx` ("N min", "Llegando"/"Arribant", `HH:MM` en Europe/Madrid) |
| AC-07 | `OccupancyInfo.test.tsx` (texto + icono con 1/2/3/0 siluetas rellenas, `null`, colores de `docs/design.md` §4, ambos idiomas), `ArrivalRow.test.tsx` |
| AC-08 | `ArrivalRow.test.tsx` (N4: tiempo, sin ocupación, sin acciones; frase sin ocupación) |
| AC-09 | `SourceNotice.test.tsx` (`role="status"`, primera frase en `<strong>`), `ArrivalTime.test.tsx`, `ArrivalsList.test.tsx` ("programado" en pantalla y en la frase) + e2e |
| AC-10 | `ArrivalsList.test.tsx` (es/ca) + e2e |
| AC-11 | `src/shared/color/__tests__/contrast.test.ts` (WCAG, oscurecido por pasos, respaldo negro/blanco, neutro), `LineBadge.test.tsx` |
| AC-12 | `StopPage.test.tsx` (cada `refresh_after_s`, tope de 30 s, lista conservada durante la petición, pausa con la pestaña oculta y petición inmediata al volver) |
| AC-13 | `src/shared/hooks/__tests__/useServerNow.test.tsx`, `ArrivalTime.test.tsx` (`currentMinutes`), `StopPage.test.tsx` (reloj del dispositivo 2 min adelantado, tic de 15 s) |
| AC-14 | `StopPage.test.tsx` ("Actualizado a las 08:40:00", botón → petición inmediata → anuncio educado "Datos actualizados" solo al terminar) |
| AC-15 | `useArrivingAnnouncements.test.tsx` (10 casos), `StopPage.test.tsx` (refresco que pasa a 0 → un anuncio; refrescos rutinarios sin anuncios), `StopPage.errors.test.tsx` (refresco fallido sin anuncios) |
| AC-16 | `StopPage.errors.test.tsx` (404 de parada o de llegadas, es/ca, sin `stop_id` ni token; sin token no llama a la API; un 404 ni se reintenta ni se refresca) + e2e |
| AC-17 | `StopPage.errors.test.tsx` (503 y error de red con "Reintentar"; parada con 503 reintenta ambas; datos conservados con "Datos de las 08:40, pueden no estar actualizados" es/ca) + e2e |
| AC-18 | `src/shared/hooks/__tests__/useOnline.test.tsx`, `StopPage.errors.test.tsx` (aviso `role="status"`, sin peticiones mientras no hay conexión, petición al volver; abierta sin conexión no llama a la API) + e2e |
| AC-19 | `lastStop.test.ts`, `StopPage.test.tsx` (se recuerda al cargar; no si 404), `src/app/routes/HomePage.test.tsx` (enlace es/ca, `lang`, URL codificada) + e2e |
| AC-20 | `src/app/routes/NotFoundPage.test.tsx` (`/no-existe`, `/p`, `/p/508/otra`, enlace a la portada) + e2e |
| AC-21 | `src/__tests__/bundle-budget.test.ts` (cálculo sobre un `dist` sintético + `dist/` real; encadenado a `npm run e2e` vía `test:bundle`). Medido: **138,7 KB** gzip |
| AC-22 | `e2e/stop-view.spec.ts`: tiempo real, programado, sin llegadas y parada no encontrada × `es`/`ca` × iPhone 14 / Pixel 7 / iPad landscape, axe WCAG 2.1 A/AA sin violaciones (también en error, sin conexión, portada con última parada y página no encontrada) |
| AC-23 | Revisión con capturas (ver abajo) |

### Capturas para la revisión visual (AC-23)
`npm run e2e` (o `CI=1 ./init.sh verify --e2e`) las regenera en cada ejecución en la ruta que
indica el design: `frontend/test-results/passenger_stop_view/<perfil>/<nombre>.png`, con
`<perfil>` = `iphone`, `pixel`, `tablet-landscape`; página completa, animaciones desactivadas y
tras `document.fonts.ready`. `test-results/` está en el `.gitignore` de la raíz (no se versiona)
y Playwright la vacía al empezar cada ejecución.

| Fichero | Contenido |
|---|---|
| `stop-realtime-es.png` / `-ca.png` | Tiempo real: "Llegando", "4 min", sentido sin resolver con "Ocupación no disponible", lleno, N4 fuera de red |
| `stop-realtime-es-refresh-focused.png` / `-ca-…` | Botón "Actualizar" con el contorno de foco |
| `stop-scheduled-es.png` / `-ca.png` | Aviso de horario programado y "programado" bajo cada hora |
| `stop-empty-es.png` / `-ca.png` | Sin llegadas |
| `stop-not-found-es.png` / `-ca.png` | Parada no encontrada |
| `stop-error-stale-es.png` | Error con "Reintentar" y datos conservados ("Datos de las 08:40…") |
| `stop-offline-es.png` | Aviso "Sin conexión" |
| `home-last-stop-es.png` | Portada con "Tu última parada" |
| `not-found-es.png` | Página no encontrada |

Las he revisado en los tres perfiles: tipografía, distintivos (rojo EMT corregido a `#e50000`,
N4 neutro), tarjeta con borde, radio y separaciones de §5.3, insignias de ocupación con icono y
texto de §5.4, botones secundarios de §5.5 y avisos de §5.6; en tablet el contenido se centra a
640 px.

## Decisiones locales
Dentro de lo que permite el design §6 (maquetación no fijada por `docs/design.md`, trazado de
iconos y redacción de textos) y de detalles internos no contractuales:

- **Backend (T-01):** `create_app(..., schema_only=True)` registra el router de paradas sin
  casos de uso; `openapi_document()` lo construye con `Settings.model_construct()` (no lee `.env`
  ni valida la configuración). JSON con `ensure_ascii=False` (diffs legibles). El test de desfase
  compara **valores JSON**, no texto, porque `gen:api` pasa Prettier sobre `openapi.json` (y
  `format:check` lo exige formateado).
- **Cliente HTTP:** si el **llamante** aborta (`signal` de TanStack Query al cancelar), se
  relanza el error de aborto tal cual (no es un error de red); un cuerpo 200 ilegible se trata
  como error de red (`ApiError(0, 'network')`).
- **`useStop`:** `staleTime: Infinity` (nombre y líneas no cambian mientras la vista está
  abierta). **`useStopArrivals`:** además del design, `refetchInterval` devuelve `false` tras un
  404 (no se sigue preguntando por una parada inexistente).
- **Conexión:** TanStack Query v5 arranca siempre "en línea" sin mirar `navigator.onLine`;
  `createQueryClient()` configura `onlineManager.setEventListener` para tomar el estado inicial
  del navegador (AC-18: abierta sin conexión no llama a la API).
- **Cuenta atrás (AC-13):** minutos = `ceil((arrival_at − ahora_servidor) / 60 s)`, nunca
  negativos ni mayores que `minutes` de la API (al recibir la respuesta se ve lo mismo que dice
  la API). `useServerNow` toma el desfase cuando aparece un `generated_at` nuevo.
- **Anuncios (AC-15):** se interpreta "pase a 'Llegando'" como transición: (a) solo llegadas
  `MINUTES` (las `CLOCK_TIME` nunca muestran "Llegando", AC-06); (b) no se anuncian los autobuses
  que ya llegaban cuando aparecen los primeros datos (la lista ya lo dice); (c) sin vehículo, la
  clave del design cambia en cada refresco porque `arrival_at` se mueve: si el grupo ya estaba
  "Llegando" en la evaluación anterior se considera el mismo autobús y no se repite ("una sola
  vez"). Varios a la vez → un único mensaje con frases separadas por ". ".
- **Textos accesibles:** la frase de la llegada marca el destino con `lang="ca-ES-valencia"` en
  castellano (`frontend_i18n.AC-06`), usando `<Trans>` con `<destination>`; por eso
  `stop.rowLabel` lleva esa etiqueta. Claves añadidas al extracto del design §4:
  `stop.lineName`, `stop.scheduledTime`, `stop.minutes`, `stop.rowLabelNoOccupancy` (AC-08),
  `stop.arrivingNow`, `stop.loading`, `occupancy.spoken.*`, `occupancy.spokenWithSeats`,
  `notFound.body`.
- **Avisos (§5.6):** componente compartido `shared/ui/StatusNotice.tsx`; el aviso de error no es
  región viva (un refresco automático fallido no debe anunciarse, AC-15); los de horario
  programado y sin conexión llevan `role="status"` (AC-09, AC-18). Con error se sustituye
  "Actualizado a las…" + "Actualizar" por el texto de datos antiguos, y el aviso trae "Reintentar".
- **Maquetación:** h1 28 px; "Parada 508" 16 px `text-muted`; rótulo "Líneas" como `h2` con
  estilo de rótulo secundario (15 px, mayúsculas); líneas sin duplicar (la API da una entrada
  por sentido) con texto oculto "Línea 70" y distintivo `aria-hidden`; mientras carga, `h1`
  "Parada" (`stop.title`) y "Cargando las próximas llegadas…". Listas con `role="list"` (Safari
  con VoiceOver pierde la semántica con `list-style: none`; `eslint-disable` justificado).
  `StopNotFound` incluye también el enlace "Ir a la portada". La última parada en la portada es
  un `LinkButton` secundario.
- **Iconos propios:** `InfoIcon`, `RefreshIcon` (en `shared/ui/icons/`) y `OccupancyIcon` (tres
  siluetas 40 × 18, rellenas o en contorno según §4).
- **Fixtures:** `src/test/fixtures/api/*.json` y `e2e/fixtures/*.json` con los ejemplos del
  design de `stop_arrivals_api`; se tipan con un helper `Json<T>` (comprobado: un campo
  renombrado rompe `tsc`). En e2e, `serviceWorkers: 'block'` para que `page.route` intercepte
  todas las peticiones.

## Desviaciones respecto al design (para que el reviewer y la persona las validen)
No cambian contratos ni comportamiento de los AC. **Propuesta:** reflejarlas en el design o en
`docs/` en la próxima revisión.

1. **`openapi-typescript` 7.13 declara `peerDependencies: typescript ^5.x`** y el proyecto usa
   TypeScript 6.0 (no hay versión de `openapi-typescript` que admita la 6). Se instala con
   `"overrides": { "openapi-typescript": { "typescript": "$typescript" } }` en `package.json`;
   la generación funciona y el resultado se valida con `tsc`.
2. **Color del rojo EMT:** el algoritmo del design (pasos de 5 puntos de L en HSL) da
   `#e50000` (4,8:1), no exactamente el `#E40000` que cita `docs/design.md` §4 ("en torno a").
3. **Negrita de los avisos (§5.6):** el texto de AC-09 se mantiene literal ("Sin datos en tiempo
   real: se muestra el horario programado"), así que la negrita llega hasta los dos puntos en
   lugar de ser una frase con punto como en el ejemplo de la guía.
4. **`docs/conventions.md` §4** dice que en `localStorage` solo hay `device_id`, idioma y
   perfil; AC-19 añade la última parada (`avisabus.lastStop`, con su token). Manda la spec
   (conventions lo prevé); propuesta: añadirlo a la lista de conventions §4.

## Textos nuevos para revisar por la persona (CP-6)
Literales de la spec: "Parada {id}", "Próximas llegadas", "Actualizado a las…", "Actualizar",
"Datos actualizados", "No hay llegadas previstas en este momento", aviso de horario programado,
"Línea {l} hacia {d} está llegando", "Parada no encontrada", "Reintentar", "Datos de las…",
"Sin conexión", "Tu última parada: {nombre}", "Página no encontrada" y niveles de ocupación.
Redactados por mí (es / ca-valencia):
- `stop.towards` "hacia" / "cap a"; `stop.lines` "Líneas" / "Línies"; `stop.title` "Parada".
- `stop.notFound.body` "Vuelve a escanear el código QR de la parada para ver sus próximas
  llegadas." / "Torna a escanejar el codi QR de la parada per a vore les pròximes arribades."
- `stop.error.body` "**No se han podido cargar las llegadas.** Comprueba la conexión y vuelve a
  intentarlo." / "**No s'han pogut carregar les arribades.** Comprova la connexió i torna-ho a
  intentar."; `stop.error.retry` ca "Reintenta"; `stop.refresh` ca "Actualitza".
- `network.offline` "**Sin conexión.** Los datos se actualizarán cuando vuelva la conexión." /
  "**Sense connexió.** Les dades s'actualitzaran quan torne la connexió."
- `stop.scheduledTime` (frase accesible) "{hora} según el horario programado" / "segons l'horari
  programat"; `stop.arrivingNow` "está llegando" / "està arribant"; `stop.loading` "Cargando las
  próximas llegadas…" / "Carregant les pròximes arribades…".
- `home.lastStop` ca "La teua última parada: {nombre}"; `notFound.body` "La dirección que has
  abierto no existe." / "L'adreça que has obert no existix."; `notFound.home` "Ir a la portada" /
  "Ves a la portada".
- Ocupación ca: "Poc ocupat", "Ocupació mitjana", "Ple", "hi ha seients lliures", "sense seients
  lliures", "Ocupació no disponible"; vacío ca "No hi ha arribades previstes en este moment".

## Observaciones (no bloqueantes)
- Playwright vacía `test-results/` al inicio de cada ejecución: si se lanza solo un spec
  (`npx playwright test e2e/i18n.spec.ts`), desaparecen las capturas de esta feature hasta la
  siguiente ejecución completa.
- `bundle-budget.test.ts` también corre en `npm run test`; si existe un `dist/` antiguo, mide
  ese (lo prevé la nota del design §5); la medición fiable es la encadenada a `npm run e2e`.

## Bloqueos
Ninguno.

## Verificación
`CI=1 ./init.sh verify --e2e` (2026-11-03, tras T-09, puerto 4173 libre) → código 0,
"verify: todo en verde":
- backend: format, lint, types, architecture OK; pytest 861 passed, 6 deselected, cobertura
  99,66 %.
- frontend: format, lint, types OK; Vitest 35 ficheros, 278 tests passed; build OK
  (`index-*.js` 439,79 kB, **138,73 kB gzip**).
- frontend e2e + a11y: 60 passed (20 tests × iPhone 14, Pixel 7, iPad gen 7 landscape), axe WCAG
  2.1 A/AA sin violaciones; `test:bundle` 2 passed (presupuesto 200 KB).
- harness: `feature_list.json` OK; trazabilidad AC→test OK.
