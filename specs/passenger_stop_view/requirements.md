# Vista de parada del pasajero — requirements

> Feature: `passenger_stop_view` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-06, RF-10, RF-15, RF-32, RNF-01, RNF-03, RNF-04, RNF-05, RNF-14 · Casos de uso: CU-01 · Depende de: stop_arrivals_api, frontend_i18n

## Contexto

Es la pantalla a la que llega el pasajero al escanear el QR de su parada (CU-01): la URL
`/p/{stop_id}?t={token}` abre, sin registro ni instalación, la lista de próximas llegadas con su
tiempo y su ocupación. Consume la API de `stop_arrivals_api` y se apoya en la base de idiomas y
accesibilidad de `frontend_i18n`.

Muchos de sus usuarios usan lector de pantalla o tienen baja visión, por lo que la información no
puede depender del color, las actualizaciones periódicas no deben saturar al lector de pantalla y
el autobús que está llegando debe anunciarse.

Esta feature también establece el **contrato tipado** entre backend y frontend (ADR-010): tipos
TypeScript generados desde el OpenAPI del backend, con un test que detecta desfases.

## Alcance

- Exportación del OpenAPI desde la CLI del backend y generación de tipos en el frontend.
- Cliente HTTP (errores `problem+json`) y TanStack Query.
- Vista de parada: cabecera, líneas, llegadas, ocupación, origen de los datos, refresco,
  cuenta atrás, anuncios, errores, estado vacío y sin conexión.
- Recordar la última parada consultada y ofrecerla en la portada.
- Página genérica "no encontrado" para rutas desconocidas.
- Presupuesto de tamaño del JavaScript inicial.

## Fuera de alcance

- Botón "Ver en el mapa" y vista de mapa (`passenger_map_view`).
- Botón "Avisar" y estado del aviso (`passenger_alert_ui`).
- Búsqueda de paradas sin QR.

## Criterios de aceptación

### Contrato con el backend

- **passenger_stop_view.AC-01** — CUANDO se ejecuta `uv run avisabus openapi export --out <fichero>`,
  LA CLI DEBERÁ escribir el documento OpenAPI de la API sin abrir la base de datos ni la red.
  *Verificación:* integration (backend)
- **passenger_stop_view.AC-02** — SI el OpenAPI generado por el backend difiere de
  `frontend/src/shared/api/openapi.json`, ENTONCES los tests del backend DEBERÁN fallar indicando
  que hay que ejecutar `npm run gen:api`.
  *Verificación:* integration (backend)
- **passenger_stop_view.AC-03** — EL CLIENTE HTTP DEBERÁ usar los tipos generados con
  `openapi-typescript` y convertir las respuestas de error `problem+json` en un `ApiError` con
  `status` y `type`; los errores de red y los tiempos de espera agotados (8 s) DEBERÁN producir un
  `ApiError` con `status = 0`.
  *Verificación:* unit

### Contenido de la vista

- **passenger_stop_view.AC-04** — CUANDO se abre `/p/{stop_id}?t={token}` con datos válidos, LA
  VISTA DEBERÁ mostrar como `h1` el nombre de la parada (GTFS, sin traducir), el texto
  "Parada {stop_id}", las líneas que la sirven y el título de documento
  `<nombre de la parada> · AvisaBus`.
  *Verificación:* unit + e2e
- **passenger_stop_view.AC-05** — LA VISTA DEBERÁ mostrar las llegadas en el orden de la API como
  una lista en la que cada elemento indica: línea, destino, tiempo de llegada y ocupación, y
  cuyo texto accesible completo sea del tipo "Línea 93, hacia Pg. Marítim, llega en 4 minutos,
  ocupación media, hay asientos libres".
  *Verificación:* unit
- **passenger_stop_view.AC-06** — EL TIEMPO DE LLEGADA DEBERÁ mostrarse como "N min" si
  `kind = MINUTES` y N ≥ 1; como "Llegando" si N = 0; y como hora `HH:MM` si
  `kind = CLOCK_TIME`.
  *Verificación:* unit
- **passenger_stop_view.AC-07** — LA OCUPACIÓN DEBERÁ mostrarse con icono y texto (nunca solo con
  color): "Poco ocupado", "Ocupación media" o "Lleno", seguido de "hay asientos libres" o
  "sin asientos libres"; SI `occupancy` es `null`, ENTONCES "Ocupación no disponible".
  *Verificación:* unit
- **passenger_stop_view.AC-08** — CUANDO una llegada tiene `in_network = false`, LA VISTA DEBERÁ
  mostrarla con su tiempo y sin ocupación ni acciones.
  *Verificación:* unit
- **passenger_stop_view.AC-09** — CUANDO `source = "SCHEDULED"`, LA VISTA DEBERÁ mostrar sobre la
  lista un aviso con `role="status"`: "Sin datos en tiempo real: se muestra el horario
  programado", y cada tiempo DEBERÁ indicar que es programado.
  *Verificación:* unit
- **passenger_stop_view.AC-10** — CUANDO no hay llegadas, LA VISTA DEBERÁ mostrar "No hay
  llegadas previstas en este momento".
  *Verificación:* unit
- **passenger_stop_view.AC-11** — LOS DISTINTIVOS DE LÍNEA DEBERÁN usar el color de la línea; SI
  el contraste entre `line_color` y `line_text_color` es menor que 4,5:1, ENTONCES EL SISTEMA
  DEBERÁ oscurecer el color de fondo hasta alcanzar al menos 4,5:1 (el rojo de EMT `#FE0000` con
  blanco da ≈ 4:1 y debe corregirse). SI la línea no tiene color, ENTONCES se usa un estilo neutro.
  *Verificación:* unit

### Actualización y anuncios

- **passenger_stop_view.AC-12** — MIENTRAS la vista esté visible, LA VISTA DEBERÁ volver a pedir
  las llegadas cada `min(refresh_after_s, 30)` segundos sin recargar la página ni borrar la lista
  mientras llegan los datos nuevos; MIENTRAS la pestaña esté oculta, DEBERÁ dejar de pedirlas, y
  CUANDO vuelva a estar visible, DEBERÁ pedirlas de inmediato.
  *Verificación:* unit (temporizadores falsos, `visibilitychange`)
- **passenger_stop_view.AC-13** — ENTRE dos respuestas, LA VISTA DEBERÁ actualizar cada 15 s los
  tiempos `MINUTES` a partir de `arrival_at`, corrigiendo la diferencia entre el reloj del
  dispositivo y `generated_at` del servidor.
  *Verificación:* unit
- **passenger_stop_view.AC-14** — LA VISTA DEBERÁ mostrar "Actualizado a las HH:MM:SS" y un botón
  "Actualizar" que pide los datos de inmediato y, al terminar, anuncia de forma educada
  "Datos actualizados".
  *Verificación:* unit
- **passenger_stop_view.AC-15** — LOS REFRESCOS AUTOMÁTICOS NO DEBERÁN generar anuncios para
  lectores de pantalla, salvo CUANDO la primera llegada de una línea y destino pase a
  "Llegando", en cuyo caso LA VISTA DEBERÁ anunciar una sola vez, de forma educada,
  "Línea {línea} hacia {destino} está llegando".
  *Verificación:* unit

### Errores y conectividad

- **passenger_stop_view.AC-16** — SI la API responde `404`, ENTONCES LA VISTA DEBERÁ mostrar una
  página con `h1` "Parada no encontrada" y la indicación de volver a escanear el QR de la parada,
  sin mostrar el `stop_id` ni el token de la URL como texto.
  *Verificación:* unit + e2e
- **passenger_stop_view.AC-17** — SI la API responde `503` o hay un error de red, ENTONCES LA
  VISTA DEBERÁ mostrar un mensaje con botón "Reintentar"; SI ya había datos, ENTONCES DEBERÁ
  conservarlos marcados como "Datos de las HH:MM, pueden no estar actualizados".
  *Verificación:* unit
- **passenger_stop_view.AC-18** — MIENTRAS el navegador indique que no hay conexión, LA VISTA
  DEBERÁ mostrar un aviso "Sin conexión" con `role="status"` y no reintentar hasta recuperarla.
  *Verificación:* unit (eventos `online`/`offline`)

### Navegación y rendimiento

- **passenger_stop_view.AC-19** — CUANDO se carga correctamente una parada, LA APLICACIÓN DEBERÁ
  recordar en el dispositivo su `stop_id`, nombre y token, y LA PORTADA DEBERÁ ofrecer un enlace
  "Tu última parada: {nombre}" que la abre.
  *Verificación:* unit
- **passenger_stop_view.AC-20** — CUANDO se abre una ruta inexistente, LA APLICACIÓN DEBERÁ mostrar
  una página "Página no encontrada" con enlace a la portada.
  *Verificación:* unit
- **passenger_stop_view.AC-21** — EL JAVASCRIPT inicial de la aplicación (sin trozos cargados bajo
  demanda) DEBERÁ ocupar como máximo 200 KB comprimido con gzip.
  *Verificación:* unit (test que mide `dist/` tras `npm run build`)
- **passenger_stop_view.AC-22** — LAS PRUEBAS E2E DEBERÁN abrir la vista con respuestas simuladas
  de la API (tiempo real, horario programado, sin llegadas, parada no encontrada) en los perfiles
  móvil y tablet, en castellano y en valenciano, y axe NO DEBERÁ reportar violaciones WCAG 2.1
  A/AA.
  *Verificación:* e2e

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-06 Parada y líneas desde el QR | AC-04, AC-16, AC-19 |
| RF-10 Refresco automático ≤ 30 s | AC-12, AC-13, AC-14 |
| RF-15 Ocupación sin depender del color | AC-07 |
| RF-32 Nombres del GTFS | AC-04, AC-05 |
| RNF-01 Rendimiento | AC-21 |
| RNF-03 Accesibilidad | AC-05, AC-07, AC-09, AC-11, AC-15, AC-18, AC-22 |
| RNF-04 Sin registro ni instalación | AC-04 (acceso directo por URL) |
| RNF-05 Compatibilidad móvil/tablet | AC-22 |
| RNF-14 Atribución | (pie de `frontend_i18n`, presente en la vista; AC-22) |
| ADR-010 Contrato tipado | AC-01, AC-02, AC-03 |
| CU-01 flujos alternativos 2a, 4a, 5a, 5b, 5c, 5d | AC-16, AC-09, AC-08, AC-06, AC-07, AC-10 |
