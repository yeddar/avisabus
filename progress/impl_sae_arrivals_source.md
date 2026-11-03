# Implementación: sae_arrivals_source
Spec: specs/sae_arrivals_source/ (v1.3, APPROVED) · Ciclo de revisión: 0 (v1.3)

> **v1.3 (2026-11-03, rama `fix/sae-occupancy-v1.3`):** solo T-14 (`HH:MM:SS`, entradas sin
> tiempo, muestra nocturna real) y T-15. T-01…T-13 son de versiones anteriores. T-08b sigue
> opcional y no se hace.

> **v1.2 (2026-11-02, rama `fix/bloque-1-ajustes`):** solo T-11 (NB-1), T-12 (NB-4, NB-7) y T-13.
> T-01…T-10 son de la v1.1 (aprobadas en la revisión de ciclo 1). T-08b sigue opcional y no se hace.

Primera pasada: T-01…T-07 y T-09 (E-01 ya estaba hecha, `progress/explore_sae.md`). Después,
con la grabación hecha por la persona el 2026-11-02 por la tarde-noche: T-08 y T-10. T-08b
(opcional, requiere red) sigue pendiente de la persona.

## Tareas
- [x] T-01 Modelo normalizado, puerto `ArrivalsSource` y `ArrivalsUnavailableError` (commit 2a3636a)
- [x] T-02 Fixtures iniciales en `tests/fixtures/sae_recordings/samples/` y README (commit efb22f0;
      tests de las fixtures en 52e27ff)
- [x] T-03 Parser `parse_qrphp_html` (commit 370ff7f)
- [x] T-04 `SaeHttpArrivalsSource` (commit 72d8c07)
- [x] T-05 `CachedArrivalsSource` (commit dc4fdb8)
- [x] T-06 Grabación (`RecordingArrivalsSource`) y `SaeReplayArrivalsSource` (commit 6e42a47)
- [x] T-07 CLI `sae fetch` y `sae record` (commit 18c46c5)
- [x] T-08 Grabación real `stop_508_peak` (commit ca36d15). **Grabada fuera de hora punta a
      petición de la persona:** lunes 2026-11-02 (laborable), 20:42:23–21:07:04 Europe/Madrid, en
      lugar de la hora punta del martes prevista en `tasks.md`. Paradas 508 y 2070, intervalo
      20 s, 25 min (75 ciclos, 150 consultas, 0 fallidas, `AVISABUS_SAE_CONTACT` definido; las 150
      respuestas se interpretan sin descartar entradas). Pasos observados en la 508: `offset_s`
      520 (70 Alboraia), 1040 (93 Pass. Marítim), 1180 (70 Alboraia); en la 2070, 8 pasos.
      Documentada en `backend/tests/fixtures/sae_recordings/README.md`; la verifica
      `tests/unit/test_sae_fixtures.py::test_a_real_peak_session_of_stop_508_shows_a_passage` (ver
      D-18).
- [ ] T-08b (opcional) Grabación nocturna — **pendiente de la persona** (requiere red). Comando
      propuesto (hacia las 23:30, ~10 min):
      `AVISABUS_ENV=dev AVISABUS_SAE_CONTACT='<correo>' uv run avisabus sae record --stop 508 --stop 2070 --interval 20 --duration 600 --out tests/fixtures/sae_recordings/night_<AAAA-MM-DD>`
- [x] T-09 Composición `build_arrivals_source`, configuración, `.env.example` y tarea `sae.stats`
      en el ciclo de vida de la app (commit e7e8031)
- [x] T-10 Verificación completa: `./init.sh verify` en verde (ver "Verificación")
- [x] T-11 (v1.2, NB-1) La caché negativa guarda solo el motivo y lanza una instancia nueva en
      cada acierto (AC-11) (commit d90898a)
- [x] T-12 (v1.2, NB-4, NB-7) Comando de regeneración del README con `--out` nueva; clientes HTTP
      de los tests de composición cerrados (commit dd60eae)
- [x] T-13 (v1.2) Verificación completa: `./init.sh verify` en verde (commit de este fichero)
- [x] T-14 (v1.3) Parser: `HH:MM:SS` como `CLOCK_TIME` (AC-03), entradas `"{destino} -"`
      descartadas con `sae.entry_without_time` a nivel `debug` (AC-23), muestra nocturna real de la
      2070 en lugar de la derivada `HH:MM` y README (AC-19 c) (commit 15e9d14)
- [x] T-15 (v1.3) Verificación completa: `./init.sh verify` (ver "Verificación"; commit de este
      fichero)

## Decisiones locales

### v1.3
- **D-24 `ParseResult.without_time` (AC-23):** el parser sigue siendo puro (D-05) y quien registra
  es `build_snapshot`. Para distinguir las entradas sin tiempo de las no interpretables, `ParseResult`
  gana un tercer campo `without_time: tuple[str, ...] = ()` con la **línea** de cada entrada
  descartada por no traer tiempo (en el orden de la página). `build_snapshot` registra por cada una
  `log.debug("sae.entry_without_time", stop_id=…, line=…)` (sin destino ni texto) y no las mete
  en `skipped`, así que no generan `sae.unparsed_entry`. Los dos campos de design §3 no cambian y
  el nuevo tiene valor por defecto (los parsers de prueba que construyen `ParseResult(arrivals,
  skipped)` siguen valiendo).
- **D-25 Regla de "sin tiempo":** tras desescapar y recortar (incluido `\xa0`), el texto termina en
  `" -"` (design §4: "texto que termina en `" -"`"). Se comprueba **antes** de separar por el
  último `" - "`, para que `"Natzaret - Port -"` sea "sin tiempo" y no un tiempo `"Port -"`
  irreconocible. Un texto que tras recortar es solo `"-"` (o `"Alboraia-"`) no termina en `" -"`
  y sigue siendo `sae.unparsed_entry` (`no separator`).
- **D-26 `HH:MM:SS`:** expresión `^\d{1,2}:\d{2}(:\d{2})?$`; segundos > 59 → `invalid clock
  time` (AC-06), igual que horas > 23 o minutos > 59. Los segundos se conservan en `arrival_at` y
  la regla de "no anterior a `fetched_at − 5 min`" (D-06) se aplica con ellos.
- **D-27 Fixture nocturna `samples/night_2026-11-02/`:** junta en una sesión dos respuestas reales
  de la exploración E-01 de `stop_arrivals_api` (`progress/explore_destinations_samples/night_20261102/`):
  la **2070** (`HH:MM:SS`, la que pide T-14 para AC-19 c) y la **2312** (5 entradas sin tiempo
  reales: AC-23 pide verificarlo con "muestra real nocturna" y la 2070 no tiene ninguna; es la única
  de las 22 consultas nocturnas que las tiene). Cuerpos y demás campos sin cambios; `started_at`
  = el de la 2070, el `offset_s` de la 2312 se recalcula (6 s, truncado como en D-09),
  `interval_s = null` (como en D-08) y cada respuesta lleva `source_sample`. Conversión con un
  script desechable (fuera del repositorio). Se borra `samples/derived_clock_time/`.
- **D-28 Tests que usaban la derivada:** `STOP_508_CLOCK_TIME` desaparece de `tests/support/sae.py`
  (pasa a `STOP_2070_NIGHT` y `STOP_2312_WITHOUT_TIME`). Los tests de `HH:MM` del parser cambian la
  última entrada de la página nocturna real (`La Malva-rosa - 01:52:28`) en lugar de la de la
  derivada. `test_cli_sae.py::test_fetch_shows_clock_times_in_madrid` (fuera de la lista de
  ficheros de T-14, pero dependía de la fixture borrada) usa la página nocturna real: la CLI sigue
  mostrando `HH:MM` (`00:42`, `01:52`); no he cambiado el formato de salida de la CLI porque T-14
  no lo pide.

### v1.2
### v1.2
- **D-19 Caché negativa (T-11, AC-11):** `_Entry` guarda `error_reason: str | None` en lugar de la
  excepción. En cada acierto se lanza `ArrivalsUnavailableError(stop_id, error_reason)` nuevo; el
  `stop_id` es la clave de la entrada (el mismo que el del error original). No hay subclases de
  `ArrivalsUnavailableError` (`SaeUnparseableError` no lo es y se traduce antes a
  `unparseable`), así que el tipo se conserva.
- **D-20 Ruta single-flight sin cambios (AC-10):** los llamantes concurrentes de **una misma**
  consulta siguen recibiendo la misma instancia (AC-10: "el mismo error"; design §3: esperan el
  mismo `Future`). La traza de esa instancia solo crece con el número de llamantes de esa consulta
  concreta, no con los aciertos durante `error_ttl`, que es lo que pide AC-11. No apliqué
  `with_traceback(None)` en esa ruta (sugerencia de NB-1) porque no lo pide la spec v1.2 y el test
  de AC-10 comprueba la identidad.
- **D-21 Tests de AC-11:** `test_failure_is_cached_for_the_error_ttl` ya no exige identidad con el
  primer error (ahora compara `stop_id` y `reason`). Dos tests nuevos: aciertos consecutivos dan
  objetos distintos con el mismo `stop_id`/`reason` (con `http_503`, para que el motivo no sea el
  por defecto), y tras 200 aciertos todas las trazas tienen el mismo número de frames, no más que
  la original, y la original no crece. `FakeSource` gana un atributo `reason`.
- **D-22 README (T-12, NB-4):** el comando de regeneración usa una carpeta `--out` nueva
  (`stop_508_<AAAA-MM-DD>`), con las paradas y la duración de la sesión actual (508 y 2070, 20 s,
  1500 s), y explica que `sae record` no sobrescribe, cómo usar la sesión nueva con
  `AVISABUS_SAE_REPLAY_DIR` y que sustituir `stop_508_peak` es una decisión aparte.
- **D-23 Clientes HTTP (T-12, NB-7):** los tres `httpx.AsyncClient()` sueltos de
  `test_sae_compose.py` pasan a `async with`; `test_missing_replay_session_stops_the_composition`
  pasa a ser `async` para poder hacerlo. El comando de la tarea (`-W error::ResourceWarning`) ya
  pasaba antes del cambio, porque httpx no emite `ResourceWarning` si no llegó a abrir conexiones:
  el cambio es de higiene y no tiene un test que falle sin él. NB-2 (el test
  `test_cache_limits_come_from_the_settings` no comprueba el TTL de error configurado) no está en
  el alcance de la v1.2 y no lo he tocado más allá del cliente.

### v1.1

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
  jueves en Madrid, sin fixtures derivadas y con al menos un paso) fallaba hasta T-08.
- **D-18 La sesión de AC-19 (a) puede grabar más paradas:** la comprobación de `stop_508_peak`
  exigía `session.stops == ("508",)`; ahora exige `"508" in session.stops`, porque AC-19 (a) pide
  una sesión real *de* la parada 508 (no *solo* de la 508) y la persona pidió grabar también la
  2070. Se mantienen las demás comprobaciones (intervalo 20 s, `qrphp_html`, de lunes a jueves en
  Madrid, ≥ 15 min, al menos un paso en la 508) y la de "sin fixtures derivadas" se amplía a
  todas las paradas de la sesión (`*/*.json`), no solo a `508/`.

## Bloqueos

Ninguno de spec (no hay CP-3). T-08b (grabación nocturna) sigue opcional y no se hace (la v1.3
cubre AC-19 (c) con la muestra nocturna real de la exploración de `stop_arrivals_api`).

Observaciones no bloqueantes de la v1.3:
- `sae fetch` muestra las horas como `HH:MM` aunque el SAE dé `HH:MM:SS` (los segundos se pierden
  solo en la salida de la CLI; `arrival_at` los conserva). AC-18 no fija el formato (D-28).
- La rama `feat/stop_arrivals_api` es anterior a la v1.3: si usa `derived_clock_time` o
  `STOP_508_CLOCK_TIME`, tendrá que adaptarse al hacer rebase.
- AC-19 (b) sigue cubierto por la derivada `derived_no_arrivals`: ninguna de las 22 respuestas
  nocturnas reales llega sin llegadas (todas traen alguna entrada).

Observaciones no bloqueantes para la persona/spec-writer y el reviewer:
- design §3 nombra `adapters/outbound/sae/parser.py`; §2 y `tasks.md` dicen `qrphp_parser.py`
  (D-07).
- Con el default `AVISABUS_SAE_CONTACT=""` el User-Agent no lleva contacto (D-15).
- `stop_508_peak` no es de hora punta (se grabó por la tarde-noche a petición de la persona);
  el nombre de la carpeta se mantiene porque es el default de `AVISABUS_SAE_REPLAY_DIR`. AC-19 (a)
  no exige hora punta; `tasks.md` (T-08) sí la mencionaba.
- `gtfs_mini` solo tiene las líneas 70, 93, 98 y C2: la parte de la 2070 de la sesión (líneas 73,
  95, 98, 99) solo casa con GTFS para la 98. Lo tendrá que tener en cuenta `stop_arrivals_api`.
- En el README, el comando de T-08 se ha reconstruido a partir de `session.json` (paradas,
  intervalo, carpeta) y de sus 75 ciclos (`--duration 1500`); el contacto figura como
  `<contacto>`.

## Verificación

### v1.3 (2026-11-03, rama `fix/sae-occupancy-v1.3`, tras el commit 15e9d14)
- T-14: `uv run pytest tests/unit/test_sae_parser.py` → 51 passed (los 15 tests nuevos o
  cambiados fallaban antes del cambio del parser). Como en versiones anteriores, ejecutado solo
  falla el umbral global de cobertura (`addopts` mide `domain`+`application` sobre toda la suite).
- T-15: `./init.sh verify` → format, lint, mypy (75 ficheros), lint-imports, pytest 662 passed /
  2 deselected (cobertura `domain`+`application` 99,52 %), frontend format/lint/types/tests (7)/
  build y `feature_list.json` en **verde**; trazabilidad **FAIL** solo por
  `occupancy_sensor.AC-15: ningún test lo cita` (AC nuevo de la otra feature de esta rama, que
  cubre su T-09). Todos los AC de `sae_arrivals_source` (AC-01…AC-23) están citados.
- Tras T-09/T-10 de `occupancy_sensor` (commit c0dbd32), `./init.sh verify` → **todo en verde**:
  pytest 665 passed / 2 deselected (cobertura 99,52 %), trazabilidad AC→test OK.

### v1.2 (2026-11-02, rama `fix/bloque-1-ajustes`, tras el commit dd60eae)
- T-11: `uv run pytest tests/unit/test_sae_cache.py` → 15 passed (los 2 tests nuevos fallaban
  antes del cambio).
- T-12: `uv run pytest tests/unit/test_sae_compose.py -W error::ResourceWarning` → 14 passed.
- T-13: `./init.sh verify` → **todo en verde**: format, lint, mypy (75 ficheros), lint-imports
  (2 contratos), pytest 623 passed / 2 deselected (cobertura `domain`+`application` 99,51 %);
  frontend format/lint/types/tests (7)/build; `feature_list.json` y trazabilidad AC→test OK.

### v1.1

`./init.sh verify` (2026-11-02, tras el commit ca36d15):

```
OK   backend: format
OK   backend: lint
OK   backend: types
OK   backend: architecture
OK   backend: tests   — 617 passed, 2 deselected; cobertura domain+application 99.51 %
OK   frontend: format / lint / types / tests (7 passed) / build
OK   harness: feature_list.json
OK   harness: trazabilidad AC→test   (AC-01…AC-22 de sae_arrivals_source citados)
OK   verify: todo en verde
```
