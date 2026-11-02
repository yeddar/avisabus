# Implementación: sae_arrivals_source
Spec: specs/sae_arrivals_source/ (v1.1, APPROVED) · Ciclo de revisión: 0

Alcance de esta sesión (orquestador): T-01…T-07 y T-09. T-08 y T-08b requieren red y se harán
con la persona (martes 2026-11-03, 7:45). E-01 ya estaba hecha (`progress/explore_sae.md`).

## Tareas
- [x] T-01 Modelo normalizado, puerto `ArrivalsSource` y `ArrivalsUnavailableError` (commit 2a3636a)
- [x] T-02 Fixtures iniciales en `tests/fixtures/sae_recordings/samples/` y README (commit efb22f0;
      tests de las fixtures en 52e27ff)
- [x] T-03 Parser `parse_qrphp_html` (commit 370ff7f)
- [x] T-04 `SaeHttpArrivalsSource` (commit 72d8c07)
- [x] T-05 `CachedArrivalsSource` (commit dc4fdb8)
- [x] T-06 Grabación (`RecordingArrivalsSource`) y `SaeReplayArrivalsSource` (commit 6e42a47)
- [x] T-07 CLI `sae fetch` y `sae record` (commit 18c46c5)
- [ ] T-08 Grabación real `stop_508_peak` — **pendiente de la persona** (requiere red). El test que
      la verifica ya existe (`tests/unit/test_sae_fixtures.py::test_a_real_peak_session_of_stop_508_shows_a_passage`,
      commit 52e27ff) y falla hasta que exista la grabación. Comando exacto (desde `backend/`,
      martes 2026-11-03 a las 7:45; dura 15 min):

      ```
      cd backend
      AVISABUS_ENV=dev AVISABUS_SAE_CONTACT='<correo de contacto>' \
        uv run avisabus sae record --stop 508 --interval 20 --duration 900 \
        --out tests/fixtures/sae_recordings/stop_508_peak
      ```

      Después: `uv run pytest tests/unit/test_sae_fixtures.py --no-cov` (debe detectar al menos un
      paso de autobús), completar la sección `stop_508_peak/` del README de las fixtures (fecha,
      hora, comando, paso observado) y hacer commit de la carpeta. Si no se detecta ningún paso,
      repetir otro día laborable de lunes a jueves con `--out` nuevo (la CLI se niega a
      sobrescribir una sesión existente).
- [ ] T-08b (opcional) Grabación nocturna — **pendiente de la persona** (requiere red). Comando
      propuesto (hacia las 23:30, ~10 min):
      `AVISABUS_ENV=dev AVISABUS_SAE_CONTACT='<correo>' uv run avisabus sae record --stop 508 --stop 2070 --interval 20 --duration 600 --out tests/fixtures/sae_recordings/night_<AAAA-MM-DD>`
- [x] T-09 Composición `build_arrivals_source`, configuración, `.env.example` y tarea `sae.stats`
      en el ciclo de vida de la app (commit e7e8031)
- [ ] T-10 Verificación completa — en rojo solo por T-08 (ver "Verificación")

## Decisiones locales

Dentro de design §9 (reglas del parser derivadas de E-01, librería de parseo):

- **D-01 Parser con `html.parser`** de la biblioteca estándar (recomendación de E-01); sin
  dependencias nuevas.
- **D-02 Cabecera** = el texto del primer `<div>` cuyo `style` contiene `background: grey`
  (espacios flexibles, sin distinguir mayúsculas). Se compara con `^{stop_id} - .+$` tras recortar.
  Sin ese `<div>`, con texto vacío o de otra parada → `SaeUnparseableError`.
- **D-03 Entradas** solo después de la cabecera: cada `<img title>` abre una entrada y su texto es
  el siguiente `<span>` que **no** sea `class="imagenParada"` (el que envuelve el icono). Una
  entrada sin texto o con `title` vacío se descarta (AC-06). Lo descubrió un test: sin esa
  exclusión, una entrada sin texto se tragaba el icono de la siguiente.
- **D-04 Cuerpo** decodificado como UTF-8 estricto (E-01: UTF-8 confirmado); si no es UTF-8 →
  no interpretable.
- **D-05 Motivos de `sae.unparsed_entry`**: `no separator in '<texto>'`,
  `unrecognised time '<tiempo>'`, `invalid clock time '<tiempo>'` (p. ej. `25:61`),
  `entry without text`, `entry without line`; el texto citado se recorta a 60 caracteres y nunca
  se incluye el cuerpo. El parser es puro (devuelve `skipped`); quien registra el evento es
  `build_snapshot`, compartido por las fuentes HTTP y de replay.
- **D-06 `HH:MM`**: la fecha de partida es la de `fetched_at − 5 min` en `Europe/Madrid`; si esa
  hora ese día cae antes del umbral, se pasa al día siguiente. Así, una `23:59` vista a las 00:02
  es la de ayer (AC-03, "no anterior a fetched_at − 5 min").

Fuera de la lista de design §9 (detalles que la spec no fija; los anoto para el reviewer):

- **D-07 Módulo del parser:** design §3 cita `adapters/outbound/sae/parser.py`, pero la tabla de
  §2 y `tasks.md` dicen `sae/qrphp_parser.py`; uso este último. `ParseResult`,
  `SaeUnparseableError`, `PARSERS` y `build_snapshot` viven ahí; `RawResponse`, `RawObserver` y
  `build_user_agent` en `http_source.py`; `SaeSession`/`SaeRecording` en `recording.py`.
- **D-08 Fixtures de E-01:** las muestras reales se agrupan en una sola sesión
  `samples/e01_2026-11-02/` (paradas 508, 2070 y 99999, `offset_s` desde la primera petición,
  10:59:09 Z) y las derivadas en `samples/derived_no_arrivals/` y `samples/derived_clock_time/`.
  Como las peticiones de E-01 fueron manuales e irregulares, `interval_s` es `null` en esas
  sesiones (el lector lo admite; `sae record` siempre lo rellena). Las respuestas convertidas
  llevan además `source_sample` y `source_url` informativos. La derivada `HH:MM` cambia la
  **última** llegada (`Alboraia - 20 min.` → `Alboraia - 22:41`) para que el orden siga siendo
  ascendente.
- **D-09 Fichero de grabación:** `offset_s` = segundos enteros (truncados) desde `started_at`;
  nombre `<offset_s:06d>.json`; fechas ISO 8601 con `Z` (con microsegundos si los hay). La fuente
  HTTP solo rellena `error` (`timeout`/`network`) cuando no hubo respuesta; una respuesta no 2xx se
  graba con su `status` y su cuerpo, y el replay la convierte en `http_<código>`.
- **D-10 Replay:** si el directorio o `session.json` no existen o no se pueden leer (igual que un
  `source_format` desconocido) → `ConfigurationError` al construirse; las grabaciones se cargan
  todas al construir. Pasado el último `offset_s` se sigue devolviendo la última grabación (lectura
  literal de AC-15). Consecuencia: en `env=test` la API no arranca sin una sesión válida en
  `AVISABUS_SAE_REPLAY_DIR`; por eso `tests/integration/test_main_composition.py` (de
  `occupancy_sensor`) ahora fija esa variable a la sesión E-01 en su subproceso (cambio mínimo de
  entorno, sin tocar lo que comprueba). En `main.py` la fuente se compone **antes** de abrir la BD,
  como ya prometía su docstring para los errores de configuración.
- **D-11 Caché — contadores:** `hits` = peticiones servidas desde una entrada vigente (también los
  errores cacheados); `misses` = el resto (incluidas las que se unen a una consulta en vuelo);
  `errors` = consultas a la fuente que fallaron. Son acumulados desde el arranque (no se reinician
  en cada `sae.stats`). Single-flight con una `Task` por parada esperada con `asyncio.shield`, de
  modo que cancelar a un llamante no cancela la consulta compartida. Solo se cachean los
  `ArrivalsUnavailableError`; otra excepción inesperada se propaga sin cachear.
- **D-12 `build_arrivals_source`** devuelve `CachedArrivalsSource` (subtipo de `ArrivalsSource`
  en lugar del puerto, como dice design §2) para que `main.py` pueda programar `emit_stats`.
- **D-13 Tarea `sae.stats`:** `background/sae_stats.py` (`run_sae_stats`, cada 5 min, `sleep`
  inyectable). Se arranca y cancela en un `lifespan` definido en `main.py`, que además cierra el
  `httpx.AsyncClient` del SAE. Para ello `create_app` acepta un parámetro opcional `lifespan`
  (`adapters/inbound/http/app.py`, cambio mínimo).
- **D-14 CLI:** `sae fetch` usa la fuente HTTP directamente (sin caché ni replay), igual que
  `record`: ambos son para mirar el SAE real. Salida en castellano como las demás CLI; las horas
  `HH:MM` se muestran en `Europe/Madrid`. Códigos de salida: `fetch` → 1 si las llegadas no están
  disponibles (con `ERROR: … (motivo: <reason>)` en stderr); `record` → 0 una vez empezado
  (AC-17), 2 si `--out` ya contiene un `session.json` (para no sobrescribir una grabación) u
  opciones inválidas (`--interval`/`--duration` ≥ 1, `--stop` obligatorio y repetible; las
  paradas repetidas se deduplican). `record` hace `ceil(duration / interval)` ciclos (900/20 →
  45 consultas en los offsets 0…880) y espera hasta el inicio del ciclo siguiente descontando lo
  que tardaron las consultas.
- **D-15 User-Agent:** `AvisaBus/<versión> (TFM; <contacto>)` literal (design §7). Con el
  contacto por defecto (`""`) queda `AvisaBus/0.1.0 (TFM; )`: AC-01 pide "un contacto", así que
  hay que definir `AVISABUS_SAE_CONTACT` antes de consultar el SAE (está en el comando de T-08 y en
  `.env.example`). No lo he hecho obligatorio porque la spec fija el default `""`.
- **D-16 Validación de configuración:** `AVISABUS_SAE_URL_TEMPLATE` debe contener `{stop_id}` y
  ningún otro marcador (si no, `ConfigurationError`); `SAE_TIMEOUT_S > 0`, `SAE_CACHE_TTL_S ≥ 0`,
  `SAE_ERROR_TTL_S ≥ 0`, `SAE_MAX_CONCURRENCY ≥ 1`. En la URL, el `stop_id` se escapa
  (`quote(…, safe="")`).
- **D-17 Test de T-08 adelantado:** `tests/unit/test_sae_fixtures.py` incluye ya el detector de
  paso de autobús (la primera ETA de una línea+destino está en 0–2 min y en la respuesta siguiente
  salta ≥ 3 min hasta lo que era el bus siguiente, ±3 min) y lo valida con el paso real de la 95 en
  la parada 2070 (E-01). La comprobación de `stop_508_peak` (≥ 15 min, intervalo 20 s, de lunes a
  jueves en Madrid, sin fixtures derivadas y con al menos un paso) falla hasta T-08.

## Bloqueos

Ninguno de spec (no hay CP-3). Pendiente operativo: T-08 (y T-08b opcional) requieren red y se
harán con la persona.

Observaciones no bloqueantes para la persona/spec-writer:
- design §3 nombra `adapters/outbound/sae/parser.py`; §2 y `tasks.md` dicen `qrphp_parser.py`
  (D-07).
- Con el default `AVISABUS_SAE_CONTACT=""` el User-Agent no lleva contacto (D-15).
- El README de las fixtures ya describe las sesiones de `samples/` y deja preparado el apartado
  de `stop_508_peak/` para T-08.

## Verificación

`./init.sh verify` (2026-11-02, tras el último commit 52e27ff):

```
OK   backend: format
OK   backend: lint
OK   backend: types
OK   backend: architecture
FAIL backend: tests   — 1 failed, 616 passed, 2 deselected; cobertura domain+application 99.51 %
OK   frontend: format / lint / types / tests (7 passed) / build
OK   harness: feature_list.json
OK   harness: trazabilidad AC→test   (AC-01…AC-22 de sae_arrivals_source citados)
FAIL verify: 1 paso(s) fallido(s): backend: tests
```

El único fallo es
`tests/unit/test_sae_fixtures.py::test_a_real_peak_session_of_stop_508_shows_a_passage`:
`AssertionError: stop_508_peak has not been recorded yet (T-08, needs the network …)`. Falla
**únicamente** porque falta la grabación real de T-08 (`tests/fixtures/sae_recordings/stop_508_peak/`
no existe); no se ha falseado ni sorteado. AC-19 (a) queda sin evidencia hasta entonces. Al
grabarla con el comando de T-08 el test debe pasar y `./init.sh verify` quedar en verde (T-10).
