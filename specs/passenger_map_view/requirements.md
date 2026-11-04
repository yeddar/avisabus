# Mapa del autobús — requirements

> Feature: `passenger_map_view` · Versión: 1.1 · Estado: APPROVED
> Requisitos: RF-13, RNF-01, RNF-03, RNF-05, RNF-14 · Casos de uso: CU-02 · Depende de: passenger_stop_view, position_estimation

## Contexto

Desde la vista de parada, el pasajero puede ver por dónde va el próximo autobús de una línea
(CU-02). La posición es **estimada** (LIM-03) y así debe decirse. Un mapa no es accesible por sí
mismo para personas ciegas o con baja visión, por lo que la vista ofrece **primero un resumen en
texto equivalente** (distancia, paradas que faltan, próxima parada, tiempo) y después el mapa.

El mapa usa Leaflet con teselas de OpenStreetMap, cargado **bajo demanda** para no penalizar la
vista de parada (presupuesto de `passenger_stop_view.AC-21`).

## Alcance

- Botón "Ver en el mapa" en las llegadas de la vista de parada que lo admiten.
- Ruta `/p/{stop_id}/map/{line}/{direction_id}?t={token}` cargada bajo demanda.
- Resumen textual de la posición y anuncios de proximidad.
- Mapa con trazado, paradas, parada del pasajero ("Tu parada") y autobús ("Estimada"), sin
  leyenda; atribución de OSM.
- Aspecto según la guía visual `docs/design.md` §5.7.
- Refresco periódico.

## Fuera de alcance

- Posiciones de varios autobuses a la vez.
- Seguimiento con la ubicación del propio pasajero.
- Proveedor de teselas propio (configurable, pero se usa OSM).

## Criterios de aceptación

### Acceso

- **passenger_map_view.AC-01** — CUANDO una llegada de la vista de parada tiene
  `in_network = true` y `direction_id` no nulo, LA VISTA DE PARADA DEBERÁ mostrar en esa llegada un
  enlace "Ver en el mapa" (nombre accesible "Ver en el mapa la línea {línea} hacia {destino}") que
  abre `/p/{stop_id}/map/{line}/{direction_id}?t={token}`; en otro caso no DEBERÁ mostrarlo.
  *Verificación:* unit
- **passenger_map_view.AC-02** — LA RUTA DEL MAPA y la librería de mapas DEBERÁN cargarse en un
  fragmento de JavaScript aparte, de modo que el presupuesto de `passenger_stop_view.AC-21` se siga
  cumpliendo; mientras se carga, DEBERÁ mostrarse un indicador "Cargando mapa…" con `role="status"`.
  *Verificación:* unit (presupuesto de bundle) + e2e
- **passenger_map_view.AC-03** — LA VISTA DEBERÁ tener como `h1` "Línea {línea} hacia {destino}"
  (destino = `arrival.destination` si hay llegada y, si no, el `headsign` de la respuesta de
  posición), título de documento acorde y un enlace "Volver a la parada" que conserva el token.
  *Verificación:* unit

### Resumen textual (alternativa al mapa)

- **passenger_map_view.AC-04** — ANTES del mapa, LA VISTA DEBERÁ mostrar un resumen en texto según
  el estado:
  - `EN_ROUTE`: "El autobús está a {distancia} de tu parada, a {n} paradas. Próxima parada:
    {nombre}. {llegada}" (con "a 1 parada" / "es la siguiente parada" cuando `n` vale 1 o 0);
  - `AT_STOP`: "El autobús está llegando a tu parada.";
  - `NOT_STARTED`: "El autobús aún no ha salido de {primera parada}. {llegada}", donde
    {primera parada} es el nombre de la primera parada del trazado (`shape.stops[0]`); (v1.1)
    MIENTRAS el trazado no se haya cargado, o SI su petición falla o no hay `shape_id`, ENTONCES
    "El autobús aún no ha salido de la primera parada del recorrido. {llegada}";
  - `NO_ARRIVAL` / `NO_VEHICLE`: "Posición no disponible en este momento." más el motivo.

  (v1.1) {llegada} sigue la regla de `passenger_stop_view.AC-06`: con `kind = MINUTES`, "Llega en
  {N minutos}." con la cuenta atrás de `passenger_stop_view.AC-13` (a partir de `arrival_at` y el
  reloj del servidor); con N = 0, "Está llegando."; con `kind = CLOCK_TIME`, "Llega a las
  {HH:MM}." (hora de Europe/Madrid). Textos en valenciano: "Arriba en {N minuts}.", "Està
  arribant.", "Arriba a les {HH:MM}.", "L'autobús encara no ha eixit de {primera parada}." y
  "…de la primera parada del recorregut." (redacción final del implementer, revisada en CP-6).
  *Verificación:* unit (por estado, por tipo de llegada y en los dos idiomas)
- **passenger_map_view.AC-05** — LA VISTA DEBERÁ indicar siempre, junto al resumen, "Posición
  estimada" (o "Posición según horario" si `source = "SCHEDULED"`), y el marcador del autobús DEBERÁ
  llevar una etiqueta de texto visible "Estimada" (o "Según horario"). EL MAPA NO DEBERÁ tener
  leyenda: la parada del pasajero lleva la etiqueta visible "Tu parada".
  *Verificación:* unit
- **passenger_map_view.AC-06** — LOS REFRESCOS NO DEBERÁN generar anuncios, salvo CUANDO
  `stops_away` pase a 0 ("El autobús llegará a tu parada en la siguiente") o el estado pase a
  `AT_STOP` ("El autobús está llegando a tu parada"), cada uno anunciado una sola vez por viaje de
  forma educada.
  *Verificación:* unit

### Mapa

- **passenger_map_view.AC-07** — EL MAPA DEBERÁ dibujar el trazado del viaje (`shape_id` de la
  respuesta de posición) con el color accesible de la línea, las paradas del trazado, la parada del
  pasajero destacada con la etiqueta "Tu parada" y el autobús con un icono orientado según
  `bearing_deg`; SI `position` es `null`, ENTONCES DEBERÁ dibujar solo el trazado y las paradas.
  (v1.1) El color del trazado es `accessibleLineColors(color, 'FFFFFF').bg` (contraste ≥ 4,5:1
  sobre blanco; neutro `#1f2937` si no hay color). SI no hay `shape_id` o el trazado responde
  `404`, ENTONCES el mapa DEBERÁ dibujar solo la parada del pasajero (coordenadas de `stop` en la
  respuesta de posición) y, si hay posición, el autobús.
  *Verificación:* unit (componentes con Leaflet en jsdom o capa de presentación aislada) + e2e
- **passenger_map_view.AC-08** — EN LA PRIMERA CARGA, EL MAPA DEBERÁ encuadrar el autobús y la parada
  del pasajero (o todo el trazado si no hay posición) y NO DEBERÁ volver a encuadrar en los
  refrescos posteriores, para no mover el mapa mientras la persona lo usa.
  *Verificación:* unit
- **passenger_map_view.AC-09** — EL MAPA DEBERÁ mostrar la atribución "© colaboradores de
  OpenStreetMap" con enlace, usar la URL de teselas de `VITE_MAP_TILE_URL` (por defecto la de OSM) y
  ser operable con teclado (zoom con botones etiquetados en el idioma activo y desplazamiento con
  flechas).
  *Verificación:* unit + e2e
- **passenger_map_view.AC-10** — MIENTRAS el sistema tenga activada la preferencia de reducir
  movimiento, EL MAPA DEBERÁ desactivar las animaciones de zoom, desplazamiento y marcadores.
  *Verificación:* unit
- **passenger_map_view.AC-11** — EL CONTENEDOR DEL MAPA DEBERÁ ser una región con nombre accesible
  "Mapa del recorrido" y una descripción que remita al resumen en texto.
  *Verificación:* unit + e2e (axe)

### Datos y errores

- **passenger_map_view.AC-12** — MIENTRAS la vista esté visible, DEBERÁ refrescar la posición cada
  `min(refresh_after_s, 30)` s, con las mismas reglas de pausa en segundo plano que la vista de
  parada; el trazado se pide una sola vez por `shape_id` y se reutiliza.
  *Verificación:* unit
- **passenger_map_view.AC-13** — SI la API de posición responde `404`, ENTONCES LA VISTA DEBERÁ
  mostrar "No se encuentra esta línea en tu parada" con enlace a la parada; SI hay error de red o
  `503`, ENTONCES DEBERÁ aplicar el mismo tratamiento que la vista de parada (reintento y datos
  conservados); un error de red o `503` del trazado recibe el mismo tratamiento. (v1.1) SI la ruta
  no trae token (`?t=`) o `directionId` no es un entero ≥ 0, ENTONCES LA VISTA NO DEBERÁ llamar a
  la API y DEBERÁ mostrar directamente "No se encuentra esta línea en tu parada".
  *Verificación:* unit
- **passenger_map_view.AC-14** — LAS PRUEBAS E2E DEBERÁN abrir el mapa con la API y las teselas
  simuladas (sin red), en los estados `EN_ROUTE`, `NOT_STARTED` y `NO_ARRIVAL`, en los perfiles
  móvil y tablet, y axe NO DEBERÁ reportar violaciones WCAG 2.1 A/AA. Solo puede excluirse del
  análisis el panel de teselas de Leaflet (`.leaflet-tile-pane`, imágenes decorativas).
  *Verificación:* e2e
- **passenger_map_view.AC-15** — LA VISTA DE MAPA DEBERÁ seguir la guía visual `docs/design.md`
  §5.7 (resumen destacado, etiquetas sobre el mapa, botones de zoom, atribución, sin leyenda).
  *Verificación:* revisión (reviewer, contra capturas de las pruebas e2e) + manual (persona en CP-6)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-13 Mapa con parada, trazado y autobús "posición estimada" | AC-01, AC-03, AC-05, AC-07, AC-08, AC-12 |
| RNF-01 Rendimiento | AC-02, AC-12 |
| RNF-03 Accesibilidad | AC-01, AC-04, AC-05, AC-06, AC-09, AC-10, AC-11, AC-14, AC-15 |
| RNF-05 Compatibilidad | AC-14 |
| RNF-14 Atribución (OSM) | AC-09 |
| CU-02 flujos 1a, 1b | AC-04, AC-05, AC-13 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-03 | Versión inicial aprobada (PR #7), con la guía visual `docs/design.md`. | CP-1 del bloque 2. Aprobada por la persona. |
| 1.1 | 2026-11-04 | AC-04: primera parada tomada del trazado, con texto alternativo si no está, y regla de {llegada} como `passenger_stop_view.AC-06` (minutos, hora o "Está llegando."); AC-07: color del trazado y caso sin trazado; AC-13: errores del trazado y ruta sin token o con sentido no numérico. Design: firma de `buildSummary`, altura de 360 px y atribución solo dentro del mapa. | CP-3 de `passenger_map_view` (B-01, B-02) y observaciones O-1…O-4 del implementer. Aprobada por la persona (PR #29). |
