# Revisión: driver_codes_cli
Ciclo: 1 · Fecha: 2026-11-09 · Agente: reviewer
Spec: specs/driver_codes_cli/ v1.0 (APPROVED) · Rama: `feat/driver_codes_cli` (HEAD b10e283), base `origin/feat/passenger_alert_ui-v1.1`

## Veredicto: CHANGES_REQUESTED

Un hallazgo bloqueante (F-01): si falla la escritura por algo distinto de un `IntegrityError` (p. ej.
`database is locked`), la traza de `create` imprime el *hash* y la etiqueta. Los seis AC tienen tests
válidos y la verificación completa está en verde.

## Matriz AC → evidencia

Todos los tests están en `backend/tests/`. `U` = `unit/test_driver_codes.py`, `C` =
`integration/test_cli_driver_codes.py`, `R` = `integration/test_driver_code_repository.py`.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | U `test_generator_*` (5), `test_create_stores_the_code_and_returns_the_plain_one`, `test_create_generates_another_code_when_it_already_exists` (activo y revocado), `test_create_retries_up_to_five_times`, `test_create_gives_up_after_the_retries_without_storing_anything`; C `test_create_prints_the_code_grouped_with_its_id_and_label`, `test_create_stores_the_generated_code`, `test_create_generates_another_code_when_the_code_exists`, `test_create_fails_cleanly_when_every_retry_collides`; R `test_add_rejects_*` | OK | Espacio completo 10^8, ceros a la izquierda, `secrets.randbelow` por defecto, una sola impresión agrupada. |
| AC-02 | U `test_create_accepts_labels_*`, `test_create_rejects_invalid_labels_without_storing_anything`; C `test_create_rejects_invalid_labels`, `test_create_requires_a_label`, `test_create_accepts_valid_labels` | OK | Límites 1 y 40, salto de línea, CR, tabulador, ESC y U+2028. La etiqueta solo de espacios no tiene test (N-02). |
| AC-03 | U `test_hash_*` (4), `test_create_never_stores_the_plain_code`, `test_repr_does_not_expose_the_plain_code_nor_the_hash`; C `test_the_hash_uses_the_configured_server_secret`, `test_the_plain_code_is_not_in_the_table`, `test_neither_the_code_nor_its_hash_reach_the_logs`; R `test_only_the_hash_is_written_to_the_table`, `test_collision_error_carries_no_stored_values` | OK | El literal del AC (código en claro) se cumple. F-01 afecta al *hash* y a la etiqueta, fuera del literal de este AC. |
| AC-04 | U `test_list_pairs_each_code_with_its_open_session_state`; C `test_list_shows_the_table_without_code_nor_hash`, `test_list_aligns_the_columns_with_long_labels`, `test_list_tells_when_a_code_has_an_open_shift`, `test_list_without_codes`, `test_list_as_json_has_the_same_information`, `test_list_as_json_without_codes`, `test_list_as_json_keeps_logs_out_of_stdout` | OK | Tabla y JSON con los cinco datos, sin código ni *hash*. |
| AC-05 | U `test_revoke_marks_the_code_and_reports_the_open_session`, `test_revoke_of_an_unknown_code_raises_and_keeps_the_id_in_an_attribute`, `test_revoke_of_a_revoked_code_changes_nothing`; C `test_revoke_marks_the_code_with_its_date`, `test_revoke_reports_the_open_shift`, `test_revoke_of_an_unknown_code_exits_with_one`, `test_revoke_of_a_revoked_code_is_harmless`, `test_revoke_of_a_revoked_code_logs_nothing_new`; R `test_revoke_*` | OK | Fecha guardada, salida 1 si no existe, salida 0 con aviso y fecha original intacta al repetir. |
| AC-06 | U `test_create_logs_only_the_code_id`, `test_create_logs_once_even_after_a_collision`, `test_revoke_logs_only_the_code_id`; C `test_create_and_revoke_log_the_code_id_only` | OK | Comparación exacta de campos; también con el `configure_logging` real. |

### Mutaciones (en una copia del backend en el scratchpad; el repositorio no se ha tocado)

54 mutantes sobre *hasher*, generador, casos de uso, repositorio, CLI, composición y modelo, contra
los tres ficheros de test: **52 detectados, 2 supervivientes**.

| Superviviente | Lectura |
|---|---|
| A15: consultar `has_open_session` después de revocar | Hueco de test (N-01). |
| M7: rechazar etiquetas solo de espacios | Hueco de test sobre una decisión local (N-02). |

Entre los detectados: dominio igual al del dispositivo, sin derivar clave, fuente no criptográfica,
espacio de 10^7, guardar el código en claro, registrar código/etiqueta/*hash*, imprimir el código dos
veces, *hash* en `list` y `--json`, quitar `from None`, sobrescribir la fecha al re-revocar, logs a
stdout con `--json`.

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` con el puerto 4173 libre (`lsof` sin procesos a la escucha): **exit 0, todo en verde**.

| Paso | Resultado |
|---|---|
| backend format / lint | OK |
| backend `mypy` | OK, 129 ficheros |
| backend `lint-imports` | OK, 2 contratos, 0 rotos |
| backend `pytest` (sockets desactivados) | 1409 passed, 6 deselected |
| frontend format / lint / types | OK |
| frontend tests | 563 passed, 2 skipped |
| frontend build + bundle | OK, 5 passed |
| frontend e2e + a11y | 126 passed |
| `feature_list.json` y trazabilidad AC→test | OK |

Pruebas adicionales con el binario real y BD en el scratchpad:

- `AVISABUS_ENV=prod` y otra conexión con `BEGIN IMMEDIATE` durante `create`: salida 1 y traza con `[parameters: ('dc-pb6dfv', '4cafc6b0…', 'EtiquetaSensible', …)]` (F-01).
- La misma prueba con `hide_parameters=True` en la copia: `[SQL parameters hidden due to hide_parameters=True]`, sin *hash* ni etiqueta; los 84 tests de la feature siguen pasando.
- `create` con `AVISABUS_LOG_LEVEL=DEBUG`: una línea de log, sin código, *hash* ni etiqueta.

## Hallazgos

### Bloqueantes

**F-01 — Una excepción de BD distinta de `IntegrityError` imprime el *hash* y la etiqueta.**
`backend/src/avisabus/adapters/outbound/persistence/sqlite_driver_codes.py:44` solo captura
`IntegrityError`, y `backend/src/avisabus/adapters/outbound/persistence/db.py:34` crea el motor sin
`hide_parameters`. Un `OperationalError` en el `INSERT` (BD bloqueada más de los 5 s de
`busy_timeout`, disco lleno, BD de solo lectura) sube sin capturar hasta Typer, que imprime por stderr
el mensaje de SQLAlchemy con los parámetros. Reproducido con el binario real (ver arriba). La API
escribe en la misma BD, así que el bloqueo es posible en producción, y el stderr de un proceso suele
acabar en un registro (journal, cron).

- **Incumple:** `docs/conventions.md` §3 "Excepciones en logs" (ninguna excepción no controlada con su mensaje) y el criterio de esta revisión (ningún log, `repr` o traza con el código o el *hash*). El literal de AC-03 solo cubre el código en claro, que no aparece: Typer 0.27.3 tiene `pretty_exceptions_show_locals=False` y `cli/main.py:12` no lo cambia.
- **Corrección propuesta:** `hide_parameters=True` en `create_engine` (`db.py` está en los ficheros de T-02; validado en la copia). Alternativa equivalente: capturar `SQLAlchemyError` en `add` y relanzar sin detalles.
- **Test necesario:** un `OperationalError` real o simulado en `add`/`create`, comprobando que el *hash* y la etiqueta no aparecen en el error ni en la salida. Hoy `test_collision_error_carries_no_stored_values` solo cubre `IntegrityError`.

### No bloqueantes

- **N-01** — `backend/src/avisabus/application/driver_codes.py:113-114`: el orden (consultar el turno antes de revocar) es el correcto, pero ningún test lo fija (mutante A15). Importa cuando exista el *reaper*: consultar después podría dar `False` si ya ha cerrado la sesión. Basta un `has_open_session` falso que dependa del estado del repositorio.
- **N-02** — `backend/src/avisabus/domain/models/driver.py:30`: la etiqueta solo de espacios se acepta sin test que lo fije (mutante M7). Si se mantiene, conviene un test.
- **N-03** — `backend/src/avisabus/adapters/inbound/cli/driver_codes.py:113-117`: el aviso va a stderr, mientras que los `AVISO:` existentes de `cli/gtfs.py:133-140` van a stdout. La spec no fija el canal y stderr es defendible; se anota por coherencia.
- **N-04** — `backend/src/avisabus/application/driver_codes.py:108-117`: entre `get` y `revoke` no hay atomicidad. Dos `revoke` simultáneos conservan la primera fecha, pero ambos informan de "revocado" y registran `driver_code.revoked`. Sin impacto real en una CLI de administración.
- **N-05** — `progress/current.md` dice `implementing` y `feature_list.json` dice `in_review`. Corresponde al orquestador.
- **N-06 (imprecisión de spec, no requiere CP-3)** — `specs/driver_codes_cli/design.md` §2 dice "IntegrityError de hash → el caso de uso reintenta", y T-01 no lista `domain/errors.py`. La implementación es la única compatible con la capa de aplicación sin SQLAlchemy. Conviene ajustarlo en la próxima versión de la spec.

## Decisiones locales de `progress/impl_driver_codes_cli.md`

`design.md` no tiene sección de decisiones locales permitidas (`driver_session` sí, §7), así que cada una se juzga contra los AC y el design.

| Decisión | Dictamen | Motivo |
|---|---|---|
| Revocar uno ya revocado: excepción, aviso por stderr, salida 0, sin log | Cabe, sin CP-3 | AC-05 fija salida 0 y aviso. La firma del design no cambia y no permite distinguir el caso de otra forma. El canal no está fijado (N-03). |
| Campos de `list --json` | Cabe, sin CP-3 | AC-04 pide "la misma información" y no fija nombres. Los cinco campos corresponden a las cinco columnas y `status` usa los valores del AC. |
| Logs a stderr con `--json` | Cabe, sin CP-3 | Necesario para que stdout sea JSON válido (`configure_logging` escribe en stdout). Es local a `cli/driver_codes.py:50-54` y no toca `logging.py`. |
| Reintentos agotados: 1 + 5 intentos, salida 1, sin guardar | Cabe, sin CP-3 | El design fija "hasta 5 reintentos"; lo que ocurre después solo admite fallar sin guardar. La salida 1 coincide con el otro error de la CLI. |
| Etiqueta inválida con `str.isprintable` | Cabe, sin CP-3 | Desarrolla "imprimibles, sin saltos de línea". Rechazar ESC y separadores Unicode protege la tabla de `list`. |
| Etiqueta solo de espacios aceptada | Cabe, sin CP-3 | Cumple el literal de AC-02. Rechazarla sería un cambio de spec, a decidir por la persona si lo quiere (N-02). |
| Excepciones nuevas en `domain/errors.py` | Cabe, sin CP-3 | `docs/conventions.md` §3 las ubica ahí, y está por encima de la spec. `driver_session` T-01 sí lista ese fichero. Ver N-06. |

Ninguna requiere CP-3.

## Revocar con un turno abierto y encaje con `driver_session`

- `_no_open_session` (`backend/src/avisabus/adapters/inbound/cli/container.py:37-39`) se inyecta en `ListDriverCodes` y `RevokeDriverCode`, como pide design §2. El caso con turno abierto se prueba con un `has_open_session` inyectado.
- `driver_session` T-01 puede sustituirlo en `cli/container.py` (fichero listado en esa tarea) con `by_code(code_id) is not None`; `code_id` es UNIQUE en `driver_session`, y AC-14 amplía `test_cli_driver_codes.py`.
- `find_by_hash` devuelve también los códigos revocados y `DriverCode.revoked` permite a `driver_session.AC-02` responder igual en ambos casos. El *hasher* usa el mismo secreto que tendrá la API.
- Al repetir `revoke` no se consulta el turno, así que dentro de la ventana del *reaper* el aviso no lo menciona. AC-05 solo exige el aviso y el primer `revoke` ya informó.
- A tener en cuenta en `driver_session`: "se cerrará en menos de 1 minuto" (design §4) depende de que `AVISABUS_DRIVER_REAPER_INTERVAL_S` siga en 60 y de que la API esté en marcha.

## Lista de comprobación (`docs/verification.md` §4)

| Bloque | Resultado |
|---|---|
| Contrato | Interfaces, tabla y CLI coinciden con el design, salvo la imprecisión N-06. |
| Arquitectura | `domain/` puro (`lint-imports` OK), sin `datetime.now()` fuera de `SystemClock`, puertos respetados; la composición sigue el patrón de las demás CLI. |
| Tests | Sin red ni sleeps; `FakeClock`; 52 de 54 mutantes detectados. |
| Privacidad y seguridad | Solo *hash* HMAC con separación de dominio; `secrets.randbelow` en producción; `repr` sin código ni *hash*; código impreso una sola vez. **Falla F-01.** |
| Frontend | No aplica: sin cambios en `frontend/`. |
| Convenciones | Glosario y Conventional Commits OK. `.env.example` sin cambios: no hay variables nuevas. |
| Alcance | Solo ficheros de T-01 a T-03, `domain/errors.py` y progreso. La carpeta `qr/` sin versionar se ha ignorado. |
