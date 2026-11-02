# Revisión: sae_arrivals_source — v1.2
Ciclo: 1 (v1.2) · Fecha: 2026-11-02 · Agente: reviewer · Spec: `specs/sae_arrivals_source/` v1.2 (APPROVED) · Rama: `fix/bloque-1-ajustes` (commits `d90898a` T-11, `dd60eae` T-12 y `485a88f` T-13 sobre `develop`)

## Veredicto: APPROVED

T-11, T-12 y T-13 están hechas. AC-11 (ampliado en v1.2) tiene dos tests nuevos que fallan con la
implementación anterior: lo he comprobado restaurando `cache.py` de `develop`. Los 22 AC conservan
su evidencia y `./init.sh verify` está en verde. Ningún hallazgo bloqueante. T-08b sigue
opcional y no bloquea.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `tests/integration/test_sae_http_source.py` | OK | Sin cambios desde v1.1 |
| AC-02 … AC-07 | `tests/unit/test_sae_parser.py` | OK | Sin cambios |
| AC-08 | `test_sae_http_source.py` | OK | Sin cambios |
| AC-09 | `tests/unit/test_sae_cache.py` | OK | Sin cambios |
| AC-10 | `test_sae_cache.py` | OK | Sin cambios. Los llamantes concurrentes siguen recibiendo el mismo resultado o error de la `Task` compartida. |
| **AC-11 (v1.2)** | `test_sae_cache.py::test_failure_is_cached_for_the_error_ttl`, `::test_each_cache_hit_raises_a_new_instance_with_the_same_stop_and_reason`, `::test_traceback_does_not_grow_with_cache_hits`, `::test_error_ttl_is_configurable` | OK | (1) Durante 5 s no se vuelve a consultar la fuente (`inner.calls == ["508"]`) y a los 5 s sí. (2) El original y 3 aciertos dan 4 objetos distintos, todos `ArrivalsUnavailableError` con el mismo `stop_id` y `reason` (`http_503`, distinto del valor por defecto del fake). (3) Tras 200 aciertos la traza tiene siempre la misma longitud, no supera la del original, y el original no cambia. **Mutación:** con `cache.py` de `develop` fallan los tests (2) y (3). Implementación: `cache.py:40-41` guarda solo `error_reason`, y `:68-69` crea la instancia nueva. |
| AC-12 | `test_sae_cache.py` | OK | Sin cambios |
| AC-13 | `test_sae_cache.py`, `test_sae_compose.py`, `test_main_sae.py` | OK | `test_stats_task_logs_the_cache_counters` usa ahora `async with httpx.AsyncClient()`; lo que comprueba no cambia. |
| AC-14, AC-15 | `test_sae_recording.py`, `test_sae_replay.py` | OK | Sin cambios |
| AC-16 | `test_sae_replay.py` | OK | Sin cambios |
| AC-17, AC-18 | `tests/integration/test_cli_sae.py` | OK | Sin cambios |
| AC-19 | `test_sae_fixtures.py`, `test_sae_parser.py`, `test_sae_replay.py` + revisión del README | OK | La sección "Regeneración" del README cambia (NB-4, ver abajo); las fixtures no. |
| AC-20 | `test_sae_compose.py`, `test_main_sae.py` | OK | Los clientes HTTP se cierran (NB-7); las aserciones no cambian. |
| AC-21 | `test_sae_parser.py`, `test_sae_http_source.py` | OK | Sin cambios |
| AC-22 | `test_sae_compose.py`, `test_sae_recording.py`, `test_sae_replay.py`, `test_main_sae.py` | OK | `test_missing_replay_session_stops_the_composition` pasa a ser `async` para cerrar el cliente; sigue esperando `ConfigurationError`. |

## Verificación ejecutada

- `./init.sh verify` → **todo en verde** (exit 0): 645 passed y 2 deselected, cobertura del
  99,52 %, lint-imports con 2 contratos respetados, frontend OK y trazabilidad OK (detalle en
  `review_stop_tokens_qr.md`, misma ejecución).
- `cd backend && uv run pytest tests/unit/test_sae_compose.py -W error::ResourceWarning` (la
  verificación de T-12) → 14 passed.
- `cd backend && uv run pytest tests/unit/test_sae_cache.py` → 15 passed. Con `cache.py` de
  `develop` en una copia del scratchpad: 2 failed (los dos tests nuevos de AC-11) y 13 passed.
- README: lo que dice coincide con el código y la fixture. `sae record` sale con 2 si `--out` ya
  tiene `session.json` (`cli/sae.py:104-106`). `stop_508_peak/session.json` tiene las paradas
  508 y 2070, intervalo de 20 s y 75 muestras por parada (unos 25 min). `stop_508_peak` es el
  valor por defecto de `sae_replay_dir` (`config.py:53`).

## Comprobación de `docs/verification.md` §4 (lo nuevo)

- **Contrato:** design §3 "Caché (detalle)" v1.2 guarda solo el motivo y crea una instancia nueva
  por acierto, y es lo que hace el código. Los puntos de design de NB-6 (`-> CachedArrivalsSource`
  en `compose.py:20-22`; `interval_s: int | None` en `recording.py:34,53`) ya coincidían con el
  código.
- **Arquitectura:** sin cambios en `domain/`. Sin `datetime.now()`: los tiempos vienen de
  `self._clock`.
- **Tests:** sin red y con `FakeClock`. Los tests nuevos no son tautológicos (mutación).
- **Privacidad:** sin cambios en los logs.
- **Convenciones:** `fix(sae_arrivals_source)`, `test(sae_arrivals_source)` y `chore(progress)`.
- **Alcance:** solo `cache.py`, `test_sae_cache.py`, `test_sae_compose.py` y el README de las
  fixtures, todos en la lista de ficheros de T-11 y T-12.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **O-01 — Por la ruta de la `Task` compartida, los llamantes concurrentes reciben la misma
  instancia del error.** `backend/src/avisabus/adapters/outbound/sae/cache.py:78` (`return await
  asyncio.shield(task)`). Lo pide AC-10 ("el mismo error a todas") y AC-11 v1.2 solo habla de los
  aciertos de la caché, así que es conforme a la spec. La traza solo crece con el número de
  llamantes concurrentes de un único fallo, no con la carga sostenida durante `error_ttl`, que
  era el problema de NB-1. Lo anoto por si `stop_arrivals_api` registra trazas de este error.
- Siguen abiertos de la revisión anterior, fuera del alcance de v1.2: NB-2 (el test de AC-20 no
  avanza el reloj), NB-3 (el detector de pasos es laxo), NB-5 (nombre `stop_508_peak`) y NB-8
  (`AVISABUS_SAE_CONTACT` vacío por defecto).

### Problemas de spec

Ninguno. NB-6 queda resuelto en el design v1.2.

---

# Revisión: sae_arrivals_source — v1.1 (revisión anterior)
Ciclo: 1 · Fecha: 2026-11-02 · Agente: reviewer
Spec: `specs/sae_arrivals_source/` v1.1 (APPROVED) · Rama: `feat/sae_arrivals_source` (base `develop`)

## Veredicto: APPROVED

Los 22 AC tienen al menos un test que los cita y que comprueba el comportamiento de verdad.
`./init.sh verify` está en verde. No hay cambios fuera del alcance que no estén justificados por
una tarea. Los hallazgos son todos **no bloqueantes**.

Contexto que dio la persona y que se ha tenido en cuenta (no aparece en la spec):
- T-08 se grabó el lunes 2026-11-02, de 20:42 a 21:07, fuera de la hora punta, con las paradas
  508 y 2070 durante 25 min. La persona lo aceptó con la condición de que se viera al menos un
  paso en la 508, y se cumple (ver AC-19).
- D-18 (la sesión de AC-19 (a) puede incluir otras paradas) se acepta.
- T-08b es opcional y no bloquea.
- `parser.py` (design §3) frente a `qrphp_parser.py`: lo corregirá la persona en la spec. No se
  cuenta como hallazgo.
- El contacto del User-Agent sale de `AVISABUS_SAE_CONTACT`, y la persona lo da por resuelto.

## Matriz AC → evidencia

Todos los tests están en `backend/tests/`.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `integration/test_sae_http_source.py::test_single_request_with_url_timeout_and_user_agent`, `::test_stop_id_is_escaped_in_the_url`, `::test_raw_response_is_handed_to_the_observer` | OK | Comprueba que se hace una sola petición GET, la URL exacta, el `User-Agent`, el timeout (en las `extensions` de la petición) y que `fetched_at` sale del FakeClock (incluida la latencia). También se comprueba que el `stop_id` se escapa en la URL. |
| AC-02 | `unit/test_sae_parser.py::test_minutes_are_normalised_with_arrival_at_relative_to_fetched_at`, `::test_minutes_without_final_dot_are_accepted`, `::test_arrival_at_is_utc` | OK | Usa una muestra real (508, E-01). Compara `ParseResult` completo por igualdad. |
| AC-03 | `unit/test_sae_parser.py` (6 tests de `HH:MM`) | OK | Cubre: mismo día, cruce de medianoche, el límite exacto de −5 min (22:40 se acepta y 22:39 pasa al día siguiente), 23:59 vista a las 00:02 cuenta como "ayer", horario de verano y una hora de 1 cifra. Usa la muestra derivada documentada. |
| AC-04 | `unit/test_sae_parser.py::test_proximo_in_a_real_sample_is_zero_minutes`, `::test_proximo_ignores_case_and_accents` | OK | Usa la muestra real de la 2070, línea 95. Está parametrizado con mayúsculas y sin acentos. |
| AC-05 | `unit/test_sae_parser.py::test_line_and_destination_are_kept_verbatim_but_trimmed`, `::test_destination_containing_the_separator_is_split_at_the_last_one`, `::test_html_entities_are_unescaped` | OK | Cubre el recorte de `&nbsp;`, el corte por el último `" - "` y las entidades HTML. |
| AC-06 | `unit/test_sae_parser.py::test_uninterpretable_entry_is_skipped_and_the_rest_returned`, `::test_entry_without_text_or_line_is_skipped`, `::test_skipped_entries_are_logged_with_stop_and_reason_but_not_the_body` | OK | Comprueba que el log `sae.unparsed_entry` lleva `stop_id` y el motivo, y que no incluye el resto de la página. |
| AC-07 | `unit/test_sae_parser.py::test_valid_page_without_arrivals_is_an_empty_list` | OK | Usa una muestra derivada documentada, que AC-19 (b) permite. |
| AC-08 | `integration/test_sae_http_source.py::test_transport_failures_raise_unavailable_with_reason_and_log`, `::test_non_2xx_status_raises_http_reason`, `::test_unparseable_body_raises_unparseable_and_logs`, `::test_successful_fetch_logs_no_error` | OK | Cubre `timeout` (3 variantes), `network`, `http_<código>` (301/404/429/500/503) y `unparseable`. Comprueba `sae.error` con `elapsed_ms` exacto y que el cuerpo no se registra. |
| AC-09 | `unit/test_sae_cache.py::test_fresh_snapshot_is_served_from_cache`, `::test_snapshot_as_old_as_the_ttl_is_fetched_again`, `::test_ttl_is_per_stop_and_configurable` | OK | Prueba los límites 19,9 s y 20 s con FakeClock. |
| AC-10 | `unit/test_sae_cache.py::test_concurrent_requests_share_one_fetch_and_result`, `::test_concurrent_requests_share_the_same_error`, `::test_cancelling_one_caller_does_not_cancel_the_shared_fetch` | OK | Usa `asyncio.gather` y un `Event`. Comprueba que todos reciben el mismo objeto (resultado o error). |
| AC-11 | `unit/test_sae_cache.py::test_failure_is_cached_for_the_error_ttl`, `::test_error_ttl_is_configurable`, `::test_failure_of_one_stop_does_not_affect_another` | OK | Prueba los límites 4,9 s y 5 s. |
| AC-12 | `unit/test_sae_cache.py::test_simultaneous_fetches_are_limited_across_stops` | OK | 10 paradas con límite 4 y 2: comprueba `in_flight == limit` y `max_in_flight == limit`. |
| AC-13 | `unit/test_sae_cache.py::test_counts_hits_misses_and_source_errors`, `::test_emit_stats_logs_the_counters`, `unit/test_sae_compose.py::test_stats_are_emitted_every_five_minutes`, `::test_stats_task_logs_the_cache_counters`, `integration/test_main_sae.py::test_app_lifespan_runs_the_stats_task_over_the_replayed_source` | OK | El `sleep` está inyectado (300 s). La tarea arranca y se cancela con el `lifespan` de la app. |
| AC-14 | `integration/test_sae_recording.py` (4 tests) | OK | Comprueba `session.json` campo a campo, los ficheros `<stop>/<offset>.json` de una respuesta 200, de una 503 y de un timeout, el base64 de cuerpos binarios, y que grabar y reproducir da el mismo resultado. |
| AC-15 | `unit/test_sae_replay.py` (4 tests), `integration/test_sae_recording.py::test_recorded_session_replays_like_the_live_source` | OK | El FakeClock avanza: con 61 s se sigue usando la grabación anterior y con 62 s cambia a la de `offset_s` 62. Comprueba `fetched_at = clock.now()` y que se usa el mismo parser que la fuente HTTP. |
| AC-16 | `unit/test_sae_replay.py::test_stop_without_recordings_is_unavailable`, `::test_stop_without_a_recording_yet_is_unavailable`, `::test_recorded_error_is_replayed_as_unavailable`, `::test_recorded_unknown_stop_page_is_unparseable` | OK | Cubre `no_recording`, `timeout`, `network`, `http_503` y `unparseable`. |
| AC-17 | `integration/test_cli_sae.py` (4 tests de `record`) | OK | El comando exacto del AC hace 45 consultas en los offsets 0…880 con un `sleep` compensado. Con fallos intercalados en 2 paradas, sale con código 0 y los fallos quedan grabados. También se rechazan las opciones inválidas y que se sobrescriba una sesión. |
| AC-18 | `integration/test_cli_sae.py` (5 tests de `fetch`) | OK | Muestra minutos, `HH:MM` (en hora de Madrid), "sin llegadas" y el motivo del error (`unparseable`, `http_503`, `timeout`). |
| AC-19 | `unit/test_sae_fixtures.py` (7 tests), más `test_sae_parser.py` y `test_sae_replay.py` | OK | (a) `stop_508_peak`: es real, con intervalo de 20 s, 25 min y en lunes. El detector encuentra en la 508 pasos en los offsets 520 (70), **1040 (93: ETA 0 → la siguiente)** y 1180 (70). Lo comprobé yo con el detector. (b) y (c) son muestras derivadas con `derived_from` y `note`: comparé byte a byte con las de `progress/explore_sae_samples/` y solo cambia lo documentado. (d) es la parada real 99999. Las 10 respuestas reales de E-01 son idénticas a sus muestras de origen. El README documenta las 4 sesiones con fecha y cómo se obtuvieron. Ver NB-3 y NB-4. |
| AC-20 | `unit/test_sae_compose.py` (8 tests), `integration/test_main_sae.py` (2 tests) | OK | Por defecto, `replay` en `test` y `http` en `dev`/`prod`, y se puede forzar. Las dos fuentes van envueltas en la caché. Con replay no se hace ninguna petición HTTP. `main.py` no arranca si no hay una sesión válida. Ver NB-2. |
| AC-21 | `unit/test_sae_parser.py` (3 tests), `integration/test_sae_http_source.py::test_unparseable_body_raises_unparseable_and_logs` | OK | Usa la muestra real de la 99999, cabeceras de otras paradas (`2070`, `50`, `5080`), una cabecera fuera de su bloque, `"508 -"` y un cuerpo que no es UTF-8. |
| AC-22 | `unit/test_sae_replay.py` (5 tests), `integration/test_sae_recording.py::test_session_file_has_start_stops_interval_and_format`, `unit/test_sae_compose.py::test_missing_replay_session_stops_the_composition`, `integration/test_main_sae.py::test_application_refuses_to_start_without_a_usable_replay_session` | OK | Un formato desconocido o ausente da `ConfigurationError` al construir la fuente. El parser se elige según el registro `PARSERS` (probado con un parser alternativo). |

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `./init.sh verify` | **OK, todo en verde.** Backend: format, lint, mypy, lint-imports y pytest (617 passed, 2 deselected, cobertura de domain+application del 99,51 %). Frontend: format, lint, types, tests (7) y build. Harness: `feature_list.json` y trazabilidad AC→test. |
| `uv run pytest -q` (warnings) | 2 warnings que ya existían (los tests de `test_no_network`, que bloquean el socket a propósito) más el aviso de `pytest-asyncio`. Ninguno es de esta feature. |
| `grep` de `sae_arrivals_source.AC-n` en `tests/` | Los 22 AC aparecen citados (entre 1 y 10 tests cada uno). |
| Detector de pasos de `test_sae_fixtures.py` sobre `stop_508_peak` (script en el scratchpad) | 508: `[(520, 70), (1040, 93), (1180, 70)]`. 2070: 8 pasos. 0 errores en 150 respuestas. `offset_s` coincide con `captured_at − started_at` en todas, el intervalo es de 20 s constantes y `started_at` es 2026-11-02T19:42:23Z. |
| Comparación de fixtures con `progress/explore_sae_samples/` | Las 10 respuestas reales de E-01 son idénticas byte a byte. Las 2 derivadas solo difieren en lo que dice su `note`. |
| `git diff --stat develop...HEAD` | Hay cambios en `backend/src` (domain, adapters/sae, cli, background, config, main y app), `backend/tests`, `.env.example`, fixtures y `progress/` + `feature_list.json` (del orquestador). No se toca `docs/` ni `specs/`. |
| `grep` de `datetime.now` / `time.time` en el diff de `src/` | Ninguna aparición. |
| Datos personales en las fixtures (`grep` de correos) | No hay ninguno. El User-Agent con el contacto no se graba. |

### Lista de comprobación (`docs/verification.md` §4)

- **Contrato:** los AC se cumplen, incluidos los casos `SI … ENTONCES`. Las interfaces, errores
  (§6), logs (`sae.error` con `elapsed_ms`, `sae.unparsed_entry`, `sae.stats`) y la configuración
  (§7) coinciden con el design. Las desviaciones menores están en NB-6.
- **Arquitectura:** `domain/` (modelo, puerto y error) no tiene dependencias externas
  (lint-imports en verde). Los adaptadores dependen del puerto, y las clases concretas solo se
  conectan en `compose.py`, `main.py` y la CLI. El tiempo siempre pasa por `Clock`. La espera de
  la CLI y de `sae.stats` es un `sleep` inyectable.
- **Tests:** no usan red (`httpx.MockTransport` y sockets bloqueados), no hay `sleep` reales y el
  reloj es `FakeClock`. Los tests prueban los límites y fallarían si se rompe el comportamiento,
  salvo el caso de NB-2. Las fixtures tienen el origen documentado. `stop_508_peak` ocupa unos
  900 KB porque AC-19 (a) exige 15 min o más de una sesión real.
- **Privacidad y seguridad:** los logs solo llevan `stop_id`, motivo, tiempos y contadores. Nunca
  se registra el cuerpo. `ArrivalsUnavailableError` no pone identificadores en el mensaje (los
  guarda en atributos). La plantilla de URL se valida y el `stop_id` se escapa. No hay secretos
  nuevos.
- **Frontend:** no aplica.
- **Convenciones:** los nombres siguen el glosario (`destination`, `SaeHttpArrivalsSource`…). Los
  commits siguen Conventional Commits con el ámbito `sae_arrivals_source` y citan su `T-xx`. Las
  8 variables nuevas están documentadas en `.env.example`.
- **Alcance:** solo se toca código ajeno a la feature en dos sitios, y los dos se justifican por
  T-09 (registrar `sae.stats` en el ciclo de vida de la app y componer la fuente en `main.py`):
  - `adapters/inbound/http/app.py`: `create_app` acepta un `lifespan` opcional.
  - `tests/integration/test_main_composition.py`: fija `AVISABUS_SAE_REPLAY_DIR` en el
    subproceso.

  Las dos son mínimas y están explicadas en D-10 y D-13.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **NB-1. La caché negativa acumula la traza del error.**
  `backend/src/avisabus/adapters/outbound/sae/cache.py:67` (`raise entry.error`) y `:76` (cada
  llamante que espera la `Task` compartida vuelve a lanzar la misma instancia).
  - **Qué pasa:** relanzar la misma instancia de excepción le añade frames a su `__traceback__`.
    Lo medí: tras 200 aciertos de un error en caché, la traza tiene 402 frames. Crece con la carga
    durante `error_ttl` y, si alguien registra la traza, saldrá enorme.
  - **Por qué no bloquea:** design §3 pide "se relanza el mismo error" y los tests de AC-10 y AC-11
    comprueban la identidad del objeto, que se puede conservar.
  - **Arreglo propuesto:** usar `raise entry.error.with_traceback(None)`, también en la ruta de la
    `Task`. Conviene hacerlo antes o durante `stop_arrivals_api`, que es quien dará carga real a la
    caché.
- **NB-2. Un test no comprueba la configuración que dice comprobar (AC-20).**
  `backend/tests/unit/test_sae_compose.py:131-139` (`test_cache_limits_come_from_the_settings`).
  - **Qué pasa:** fija `sae_error_ttl_s=30` pero no avanza el reloj, así que también pasaría con el
    valor por defecto (5 s). Tampoco se comprueba que `sae_max_concurrency` llegue a la caché.
  - **Por qué no bloquea:** que el TTL sea configurable sí está probado en la propia caché
    (`test_error_ttl_is_configurable`).
  - **Arreglo propuesto:** avanzar el reloj unos 10 s entre llamadas.
- **NB-3. El detector de pasos de AC-19 (a) es más laxo que el AC.**
  `backend/tests/unit/test_sae_fixtures.py:50-67`.
  - **Qué pasa:** el detector da por llegado un autobús con ETA de 0–2 min, mientras que el AC dice
    "llega a 0". Además, no detecta el caso "desaparece la línea" (exige que la línea siga en la
    respuesta siguiente).
  - **Por qué no bloquea:** la sesión sí cumple el AC tal como está escrito: en el offset 1040 la
    93 pasa de 0 min a la siguiente llegada.
  - **Arreglo propuesto:** si se quiere que el test lo garantice, que `test_a_real_peak_session…`
    exija al menos un paso con ETA previa igual a 0.
- **NB-4. El comando de "Regeneración" del README de las fixtures no funciona tal cual.**
  `backend/tests/fixtures/sae_recordings/README.md:103-111`.
  - **Qué pasa:** apunta `--out` a `stop_508_peak`, que ya existe, y `sae record` se niega a
    sobrescribir (sale con código 2). Además usa `--duration 900` y una sola parada, que no se
    corresponde con la sesión actual (1500 s, paradas 508 y 2070).
  - **Arreglo propuesto:** indicar que hay que borrar o renombrar la carpeta antes, o usar otro
    `--out`.
- **NB-5. El nombre `stop_508_peak` ya no describe la sesión.** La sesión no es de hora punta.
  Está documentado en el README y la persona lo aceptó. Queda anotado por si se quiere renombrar
  junto con el valor por defecto de `AVISABUS_SAE_REPLAY_DIR`.
- **NB-6 (problema de spec, menor; sin CP-3).** La spec se ha seguido salvo en dos detalles
  menores, ninguno incompatible con el contrato. Conviene alinearla:
  - `build_arrivals_source` devuelve `CachedArrivalsSource` (D-12), mientras que design §2 dice
    `-> ArrivalsSource`. Es un subtipo compatible, y `main.py` lo necesita para `emit_stats`.
  - Las sesiones de E-01 llevan `interval_s: null` (D-08), y design §5 solo muestra el caso
    entero.

  El nombre `parser.py` de design §3 queda excluido, como pidió la persona.
- **NB-7. Hay clientes `httpx.AsyncClient()` sin cerrar en los tests.**
  `backend/tests/unit/test_sae_compose.py:134`, `:146` y `:180`. No abren sockets y solo dejan
  recursos sin liberar. Es menor.
- **NB-8. Con el valor por defecto `AVISABUS_SAE_CONTACT=""`, el User-Agent queda como
  `AvisaBus/0.1.0 (TFM; )`** (D-15). La persona lo da por resuelto. Solo se recuerda que hay que
  definir esa variable en cualquier despliegue `dev`/`prod`.

### Observaciones para features posteriores (no son de esta revisión)

- En `stop_508_peak`, la ETA de la 93 se queda en 0 desde el offset 780 hasta el 1020 (4 min).
  `alert_expiry` deberá tener en cuenta que un autobús puede seguir "en 0" durante varios minutos.
- `gtfs_mini` solo casa con la línea 98 de la parada 2070 de la sesión (ya anotado por el
  implementer). Afecta a `stop_arrivals_api`.
