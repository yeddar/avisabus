# Exploración: map (Leaflet / react-leaflet y teselas de OSM)
Feature(s): passenger_map_view (spec v1.0, E-01) · Fecha: 2026-11-04 · Agente: explorer

## Pregunta(s)

1. ¿Son compatibles `react-leaflet` y `leaflet` (últimas estables) con las versiones reales del
   frontend (React 19.3.1, Vite 8.3.5, TypeScript 6.0.3, Vitest 5, jsdom 30) y con `StrictMode`?
   Si no, ¿es viable usar Leaflet directamente con un componente propio (`useEffect` + `ref`)?
2. Política de uso de teselas de OpenStreetMap (`tile.openstreetmap.org`): `Referer`, atribución,
   User-Agent, volumen aceptable. ¿La cumple una demo de TFM? ¿Conviene un proveedor alternativo?

Restricciones consideradas: `specs/passenger_map_view/design.md` (teselas configurables por
`VITE_MAP_TILE_URL`, atribución, teclado, movimiento reducido, ningún marcador enfocable),
`docs/design.md` §2.6 y §5.7, y el presupuesto de JS inicial (≤ 200 KB gzip, `passenger_stop_view.AC-21`;
medido hoy: 138,7 KB gzip según `progress/review_passenger_stop_view.md:168`).

## Hallazgos

### H-1. Versiones publicadas y dependencias declaradas (npm, fuente primaria)

Comando: `npm view <pkg> dist-tags peerDependencies dependencies time`.

| Paquete | Última estable | Notas |
|---|---|---|
| `react-leaflet` | **5.0.0** (2024-12-14) | `peerDependencies`: `leaflet ^1.9.0`, `react ^19.0.0`, `react-dom ^19.0.0`. Depende de `@react-leaflet/core ^3.0.0`. ESM (`"type": "module"`, `"sideEffects": false`). Sin versiones posteriores. |
| `@react-leaflet/core` | 3.0.0 | Mismas peer deps. |
| `leaflet` | **1.9.4** (2023-05-18, `latest`) | `2.0.0-beta.1` publicada el **2026-11-02** (etiqueta `beta`, no estable). La línea 1.x está en mantenimiento (notas de 1.9.0: solo correcciones críticas). |
| `@types/leaflet` | **1.9.22** | Etiquetas `ts6.0`/`ts7.0` → 1.9.22: tipado declarado para TS 6. |

`frontend/package.json`: `react ^19.3.1`, `vite ^8.3.5`, `typescript ~6.0.3`, `vitest ^5.0.5`,
`jsdom ^30.1.3`; versiones instaladas comprobadas en `frontend/node_modules` (19.3.1, 8.3.5, 6.0.3).
Las peer deps de `react-leaflet@5` encajan (React 19.x). **Leaflet 2.0 no es compatible con
react-leaflet 5** (peer `^1.9.0`) y además cambia la API (sin export por defecto, clases renombradas
como `Control.Zoom` → `ZoomControl`, sin `@types/leaflet`, según las notas de
`github.com/Leaflet/Leaflet/releases` 2.0.0-alpha/beta): queda descartada para esta feature.

### H-2. Instalación aislada, compilación y build (scratchpad, sin tocar `frontend/`)

Directorio: `/private/tmp/claude-501/-Users-diegob-Developer-avisabus/7c6d7bf6-af5b-4ade-b145-3b1f50f59c8b/scratchpad/maptest`
(`leaflet@1.9.4`, `react-leaflet@5.0.0`, `@types/leaflet@1.9.22` + las mismas versiones de React,
Vite, TS, Vitest, jsdom y `@vitejs/plugin-react` que el proyecto).

- `npm install`: **sin avisos de peer dependencies**; `npm ls` resuelve un único `react@19.3.1` y
  `leaflet@1.9.4` deduplicados.
- Ejemplo mínimo que reproduce el design: `BusMap` cargado con `React.lazy` bajo `<StrictMode>`,
  `MapContainer` con `bounds`, `keyboard`, `zoomControl={false}`, opciones de movimiento reducido,
  `TileLayer` con `import.meta.env.VITE_MAP_TILE_URL ?? OSM`, `ZoomControl` con
  `zoomInTitle`/`zoomOutTitle`, `Polyline`, `CircleMarker` + `Tooltip permanent` ("Tu parada"),
  `Marker` con `L.divIcon` (SVG rotado + "Estimada"), `import 'leaflet/dist/leaflet.css'`.
- `tsc` con la configuración de `frontend/tsconfig.app.json` (strict, `noUncheckedIndexedAccess`,
  `verbatimModuleSyntax`, `skipLibCheck: true`): **exit 0**.
  - Con `skipLibCheck: false` aparecen 4 errores **en los `.d.ts` de react-leaflet**
    (`LayersControl.d.ts`, `SVGOverlay.d.ts`: `Cannot find module '@react-leaflet/core/lib/context'`).
    El proyecto usa `skipLibCheck: true`, así que no afecta; anotado como riesgo menor.
- `vite build` (Vite 8.3.5): OK. Fragmentos:
  ```
  dist/assets/BusMap-*.css   15.09 kB │ gzip:  6.36 kB
  dist/assets/BusMap-*.js   155.14 kB │ gzip: 45.55 kB   ← leaflet + react-leaflet + ejemplo
  dist/assets/index-*.js    221.96 kB │ gzip: 69.65 kB   ← solo React (ejemplo)
  ```
  `grep -c leaflet dist/assets/index-*.js` → `0`, y `index.html` no tiene `modulepreload` del
  fragmento del mapa: **Leaflet queda fuera del JS inicial** con un `import()` dinámico.
  Referencia: `leaflet/dist/leaflet.js` minificado ≈ 42,7 KB gzip, así que `react-leaflet` aporta
  ≈ 3 KB gzip. El CSS (6,4 KB gzip) va en el fragmento diferido.
- `leaflet@1.9.4` publica `main: dist/leaflet-src.js` (UMD) y no tiene campo `module`/`exports`;
  Vite 8 (Rolldown) lo resuelve sin configuración, tanto `import L from 'leaflet'` como las
  importaciones con nombre que usa react-leaflet.

### H-3. Modo estricto

- Código de `react-leaflet/lib/MapContainer.js` (v5.0.0): crea el mapa en un *callback ref* con
  guarda `mapInstanceRef`, guarda el contexto en `useState` y llama a `map.remove()` en la limpieza
  de un `useEffect([context])`. En el doble montaje de StrictMode la primera limpieza se ejecuta con
  `context = null`, de modo que no se destruye el mapa recién creado.
- Prueba en Vitest 5 + jsdom 30 con `<StrictMode>` (build de desarrollo de React, que es la que
  hace el doble montaje), en el scratchpad (`src/BusMap.test.tsx`, `src/opts.test.tsx`): **2/2 en
  verde**, exactamente **un** `.leaflet-container`, y `console.error` **no se llama** (no aparece
  "Map container is already initialized").
- Issue de referencia: `PaulLeCam/react-leaflet#1133` ("React 19 Old Error Back: Map container is
  already initialized"), **abierta** desde 2024-05, sin respuesta del mantenedor. Los informes son
  sobre 5.0.0-rc.1/Next.js 15; un usuario indica el 2025-12-01 que "using v5.0.0 solves this issue".
  Nuestra prueba con 5.0.0 + React 19.3.1 + StrictMode lo confirma. Mismo hilo: un usuario indica
  `Cannot read properties of undefined (reading '_leaflet_events')` tras actualizar a v5 (sin
  reproducción; no lo hemos visto).
- Mantenimiento: sin publicaciones desde 2024-12 y 45 issues abiertas. Es estable, pero no tiene
  actividad.

### H-4. Requisitos del design que dependen del comportamiento de Leaflet 1.9.4 (comprobados en el código)

| Requisito (design / docs) | Comportamiento real | Consecuencia para el implementer |
|---|---|---|
| Zoom con títulos traducidos (AC-09) | `MapContainer zoomControl` crea `Control.Zoom` con títulos en inglés. `Control.Zoom._createButton` pone `title`, `role="button"` y `aria-label=title`; el texto `+`/`−` lleva `aria-hidden`. `ZoomControl` de react-leaflet **solo actualiza `position`** (`@react-leaflet/core/lib/control.js`), no los títulos. | Usar `zoomControl={false}` + `<ZoomControl position="topright" zoomInTitle zoomOutTitle key={lang}/>` para que se vuelva a crear al cambiar de idioma. Comprobado: `aria-label="Acercar"`. |
| Botones de zoom de 44 × 44 arriba a la derecha (`docs/design.md` §5.7) | Por defecto están arriba a la izquierda; miden 30 px con `leaflet-touch` y 26 px sin él (`leaflet.css:291,325`). | `position="topright"` y CSS propio para 44 × 44. |
| Atribución 12 px, fondo blanco al 92 % | `leaflet.css` usa 12 px y `rgba(255,255,255,0.8)` (`:415,451`); enlace `#0078A8`. Prefijo por defecto "Leaflet" con bandera SVG `aria-hidden`. | Sobrescribir el fondo a 0,92. Mantener o quitar el prefijo "Leaflet" es decisión local (la licencia BSD-2 no exige mostrarlo). |
| Ningún marcador enfocable | `Marker._initIcon`: si `options.keyboard` (por defecto `true`) pone `tabIndex=0` y `role="button"` (`Marker.js:236-238`). | `Marker keyboard={false} interactive={false}`. Comprobado: sin `tabindex`. |
| Mapa enfocable y flechas/±(AC-09) | `Map.Keyboard` pone `tabIndex=0` en el contenedor (comprobado `tabIndex === 0`) y usa `keyCode` (`zoomIn: [187,107,61,171]`). | El e2e debe pulsar teclas con el mapa enfocado. Playwright emite `keyCode` para `+`, `-` y las flechas. |
| Movimiento reducido (AC-10) | Las opciones solo se leen al crear el mapa (`MapContainer` las pasa a `new L.Map` una vez). En jsdom `Browser.any3d` es falso y Leaflet desactiva la animación de zoom igualmente, así que **la clase CSS no sirve como prueba**. | Probar con `map.options` mediante `ref`. Comprobado: `{"z":false,"f":false,"m":false,"i":false,"kb":true}`. |
| "Tu parada" (Tooltip permanente) | `Tooltip` pone `role="tooltip"` y el texto visible (comprobado). | Sin incidencias. |
| Teselas decorativas | `TileLayer` pone `alt=""` (`TileLayer.js:167`). | Coherente con la exclusión `.leaflet-tile-pane` de AC-14. |
| `Referer` | `TileLayer.options.referrerPolicy = false`: el navegador aplica su política por defecto (`strict-origin-when-cross-origin`, que envía el origen). | No tocar `referrerPolicy`. |

**jsdom (estrategia de test de AC-07/09/10/11):** con jsdom 30 Leaflet dibuja SVG
(`Polyline`/`CircleMarker` generan `<path>`), así que **no hace falta simular `createSVGRect`**. El
contenedor mide 0 px, por lo que `fitBounds` da zoom 0. jsdom no descarga subrecursos por defecto:
el `<img src="https://tile.openstreetmap.org/0/0/0.png">` se crea, pero no se pide. Por eso los
tests unitarios de `useInitialFit` deben simular el mapa o comprobar las llamadas a
`fitBounds`/`setView`, no el zoom resultante.

### H-5. Alternativa: Leaflet directo (`useEffect` + `ref`)

Es viable. Un `useEffect` que crea `L.map(ref.current, options)` y devuelve `() => map.remove()`
sobrevive al doble montaje de StrictMode, porque crea, destruye y vuelve a crear. Ahorra unos 3 KB
gzip, pero obliga a reimplementar la sincronización de capas que ya hace react-leaflet (actualizar
la posición o el icono del autobús en cada refresco, crear y quitar capas). **No hace falta:**
react-leaflet 5.0.0 funciona con las versiones del proyecto. Según `tasks.md`, el cambio sería una
decisión local que no alteraría la interfaz de `BusMap` ni los AC.

### H-6. Política de uso de teselas de OSM (fuente: operations.osmfoundation.org/policies/tiles/)

Citas y requisitos de la política:

- **URL:** HTTPS `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Recomienda no fijar la URL en el
  código para poder cambiarla sin actualizar el software. `VITE_MAP_TILE_URL` ya lo cumple.
- **Referer:** "Browsers are expected to send a valid Referer header." / "Do not set a restrictive
  Referrer-Policy that prevents the Referer header being sent." Tampoco pueden quitarla los proxies
  ni las CDN.
- **User-Agent:** se exige un User-Agent propio a las **apps** (nativas) y prohíbe los genéricos de
  librería. Para la web: "Modern browsers, with default settings, already satisfy these technical
  requirements." Una PWA usa el User-Agent del navegador y lo cumple.
- **Atribución:** clara y visible en el mapa, normalmente abajo a la derecha, según las *Attribution
  Guidelines*; "Do not hide attribution beneath UI, behind toggles, or off-screen". Las guías
  (osmfoundation.org/wiki/Licence/Attribution_Guidelines) dicen: "Attribution must be to
  'OpenStreetMap'", con enlace recomendado a `openstreetmap.org/copyright`, sin interacción y
  legible (recomiendan WCAG). No dicen nada de traducir. "© colaboradores de OpenStreetMap" con
  enlace contiene "OpenStreetMap" y enlaza la licencia: **cumple**.
- **Caché:** respetar `Cache-Control`/`Expires`/`ETag`; no enviar `no-cache`. Cabeceras reales
  obtenidas con una sola petición `HEAD` a `/0/0/0.png`:
  `cache-control: max-age=93841, stale-while-revalidate=604800, stale-if-error=604800`, `etag`,
  `access-control-allow-origin: *`. La caché HTTP del navegador lo gestiona sola.
- **Prohibido:** descarga masiva, *prefetch* de teselas que no se ven, botones de "descargar para
  usar sin conexión", "Offline use is not permitted on `tile.openstreetmap.org`" y "Headless bots
  that pan/zoom the map to force rendering".
- **Volumen:** la política no da cifras. Acepta el uso interactivo normal (teselas del área visible
  con un margen pequeño) y la caché local. Puede bloquear sin aviso el uso intenso o anómalo, y el
  servicio no tiene SLA. No distingue el uso no comercial; a los servicios comerciales les advierte
  de que pueden perder el acceso.

**¿La cumple la demo del TFM?** Sí, con estas condiciones (todas compatibles con la spec actual):
1. Navegador con su configuración por defecto, sin `Referrer-Policy: no-referrer` en el futuro
   `deploy/nginx/web.conf` ni `<meta name="referrer">` en `index.html`. Hoy no existe ninguno:
   `grep -rni "referrer" deploy frontend/index.html frontend/vite.config.ts` no da resultados y no
   hay directorio `deploy/`.
2. Atribución visible abajo a la derecha (AC-09, `docs/design.md` §5.7).
3. **No cachear teselas en el service worker.** Hoy `vite.config.ts` (`workbox`) no define
   `runtimeCaching`, así que las teselas no se cachean. Si se añadiera un `CacheFirst` para
   teselas, sería "uso sin conexión" y prefetch, que la política prohíbe.
4. Los E2E nunca piden teselas reales: AC-14 ya exige `page.route('**/tile.openstreetmap.org/**')`
   → PNG local. Un navegador *headless* que mueve el mapa contra OSM entraría en la prohibición.
5. Volumen de una demo (pocos usuarios, una línea, zoom urbano): uso interactivo normal.

**Proveedor alternativo para el despliegue:** no hace falta para la demo. Si OSM bloquease la
instalación o creciera el uso, hay dos candidatos de teselas *raster* que Leaflet usa sin
adaptadores:
- **IGN España, IGN Base (WMTS, CC BY 4.0, sin clave):**
  `https://www.ign.es/wmts/ign-base?service=WMTS&request=GetTile&version=1.0.0&Format=image/png&layer=IGNBaseTodo&style=default&tilematrixset=GoogleMapsCompatible&TileMatrix={z}&TileRow={y}&TileCol={x}`.
  La plantilla sale de `dieghernan/leaflet-providersESP`, sin verificar contra el servidor.
  Atribución "CC BY 4.0 scne.es. Sistema Geográfico Nacional IGN". Es pública y española, y no
  depende de las donaciones a OSM.
- **CARTO basemaps (Voyager/Positron):** hoy piden **clave de API** (docs.carto.com/faqs/carto-basemaps).
  Son gratuitas para uso no comercial hasta unos 5 M de teselas al mes, según su documentación.
  Atribución "© OpenStreetMap contributors © CARTO".
Las teselas vectoriales (OpenFreeMap, etc.) necesitarían MapLibre y no encajan con Leaflet *raster*.

## Impacto en la spec

No hay contradicciones que bloqueen la feature. **No se necesita CP-3.** Hay matices para el
implementer, todos dentro de lo que permite el design:

1. `design.md` §3 "Mapa": dice "`MapContainer` con … `zoomControl` (títulos traducidos vía
   `L.Control.Zoom` con `zoomInTitle`/`zoomOutTitle`)". Con react-leaflet eso se hace con
   `zoomControl={false}` + `<ZoomControl position="topright" … key={lang}/>` (H-4). No hace falta
   cambiar la spec; lo apunto para que el implementer no use el `zoomControl` por defecto (títulos
   en inglés, arriba a la izquierda).
2. `design.md` §5 (tabla de tests, AC-10): "opciones pasadas a `MapContainer`". En jsdom hay que
   leer `map.options` mediante `ref` o simular `MapContainer`; la clase CSS de animación no sirve
   (H-4).
3. **Mejora opcional (no bloqueante) para una versión futura de la spec:** la URL es configurable
   (`VITE_MAP_TILE_URL`), pero la atribución es fija (`map.osmAttribution`). Si se cambiara de
   proveedor, faltaría su atribución (p. ej. "© CARTO" o "IGN"). Propuesta: añadir
   `VITE_MAP_TILE_ATTRIBUTION` (HTML adicional que se añade a la de OSM) o declarar en `requirements.md` (Fuera de
   alcance) que cambiar de proveedor exige cambiar la spec. Con OSM, que es lo que fija la v1.0, no
   afecta.
4. **Restricciones que convendría escribir** (en `docs/architecture.md` o en la futura spec de
   despliegue, no en esta): no usar `Referrer-Policy: no-referrer` en `deploy/nginx/web.conf` y no
   cachear las teselas de OSM en el service worker de Workbox. Las propone el explorer; las decide
   la persona.
5. Versiones que fijar en T-04: `leaflet@^1.9.4` (no `2.0.0-beta`), `react-leaflet@^5.0.0`,
   `@types/leaflet@^1.9.22` (dev).

## Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| react-leaflet sin mantenimiento (sin releases desde 2024-12; #1133 abierta). | Media | Bajo | Funciona con React 19.3 + StrictMode (H-3). La capa de Leaflet es fina y está aislada en `BusMap.tsx`, así que pasar a Leaflet directo (H-5) es una decisión local que no cambia los AC. |
| Leaflet 2.0 (beta desde 2026-11-02) rompe la API y react-leaflet no la admite. | Alta a medio plazo | Bajo | Fijar `leaflet@^1.9.4`. Usar importaciones con nombre (`import { divIcon } from 'leaflet'`) en lugar de `L.` por defecto para facilitar una migración futura. |
| Bloqueo o falta de servicio de `tile.openstreetmap.org` (sin SLA). | Baja | Medio (mapa sin fondo; el resumen textual sigue disponible) | URL configurable. Alternativas: IGN Base o CARTO (H-6). |
| Contraste de la atribución sobre el mapa (fondo 0,8 en Leaflet) en axe (AC-14). | Media | Bajo | Aplicar el 0,92 de `docs/design.md` §5.7 y comprobar el color del enlace en las capturas. |
| Botones de zoom de 30 px (< 44 px, RNF-03). | Seguro si no se cambia el CSS | Medio (a11y) | CSS propio de 44 × 44 (H-4). |
| `.d.ts` de react-leaflet con imports internos rotos si alguna vez se pone `skipLibCheck: false`. | Baja | Bajo | Mantener `skipLibCheck: true` (configuración actual). |
| El E2E del teclado depende de `keyCode` (Leaflet 1.x). | Baja | Bajo | Enfocar el contenedor `.leaflet-container` y usar `page.keyboard.press('+' / 'ArrowRight')`. |

## Recomendación

- Usar **react-leaflet 5.0.0 + leaflet 1.9.4 + @types/leaflet 1.9.22**, como dice el design. Son
  compatibles con React 19.3.1, Vite 8.3.5, TypeScript 6.0.3, Vitest 5 y jsdom 30, también en
  StrictMode. Leaflet directo queda como plan B (decisión local), pero no hace falta.
- Mantener **OSM** como teselas de la demo: la cumple con las condiciones de H-6 (navegador por
  defecto, atribución visible, sin caché de teselas en el SW, E2E sin teselas reales). No hay
  bloqueo, así que **no se necesita CP-3**.
- La feature puede pasar a `implementing` con la spec v1.0 tal cual. Los puntos 3 y 4 de "Impacto
  en la spec" son mejoras opcionales que decide la persona.

### Nota de proceso

Para leer las cabeceras de la política se hizo **una** petición `HEAD` a
`https://tile.openstreetmap.org/0/0/0.png` con `curl`. Por error, el User-Agent incluía el correo de
la persona como contacto (`AvisaBus-explorer/0.1 (TFM; policy header check; contact <email>)`). No
debió enviarse a un tercero sin su permiso. No se hizo ninguna otra petición a servidores de teselas.
