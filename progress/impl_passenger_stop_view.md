# Implementación: passenger_stop_view
Spec: specs/passenger_stop_view/ (v1.3, APPROVED) · Ciclo de revisión: 0 (v1.3) · Rama: `feat/passenger_stop_view-v1.3`
(v1.0: T-01…T-10 en `feat/passenger_stop_view`, revisada y APPROVED en el ciclo 1; v1.1: T-11 en
`feat/passenger_stop_view-v1.1`; v1.2: T-12 en `feat/passenger_stop_view-v1.2`; v1.3: solo T-13 y
T-10, sobre `develop`)

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
- [x] T-11 (v1.1) Anuncio y foco tras "Actualizar"/"Reintentar" (AC-24); mensaje de error sobre "los datos" y "Reintentar" que repite la petición de la parada (AC-17); `stop.refreshFailed` es/ca; comentario de `shared/device/storage.ts` (commit fd1825d)
- [x] T-12 (v1.2) Foco tras una acción manual con 404 (al `h1` de "Parada no encontrada", sin anuncio) y tras un refresco automático que acierta con el foco en "Reintentar" (a "Actualizar", sin anuncio) (commit e665d86)
- [x] T-13 (v1.3) Presupuesto de bundle solo sobre un `dist/` recién construido: `npm run test` omite los tests que leen `dist/`, `npm run test:bundle` construye y los ejecuta, `./init.sh verify` los ejecuta tras el build (paso "frontend: build + bundle") con y sin `--e2e`, y `npm run e2e` ya no encadena `test:bundle` (commit a417df7)
- [x] T-10 Verificación completa: `CI=1 ./init.sh verify --e2e` en verde (v1.0 tras T-09, v1.1 tras T-11, v1.2 tras T-12 y v1.3 tras T-13; ver "Verificación")

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
| AC-17 | `StopPage.errors.test.tsx` (503 y error de red con "Reintentar"; parada con 503 reintenta ambas; (v1.1) **solo falla la parada**: mensaje "No se han podido cargar los datos." con las llegadas visibles y "Reintentar" vuelve a pedir la parada; mensaje en `ca` "No s'han pogut carregar les dades."; datos conservados con "Datos de las 08:40, pueden no estar actualizados" es/ca) + e2e |
| AC-24 | (v1.1) `StopPage.errors.test.tsx`: "Actualizar" con error → anuncio "No se han podido actualizar los datos" / "No s'han pogut actualitzar les dades" y `document.activeElement` = "Reintentar"/"Reintenta" (es/ca); "Reintentar" con éxito tras fallo de las llegadas, de la parada o de un refresco → "Datos actualizados" y foco en "Actualizar"; "Reintentar" con error (llegadas o parada) → anuncio y el foco sigue en "Reintentar", también mientras la petición está en curso; refresco automático fallido sin anuncios (AC-15). Mutaciones temporales (revertidas): sin conservar el aviso durante el reintento fallan 2 tests; sin `stop.refetch()` fallan 3 |
| AC-24 (v1.2) | `StopPage.errors.test.tsx`: "Actualizar"/"Actualitza" y "Reintentar"/"Reintenta" (tras fallo de las llegadas o de la parada) con 404 → `h1` "Parada no encontrada"/"Parada no trobada" = `document.activeElement` y regiones vivas vacías; 404 al cargar no toma el foco; foco en "Reintentar" y refresco automático que acierta → foco en "Actualizar"/"Actualitza" sin anuncio (es/ca), también tras un "Actualizar" fallido (sin "Datos actualizados"); sin datos, el aviso y el foco se mantienen durante el refresco automático en curso y en pausa sin conexión; si "Reintentar" desaparece antes de que exista "Actualizar", el foco va a "Actualizar" solo si sigue en `body` (no se le quita a la persona); sin foco en "Reintentar", un refresco que acierta no mueve el foco. Mutaciones temporales (revertidas), todas detectadas: sin la salvaguarda de foco movido (1 test), sin el aviso de foco perdido (6), sin mantener el aviso al reintentar sin datos (2; solo en curso, sin pausa: 1), sin `onManualNotFound` en "Actualizar" (2) o en "Reintentar" (3), sin `tabIndex=-1` (5), enfocando el `h1` siempre (1) |
| AC-18 | `src/shared/hooks/__tests__/useOnline.test.tsx`, `StopPage.errors.test.tsx` (aviso `role="status"`, sin peticiones mientras no hay conexión, petición al volver; abierta sin conexión no llama a la API) + e2e |
| AC-19 | `lastStop.test.ts`, `StopPage.test.tsx` (se recuerda al cargar; no si 404), `src/app/routes/HomePage.test.tsx` (enlace es/ca, `lang`, URL codificada) + e2e |
| AC-20 | `src/app/routes/NotFoundPage.test.tsx` (`/no-existe`, `/p`, `/p/508/otra`, enlace a la portada) + e2e |
| AC-21 | `src/__tests__/bundle-budget.test.ts` (cálculo sobre un `dist` sintético + `dist/` real). (v1.3) Los tests sobre el `dist/` real (también los de `passenger_map_view.AC-02`) solo corren con `AVISABUS_BUNDLE_CHECK=1`, que pone `npm run test:bundle` tras `npm run build`; `./init.sh verify` los ejecuta en "frontend: build + bundle"; un test nuevo comprueba los scripts de `package.json` y el paso de `init.sh`. Medido (v1.3): **141,49 kB** gzip |
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

### Decisiones locales de T-11 (v1.1)
- **Aviso de error durante "Reintentar":** TanStack Query v5 pasa a `pending` (sin `error`) una
  consulta sin datos al volver a pedirla, así que el aviso y su botón desaparecían durante el
  reintento y el foco caía en `body`. Mientras `manualAction === 'retry'` se mantiene el aviso
  (`showError = failed || manualAction === 'retry'`) y no se muestra "Cargando…": el foco "sigue
  en Reintentar" de verdad, sin moverlo.
- **Foco:** solo se mueve cuando el control enfocado desaparece ("Actualizar" con error →
  "Reintentar"; "Reintentar" con éxito → "Actualizar"). En los casos "se queda" no se llama a
  `focus()`, para no quitar el foco si la persona lo ha movido mientras esperaba. Se pide con un
  estado `focusRequest` y un `useEffect` que enfoca cuando el control ya está pintado (una sola
  vez por petición).
- **`ref` en un envoltorio:** `shared/ui/Button` (de `frontend_i18n`) no acepta `ref` en sus tipos
  y T-11 no incluye ese fichero, así que los botones van dentro de un `<div className="flex">`
  con `ref` y se enfoca su `button`. Sin cambio visual (capturas revisadas).
- **Pulsaciones repetidas:** mientras hay una acción manual en curso se ignoran nuevas pulsaciones
  de "Actualizar"/"Reintentar" (un segundo `refetch()` cancela el primero y su promesa podría
  resolverse antes de tiempo y anunciar "Datos actualizados" sin datos nuevos).
- **Textos (redacción, design §6):** `stop.error.body` "**No se han podido cargar los datos.**
  Comprueba la conexión y vuelve a intentarlo." / "**No s'han pogut carregar les dades.** Comprova
  la connexió i torna-ho a intentar."; `stop.refreshFailed` "No se han podido actualizar los
  datos" (literal de AC-24) / "No s'han pogut actualitzar les dades".

### Decisiones locales de T-12 (v1.2)
- **404 tras una acción manual:** `StopView` guarda `manualNotFound` (estado) y se lo pasa a
  `StopNotFound` como `focusHeading`; `refresh()`/`retry()` lo activan si alguna respuesta del
  `refetch()` es 404 y salen sin anuncio ni `finish()`. `StopNotFound` tiene `h1` con
  `tabIndex={-1}` (el CSS global ya quita el contorno a `h1[tabindex='-1']:focus`) y lo enfoca en
  un `useEffect` sobre `focusHeading`: así funciona tanto si `StopNotFound` se monta antes como
  después de que termine la promesa del `refetch()`. Con 404 al cargar (o sin token) no se toca el
  foco (`frontend_i18n.AC-11`: carga inicial).
- **Detección del foco antes de desmontar el aviso (design v1.2):** el botón "Reintentar" va en un
  componente `RetryAction` cuyo `useLayoutEffect` lee `document.activeElement` en la limpieza: React
  ejecuta las limpiezas de *layout* de un subárbol eliminado antes de quitar sus nodos del DOM
  (como `componentWillUnmount`). Si el botón tenía el foco, pide el foco para "Actualizar" (sin
  anuncio). Tras un "Reintentar" con éxito también se dispara, con el mismo resultado que T-11.
- **Aviso de error durante un reintento automático sin datos:** TanStack Query v5 pasa a `pending`
  (sin `error`) una consulta sin datos al volver a pedirla, también en los refrescos automáticos
  (`refetchInterval` de 20 s, reconexión, foco de ventana). El aviso desaparecía al **empezar** la
  petición y no al acertar, y el foco caía en `body` antes de saber el resultado. Como en T-11
  para "Reintentar", el aviso se mantiene mientras la consulta sin datos que falló se vuelve a
  pedir, en curso o en pausa sin conexión (`isPending && fetchStatus !== 'idle' &&
  errorUpdateCount > 0`). Efecto visible: sin datos y con error ya no aparece "Cargando las
  próximas llegadas…" cada 20 s durante el reintento automático; el aviso de error sigue hasta que
  llegan los datos (con datos antiguos ya era así, porque la consulta sigue en `error`). Con esto,
  "el aviso de error desaparece" equivale a "el refresco acierta" o al 404, como presupone AC-24.
- **No quitar el foco a la persona:** la petición de foco por "Reintentar" desaparecido (`lost`)
  solo se cumple si el foco sigue en `body`; si "Actualizar" aún no existe (p. ej. solo falló la
  parada, se recupera al reconectar y las primeras llegadas no han llegado), espera a que aparezca,
  pero se descarta si la persona ha enfocado otra cosa mientras tanto.
- **Textos:** ninguno nuevo (el `h1` "Parada no encontrada"/"Parada no trobada" ya existía).

### Decisiones locales de T-13 (v1.3)
El design §5 deja el mecanismo exacto como decisión local:
- **Variable `AVISABUS_BUNDLE_CHECK=1`** puesta en el propio script:
  `"test:bundle": "npm run build && AVISABUS_BUNDLE_CHECK=1 vitest run src/__tests__/bundle-budget.test.ts"`.
  Los dos tests que leen `dist/` usan `it.runIf(BUNDLE_CHECK)`; sin la variable se omiten con el
  aviso `[bundle-budget] dist/ checks skipped: run npm run test:bundle …`.
- **Sin `exclude` en `vite.config.ts`** (no se ha tocado): los tests del cálculo sobre un `dist`
  sintético en un directorio temporal (AC-21 y `passenger_map_view.AC-02`) no leen `dist/` y
  siguen corriendo en `npm run test`, que así detecta pronto un fallo del cálculo.
- **Con la variable y sin `dist/` el test falla** (antes se omitía con `skipIf`): bajo
  `test:bundle` el `dist/` siempre acaba de construirse, así que su ausencia es un error y no un
  motivo para omitir. Mensaje: "dist/index.html is missing: run `npm run test:bundle` (it builds first)".
  `vite build` vacía `dist/` antes de escribir (`emptyOutDir`), así que no quedan restos de builds
  anteriores.
- **Test del arnés** `[passenger_stop_view.AC-21] the budget is only checked on a fresh build…`
  (en `npm run test`): comprueba el script `test:bundle` exacto, que `test` no pone la variable, que
  `e2e` no encadena `test:bundle` y que `init.sh` tiene el paso
  `"frontend: build + bundle" … npm run --silent test:bundle` y ya no `npm run --silent build`.
  Se vio en rojo antes de cambiar `package.json` e `init.sh`.
- **`init.sh`:** el paso "frontend: build" pasa a ser "frontend: build + bundle"
  (`npm run --silent test:bundle`), en el mismo sitio (antes de e2e). Con `--e2e`, el
  `webServer` de Playwright sigue construyendo por su cuenta (`npm run build && npm run preview`);
  no se ha cambiado.

## Desviaciones respecto al design (v1.0) y estado actual
Las cuatro se detectaron en la v1.0. No cambian contratos ni comportamiento de los AC. La PR #24
(spec v1.1 y CP-4 de `docs/`) las recoge todas. Esa PR ya está fusionada en
`develop`, de donde sale la rama de la v1.2.

1. **`openapi-typescript` 7.13 con TypeScript 6 mediante `overrides`.** *Resuelta en la spec
   (v1.1, PR #24):* el design §2 documenta el `overrides` como deuda técnica. **Sigue abierta la
   deuda:** hay que quitar el `overrides` cuando haya una versión de `openapi-typescript`
   compatible con TypeScript 6.
2. **Rojo EMT `#e50000` en vez de `#E40000`.** *Resuelta en `docs/` (PR #24):*
   `docs/design.md` §4 v1.1 dice `#E50000` (4,8:1).
3. **Negrita del aviso de horario programado (§5.6).** *Resuelta en `docs/` (PR #24):* el
   ejemplo de `docs/design.md` §5.6 v1.1 usa el texto literal de AC-09.
4. **`avisabus.lastStop` frente a `docs/conventions.md` §4.** *Resuelta en `docs/` (PR #24):*
   conventions §4 ya incluye la última parada consultada. El comentario de
   `shared/device/storage.ts` se actualizó en T-11 (hallazgo N-3).

## Textos para revisar por la persona (CP-6)
Redacción vigente tras T-11, tal como está en `src/locales/es` y `src/locales/ca-valencia`.
Los marcados con **(spec)** son literales de la spec en castellano; el resto los redacté yo
(design §6). Todos los textos en valenciano son míos. `<strong>` = negrita; `{…}` = variable.

### Novedades de la v1.1 (T-11)
| Clave | es | ca-valencia |
|---|---|---|
| `stop.error.body` | "**No se han podido cargar los datos.** Comprueba la conexión y vuelve a intentarlo." | "**No s'han pogut carregar les dades.** Comprova la connexió i torna-ho a intentar." |
| `stop.refreshFailed` | "No se han podido actualizar los datos" **(spec, AC-24)** | "No s'han pogut actualitzar les dades" |

### Vista de parada
| Clave | es | ca-valencia |
|---|---|---|
| `stop.title` | "Parada" | "Parada" |
| `stop.code` | "Parada {código}" **(spec)** | "Parada {código}" |
| `stop.lineName` (oculto) | "Línea {línea}" | "Línia {línea}" |
| `stop.lines` | "Líneas" | "Línies" |
| `stop.arrivals` | "Próximas llegadas" **(spec)** | "Pròximes arribades" |
| `stop.updatedAt` | "Actualizado a las {hora}" **(spec)** | "Actualitzat a les {hora}" |
| `stop.refresh` | "Actualizar" **(spec)** | "Actualitza" |
| `stop.refreshed` (anuncio) | "Datos actualizados" **(spec)** | "Dades actualitzades" |
| `stop.loading` | "Cargando las próximas llegadas…" | "Carregant les pròximes arribades…" |
| `stop.empty` | "No hay llegadas previstas en este momento" **(spec)** | "No hi ha arribades previstes en este moment" |
| `stop.scheduledNotice` | "**Sin datos en tiempo real:** se muestra el horario programado" **(spec)** | "**Sense dades en temps real:** es mostra l'horari programat" |
| `stop.scheduledSuffix` | "programado" | "programat" |
| `stop.towards` | "hacia" | "cap a" |
| `stop.error.retry` | "Reintentar" **(spec)** | "Reintenta" |
| `stop.stale` | "Datos de las {hora}, pueden no estar actualizados" **(spec)** | "Dades de les {hora}, poden no estar actualitzades" |
| `network.offline` | "**Sin conexión.** Los datos se actualizarán cuando vuelva la conexión." (spec: "Sin conexión") | "**Sense connexió.** Les dades s'actualitzaran quan torne la connexió." |

### Textos para lector de pantalla
| Clave | es | ca-valencia |
|---|---|---|
| `stop.rowLabel` | "Línea {línea}, hacia {destino}, {tiempo}, {ocupación}" **(spec, AC-05)** | "Línia {línea}, cap a {destino}, {tiempo}, {ocupación}" |
| `stop.rowLabelNoOccupancy` (AC-08) | "Línea {línea}, hacia {destino}, {tiempo}" | "Línia {línea}, cap a {destino}, {tiempo}" |
| `stop.arrivesIn` | "llega en {duración}" **(spec)** | "arriba en {duración}" |
| `stop.arrivesAt` | "llega a las {hora}" **(spec)** | "arriba a les {hora}" |
| `stop.scheduledTime` | "{hora} según el horario programado" | "{hora} segons l'horari programat" |
| `stop.arrivingNow` | "está llegando" | "està arribant" |
| `stop.arriving` (anuncio) | "Línea {línea} hacia {destino} está llegando" **(spec)** | "Línia {línea} cap a {destino} està arribant" |
| `occupancy.spoken.*` | "poco ocupado", "ocupación media", "lleno", "ocupación no disponible" | "poc ocupat", "ocupació mitjana", "ple", "ocupació no disponible" |

### Ocupación (en pantalla)
| Clave | es | ca-valencia |
|---|---|---|
| `occupancy.FREE` / `MEDIUM` / `FULL` | "Poco ocupado" / "Ocupación media" / "Lleno" **(spec)** | "Poc ocupat" / "Ocupació mitjana" / "Ple" |
| `occupancy.seatsYes` / `seatsNo` | "hay asientos libres" / "sin asientos libres" **(spec)** | "hi ha seients lliures" / "sense seients lliures" |
| `occupancy.unavailable` | "Ocupación no disponible" **(spec)** | "Ocupació no disponible" |

### Páginas de error y portada
| Clave | es | ca-valencia |
|---|---|---|
| `stop.notFound.title` | "Parada no encontrada" **(spec)** | "Parada no trobada" |
| `stop.notFound.body` | "Vuelve a escanear el código QR de la parada para ver sus próximas llegadas." | "Torna a escanejar el codi QR de la parada per a vore les pròximes arribades." |
| `notFound.title` | "Página no encontrada" **(spec)** | "Pàgina no trobada" |
| `notFound.body` | "La dirección que has abierto no existe." | "L'adreça que has obert no existix." |
| `notFound.home` | "Ir a la portada" | "Ves a la portada" |
| `home.lastStop` | "Tu última parada: {nombre}" **(spec)** | "La teua última parada: {nombre}" |

## Observaciones (no bloqueantes)
- (v1.1) ~~Hueco menor de AC-24 con un 404~~: **resuelto en la v1.2 (T-12)**. Ya no se anuncia
  "No se han podido actualizar los datos" tras un 404 manual; el foco va al `h1`.
- (v1.2) Para CP-6 con lector de pantalla: (a) 404 tras "Actualizar" → debe leerse "Parada no
  encontrada, encabezado nivel 1"; (b) foco en "Reintentar", esperar a que un refresco automático
  acierte (≤ 30 s) → el lector debe situarse en "Actualizar" sin anuncio.
- (v1.2) Si se pierde el foco en "Reintentar" por una causa no regulada (p. ej. un 404 de un
  refresco **automático**), no se mueve: AC-24 solo regula el 404 de las acciones manuales.
- Playwright vacía `test-results/` al inicio de cada ejecución: si se lanza solo un spec
  (`npx playwright test e2e/i18n.spec.ts`), desaparecen las capturas de esta feature hasta la
  siguiente ejecución completa.
- ~~`bundle-budget.test.ts` mide un `dist/` antiguo en `npm run test`~~: **resuelto en la v1.3
  (T-13)**. Solo `npm run test:bundle` (y por tanto `./init.sh verify`) mide `dist/`, y siempre tras
  construirlo.
- (v1.3) **Propuesta para `docs/` (no lo modifico):** `docs/verification.md` (fila "Build":
  `npm run build`) y, si procede, `docs/conventions.md` §8 deberían decir que el paso de build de
  `verify` es `npm run test:bundle` (build + presupuesto de bundle) y que `npm run e2e` ya no lo
  encadena.

## Bloqueos
Ninguno.

## Verificación
**v1.3 (tras T-13), comportamiento con `dist/` borrado y manipulado (2026-11-04):**
- `rm -rf frontend/dist && ./init.sh verify` → código 0, "verify: todo en verde"; "frontend: tests"
  408 passed | 2 skipped (los dos tests de `dist/`); "frontend: build + bundle" construye
  (`index-*.js` 448,27 kB, 141,49 kB gzip) y pasa 5/5 tests de `bundle-budget.test.ts`.
- Sin `dist/` y con `AVISABUS_BUNDLE_CHECK=1` sin construir → los 2 tests de `dist/` fallan
  ("dist/index.html is missing…"), no se omiten.
- **`dist/` antiguo manipulado** (≈400 KB aleatorios y la marca `leaflet-pane` añadidos a
  `index-*.js`: 544 956 B gzip): `npm run test` → código 0, 408 passed | 2 skipped (no lo lee);
  leyéndolo sin construir (`AVISABUS_BUNDLE_CHECK=1 vitest run …bundle-budget…`) → 2 fallos
  (544 938 > 204 800 y Leaflet en 2 trozos), es decir, la manipulación sería detectable;
  `./init.sh verify` → código 0 sin falso rojo: reconstruye `dist/` (`index-*.js` vuelve a
  448 275 B) y mide el build nuevo.
- **Falso verde de antes** (`dist/` antiguo correcto + fuente que rompe el presupuesto, cambio
  temporal ya revertido: `import 'leaflet'` y ~120 KB aleatorios en `src/main.tsx`):
  `npm run test` → código 0 (no lee `dist/`); `./init.sh verify` → código 1, "frontend: build +
  bundle" FAIL (274 191 > 204 800 y Leaflet en el trozo inicial `index-*.js`). También falló
  "frontend: format" por la línea larga del cambio temporal.

**v1.3 (tras T-13):** `CI=1 ./init.sh verify --e2e` (2026-11-04, puerto 4173 libre) → código 0,
"verify: todo en verde":
- backend: format, lint, types, architecture (2 contratos respetados, 0 rotos) OK; pytest
  988 passed, 6 deselected, cobertura 99,46 %.
- frontend: format, lint, types OK; Vitest 44 ficheros, **408 passed | 2 skipped** (los 2 de
  `dist/`, que ya no corren en `npm run test`).
- frontend: build + bundle OK (`index-*.js` 448,27 kB, **141,49 kB gzip**; `bundle-budget.test.ts`
  5 passed, incluidos los de `passenger_map_view.AC-02`).
- frontend e2e + a11y: 87 passed, axe sin violaciones; ya no ejecuta Vitest tras Playwright.
- harness: `feature_list.json` OK; trazabilidad AC→test OK.

**v1.2 (tras T-12):** `CI=1 ./init.sh verify --e2e` (2026-11-04, puerto 4173 libre) → código 0,
"verify: todo en verde":
- backend: format, lint, types, architecture (2 contratos respetados, 0 rotos) OK; pytest
  969 passed, 6 deselected, cobertura 99,39 %.
- frontend: format, lint, types OK; Vitest 35 ficheros, **301 tests** passed (+14 de T-12); build
  OK (`index-*.js` 441,37 kB, **139,25 kB gzip**).
- frontend e2e + a11y: 60 passed, axe sin violaciones; `test:bundle` 2 passed (presupuesto 200 KB).
- harness: `feature_list.json` OK; trazabilidad AC→test OK.
- T-12 no cambia la maquetación (el `h1` con `tabIndex=-1` no muestra contorno; `RetryAction`
  pinta el mismo `<div className="flex">`); las capturas se han regenerado en
  `frontend/test-results/passenger_stop_view/<perfil>/`.

**v1.1 (tras T-11):** `CI=1 ./init.sh verify --e2e` (2026-11-03, puerto 4173 libre) → código 0,
"verify: todo en verde":
- backend: format, lint, types, architecture (2 contratos respetados) OK; pytest 969 passed,
  6 deselected, cobertura 99,39 %.
- frontend: format, lint, types OK; Vitest 35 ficheros, 287 tests passed; build OK
  (`index-*.js` 440,58 kB, **138,96 kB gzip**).
- frontend e2e + a11y: 60 passed, axe sin violaciones; `test:bundle` 2 passed.
- harness: `feature_list.json` OK; trazabilidad AC→test OK.
- Capturas regeneradas (23:25) en `frontend/test-results/passenger_stop_view/<perfil>/`;
  `stop-error-stale-es.png` muestra el texto nuevo "No se han podido cargar los datos." y los
  botones envueltos no cambian la maquetación (`stop-realtime-*-refresh-focused.png`).

**v1.0:** `CI=1 ./init.sh verify --e2e` (2026-11-03, tras T-09, puerto 4173 libre) → código 0,
"verify: todo en verde":
- backend: format, lint, types, architecture OK; pytest 861 passed, 6 deselected, cobertura
  99,66 %.
- frontend: format, lint, types OK; Vitest 35 ficheros, 278 tests passed; build OK
  (`index-*.js` 439,79 kB, **138,73 kB gzip**).
- frontend e2e + a11y: 60 passed (20 tests × iPhone 14, Pixel 7, iPad gen 7 landscape), axe WCAG
  2.1 A/AA sin violaciones; `test:bundle` 2 passed (presupuesto 200 KB).
- harness: `feature_list.json` OK; trazabilidad AC→test OK.
