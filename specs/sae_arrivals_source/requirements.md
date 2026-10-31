# Fuente de llegadas del SAE — requirements

> Feature: `sae_arrivals_source` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-07, RF-08, RF-11, RF-35, RNF-08, RNF-10, RNF-13 · Casos de uso: CU-01 · Depende de: project_scaffold

## Contexto

Los tiempos de llegada en tiempo real proceden del sistema SAE de EMT València, accesible por
parada a través del enlace "próximas llegadas" que publica el Ajuntament en su dataset de paradas
EMT. **No es una API documentada oficialmente** (riesgo R-01), por lo que:

- se consulta con moderación (caché por parada, una sola petición simultánea por parada,
  límite global de concurrencia, caché negativa ante errores);
- se graban respuestas reales para que los tests y las demos no dependan de la red;
- el formato bruto se aísla en un parser; el resto del sistema solo ve el modelo normalizado.

Referencia del formato conocido (cliente comunitario `emtvlcapi`): por cada llegada, `linea`,
`destino` y `minutos`, o bien `horaLlegada` (`HH:MM`) para algunas líneas (p. ej. nocturnas).
**El endpoint y el formato exactos se confirman en la exploración E-01** antes de implementar.

## Alcance

- Puerto `ArrivalsSource` y modelo normalizado `ArrivalsSnapshot` / `SaeArrival`.
- Adaptador HTTP + parser del formato del SAE.
- Decorador de caché (TTL, single-flight, caché negativa, límite de concurrencia, contadores).
- Decorador de grabación y adaptador de reproducción (replay) dirigido por el reloj.
- CLI `avisabus sae fetch` y `avisabus sae record`.
- Grabaciones reales como fixtures.

## Fuera de alcance

- Resolución de sentido, emparejamiento con viajes GTFS, ocupación y respaldo por horario
  (feature `stop_arrivals_api`).
- Detección de paso de autobuses (feature `alert_expiry`; aquí solo se graban datos que la
  permitan probar).

## Criterios de aceptación

### Normalización

- **sae_arrivals_source.AC-01** — CUANDO se piden las llegadas de una parada, EL ADAPTADOR HTTP
  DEBERÁ hacer una única petición al SAE para ese `stop_id` con el timeout configurado y una
  cabecera `User-Agent` que identifique el proyecto y un contacto, y devolver un
  `ArrivalsSnapshot` con `stop_id`, `fetched_at` (del `Clock`) y la lista de llegadas.
  *Verificación:* integration (transporte HTTP simulado)
- **sae_arrivals_source.AC-02** — CUANDO una llegada viene expresada en minutos, EL SISTEMA
  DEBERÁ normalizarla con `kind = MINUTES`, `minutes = n` y `arrival_at = fetched_at + n min`.
  *Verificación:* unit (parser) con muestras reales
- **sae_arrivals_source.AC-03** — CUANDO una llegada viene expresada como hora `HH:MM`, EL
  SISTEMA DEBERÁ normalizarla con `kind = CLOCK_TIME` y `arrival_at` igual a la siguiente
  ocurrencia de esa hora en `Europe/Madrid` no anterior a `fetched_at − 5 min`.
  *Verificación:* unit (incluido el cruce de medianoche)
- **sae_arrivals_source.AC-04** — CUANDO el SAE indica que el autobús está llegando o en la
  parada (marcadores identificados en E-01), EL SISTEMA DEBERÁ normalizarlo como `MINUTES` con
  `minutes = 0`.
  *Verificación:* unit con muestras reales
- **sae_arrivals_source.AC-05** — EL SISTEMA DEBERÁ conservar `line` y `destination` tal como
  los devuelve el SAE, eliminando solo espacios al principio y al final.
  *Verificación:* unit
- **sae_arrivals_source.AC-06** — SI una entrada concreta no se puede interpretar, ENTONCES EL
  SISTEMA DEBERÁ descartarla, registrar `sae.unparsed_entry` (con `stop_id` y el motivo, sin el
  cuerpo completo) y devolver el resto de llegadas.
  *Verificación:* unit
- **sae_arrivals_source.AC-07** — CUANDO el SAE responde correctamente sin llegadas, EL SISTEMA
  DEBERÁ devolver un `ArrivalsSnapshot` con la lista vacía (no un error).
  *Verificación:* unit con muestra real
- **sae_arrivals_source.AC-08** — SI la petición falla (error de red, timeout, código HTTP ≠ 2xx)
  o el cuerpo completo no es interpretable, ENTONCES EL SISTEMA DEBERÁ lanzar
  `ArrivalsUnavailableError` con un motivo (`timeout`, `http_<código>`, `network`,
  `unparseable`) y registrar `sae.error`.
  *Verificación:* integration (transporte simulado)

### Caché y uso respetuoso (RNF-08)

- **sae_arrivals_source.AC-09** — MIENTRAS una respuesta de una parada tenga menos antigüedad
  que el TTL (20 s por defecto), EL SISTEMA DEBERÁ devolverla desde caché sin consultar la fuente.
  *Verificación:* unit (FakeClock)
- **sae_arrivals_source.AC-10** — CUANDO llegan varias peticiones concurrentes para la misma
  parada sin dato en caché, EL SISTEMA DEBERÁ hacer una sola consulta a la fuente y entregar el
  mismo resultado (o el mismo error) a todas.
  *Verificación:* unit (asyncio.gather)
- **sae_arrivals_source.AC-11** — SI la fuente falla para una parada, ENTONCES durante los
  siguientes 5 s (configurable) EL SISTEMA DEBERÁ responder `ArrivalsUnavailableError` para esa
  parada sin volver a consultarla.
  *Verificación:* unit
- **sae_arrivals_source.AC-12** — EL SISTEMA DEBERÁ limitar a 4 (configurable) las consultas
  simultáneas a la fuente, sumando todas las paradas.
  *Verificación:* unit
- **sae_arrivals_source.AC-13** — EL SISTEMA DEBERÁ llevar contadores de aciertos de caché,
  fallos de caché y errores de la fuente, y registrar cada 5 minutos el evento `sae.stats` con
  sus valores.
  *Verificación:* unit

### Grabación y reproducción (RF-35)

- **sae_arrivals_source.AC-14** — DONDE la grabación esté activa, EL SISTEMA DEBERÁ guardar cada
  respuesta bruta de la fuente HTTP en `<dir>/<stop_id>/<offset_s>.json` con `stop_id`,
  `captured_at`, `offset_s` (segundos desde el inicio de la sesión), estado HTTP, `content_type`
  y el cuerpo, y un `session.json` con el inicio, las paradas y el intervalo.
  *Verificación:* integration (tmp_path)
- **sae_arrivals_source.AC-15** — CUANDO se piden llegadas a la fuente de replay, EL SISTEMA
  DEBERÁ devolver la grabación de esa parada con mayor `offset_s` que no supere el tiempo
  transcurrido desde el inicio del replay según el `Clock`, interpretada con el mismo parser que
  la fuente HTTP y con `fetched_at = clock.now()`.
  *Verificación:* unit (FakeClock avanzando)
- **sae_arrivals_source.AC-16** — SI la parada no tiene grabaciones, o la grabación seleccionada
  registra un error, ENTONCES LA FUENTE DE REPLAY DEBERÁ lanzar `ArrivalsUnavailableError`.
  *Verificación:* unit
- **sae_arrivals_source.AC-17** — CUANDO se ejecuta
  `avisabus sae record --stop 508 --interval 20 --duration 900 --out <dir>`, LA CLI DEBERÁ
  consultar cada parada cada `interval` segundos durante `duration` segundos grabando las
  respuestas, y terminar con código 0 aunque alguna consulta falle (el fallo queda grabado).
  *Verificación:* integration (reloj y espera inyectados, transporte simulado)
- **sae_arrivals_source.AC-18** — CUANDO se ejecuta `avisabus sae fetch --stop 508`, LA CLI
  DEBERÁ mostrar las llegadas normalizadas (línea, destino, minutos u hora) o el motivo del error.
  *Verificación:* integration
- **sae_arrivals_source.AC-19** — EL REPOSITORIO DEBERÁ incluir en
  `backend/tests/fixtures/sae_recordings/` al menos: (a) una sesión real de la parada 508 de
  ≥ 15 min con intervalo de 20 s en la que se observe el paso de al menos un autobús (su ETA llega
  a 0 o desaparece y la primera llegada de la línea salta a la siguiente); (b) una respuesta real
  sin llegadas o, si no es posible obtenerla, una derivada de una real y documentada; (c) una
  respuesta con hora `HH:MM` (real o derivada documentada); (d) un caso de error grabado. El
  `README.md` DEBERÁ describir cada sesión, su fecha y cómo se obtuvo.
  *Verificación:* revisión + tests que las usan

### Configuración y composición

- **sae_arrivals_source.AC-20** — CUANDO `AVISABUS_ARRIVALS_SOURCE=replay`, EL SISTEMA DEBERÁ
  componer la fuente de replay sobre `AVISABUS_SAE_REPLAY_DIR`; CUANDO es `http` (por defecto en
  `dev`/`prod`), la fuente HTTP; en ambos casos envuelta por la caché. EL ENTORNO `test` DEBERÁ
  usar replay por defecto.
  *Verificación:* unit (función de composición)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-07 Tiempos reales del SAE | AC-01, AC-07, AC-08 |
| RF-08 Caché por parada | AC-09, AC-10 |
| RF-11 Normalización (minutos / hora) | AC-02, AC-03, AC-04, AC-05, AC-06 |
| RF-35 Grabar y reproducir | AC-14, AC-15, AC-16, AC-17, AC-19 |
| RNF-08 Uso respetuoso / resiliencia | AC-08, AC-10, AC-11, AC-12 |
| RNF-10 Tests sin red | AC-15, AC-16, AC-19, AC-20 |
| RNF-13 Observabilidad | AC-06, AC-08, AC-13 |
| Depuración (CU-01) | AC-18 |
