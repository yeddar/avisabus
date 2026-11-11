# Implementación: driver_codes_cli
Spec: specs/driver_codes_cli/ (v1.1, APPROVED) · Ciclo de revisión: 0 de la v1.1 (la v1.0 terminó en el ciclo 2) · Agente: implementer · Fecha: 2026-11-11

## v1.1 (ciclo de revisión 0 de la v1.1)

Spec: specs/driver_codes_cli/ v1.1 (APPROVED, PR #60) · Rama: `feat/driver_codes_cli-v1.1` · Agente: implementer · Fecha: 2026-11-11

### Tareas
- [x] T-05 `pretty_exceptions_show_locals=False` explícito en `cli/main.py` y tests que lo fijan (AC-03) (commit 10eb266)
- [x] T-04 Verificación completa: `CI=1 ./init.sh verify --e2e` en verde (commit de este fichero)

### Tests nuevos (`backend/tests/integration/test_cli_driver_codes.py`, citan `driver_codes_cli.AC-03`)
- `test_the_error_trace_does_not_show_the_code_kept_in_a_local_variable`: provoca un
  `OperationalError` real (se borra la tabla tras componer, como en F-01) con el código
  `48210937` en la variable local `plain_code` de `CreateDriverCode.execute`. Antes comprueba que
  esa variable local existe en la traza, para que el test no pase sin ejercitar nada. Después
  renderiza la traza con el *hook* que instala Typer y comprueba que no aparecen el código (junto
  o agrupado), su *hash* ni la etiqueta.
- `test_the_cli_sets_show_locals_off_explicitly`: el `False` está escrito en `cli/main.py` y
  `app.pretty_exceptions_show_locals is False`.

### Comprobación TDD y mutantes
- En rojo antes del cambio: `test_the_cli_sets_show_locals_off_explicitly` fallaba (no había
  ajuste explícito). El test de comportamiento pasaba, porque el valor por defecto de Typer 0.27.3
  ya es `False`: es lo que la v1.1 pide dejar de dar por supuesto.
- Mutante `pretty_exceptions_show_locals=True` en `cli/main.py`: falla el test de comportamiento.
  La traza muestra `plain_code = '48210937'`. Mutante sin el argumento: falla el test del ajuste
  explícito. Ambos revertidos.

### Decisiones locales (v1.1)
- **Invocar `app(...)` en lugar de `CliRunner` en el test de la traza:** `CliRunner.invoke` llama
  al comando de Click sin pasar por `Typer.__call__`, que es quien adjunta a la excepción la
  configuración `pretty_exceptions_*`. Sin ella, el *hook* de Typer cae a la traza estándar de
  Python, que nunca muestra variables locales, y el mutante `True` sobrevivía (lo comprobé con
  una primera versión del test). El test llama a `app([...], prog_name="avisabus")` como el binario
  real y restaura con `monkeypatch` el `sys.excepthook` que Typer instala. También anula
  `TYPER_STANDARD_TRACEBACK` y `_TYPER_STANDARD_TRACEBACK`.
- **Test que lee el fuente de `cli/main.py`:** el comportamiento no permite distinguir un `False`
  explícito del valor por defecto, y AC-03 v1.1 pide que sea explícito "con un test que lo
  comprueba". Ese test es el único modo de fijarlo. Es un test de configuración, no de
  comportamiento; el de la traza cubre el comportamiento.
- **Dependencia de `rich`:** el test de la traza ejercita la traza de `rich`, que se usa porque
  `rich` está instalado (dependencia de Typer). Sin `rich`, Typer usa la traza estándar, que no
  muestra variables locales, y el test seguiría pasando.

### Bloqueos (v1.1)

Ninguno.

### Verificación (v1.1)

`CI=1 ./init.sh verify --e2e` (2026-11-11, tras el commit 10eb266, con el puerto 4173 libre):
**exit 0, todo en verde**.

| Paso | Resultado |
|---|---|
| backend: format / lint | OK |
| backend: types (`mypy`) | OK — no issues found in 150 source files |
| backend: architecture (`lint-imports`) | OK — 2 contracts kept, 0 broken |
| backend: tests | OK — 1915 passed, 12 deselected; cobertura `domain` + `application` 99,66 % |
| frontend: format / lint / types | OK |
| frontend: tests | OK — 660 passed, 2 skipped |
| frontend: build + bundle | OK — 5 passed |
| frontend: e2e + a11y | OK — 132 passed |
| harness: `feature_list.json` y trazabilidad AC→test | OK |

Comando de la tarea: `cd backend && uv run pytest tests/integration/test_cli_driver_codes.py
--no-cov` → 36 passed.

---

Histórico: implementación de la v1.0.

## Tareas
- [x] T-01 `DriverCode`, puertos, `HmacDriverCodeHasher`, `SecretsCodeGenerator` y casos de uso (AC-01, AC-03, AC-06) (commit 6eaec64)
- [x] T-02 Tabla `driver_code` y `SqliteDriverCodeRepository` (AC-01, AC-03, AC-05) (commit 681d227)
- [x] T-03 Comandos `driver-codes create/list/revoke` y composición en la CLI (AC-01 – AC-06) (commit ad0914a)
- [x] T-04 Verificación completa: `CI=1 ./init.sh verify --e2e` en verde (commit 1f7e935)

### Ciclo 2 (correcciones de la revisión)
- [x] F-01 (bloqueante): un error de BD distinto de `IntegrityError` mostraba el *hash* y la etiqueta en la traza; `hide_parameters=True` en `create_engine` (commit 412e42d)
- [x] N-01 y N-02 (mutantes A15 y M7): tests que fijan que el turno se consulta antes de revocar y que se acepta una etiqueta solo de espacios (commit 3dbc8d9)
- [x] Verificación completa: `CI=1 ./init.sh verify --e2e` en verde (commit de este fichero)

## Decisiones locales

`design.md` no marca ninguna "decisión local permitida". Estas son las que hacen falta para
implementar el contrato sin cambiarlo. Las cuatro primeras cubren detalles que la spec no fija, y
la persona o el reviewer pueden pedir otra cosa sin rehacer nada más.

- **Revocar uno ya revocado (AC-05):** la firma de `RevokeDriverCode.execute` devuelve
  `tuple[DriverCode, bool]`, que no permite distinguir "recién revocado" de "ya lo estaba". El caso
  de uso lanza `DriverCodeAlreadyRevokedError` (con `code_id` y `revoked_at`) y la CLI imprime el
  aviso por stderr y sale con 0. No cambia la fecha original ni registra `driver_code.revoked`.
- **JSON de `list --json` (AC-04):** el AC no fija los nombres. Es un array de objetos con
  `code_id`, `label`, `created_at` (ISO-8601 UTC), `status` (`activo`/`revocado`) y
  `has_open_session` (booleano); los mismos datos que la tabla.
- **Colisión tras agotar los reintentos (AC-01, design §2):** son 1 intento + 5 reintentos. Si
  todos colisionan, se relanza `DriverCodeCollisionError`, la CLI imprime un error y sale con 1, sin
  guardar nada. Con 10^8 códigos no debería ocurrir en la práctica.
- **Salidas sin datos y fechas:** sin códigos, `list` imprime "No hay códigos de conductor." y
  `list --json` imprime `[]` (mismo criterio que `occupancy override --list`). `CREADO` va en UTC con
  el formato del design (conventions §3: `Europe/Madrid` solo para interpretar horarios GTFS).
- **Traducción de `IntegrityError` (design §2):** el dominio y la aplicación no conocen SQLAlchemy.
  El repositorio traduce cualquier `IntegrityError` a `DriverCodeCollisionError` con `from None`,
  porque el mensaje de SQLAlchemy incluye los parámetros de la sentencia (hash y etiqueta). La
  colisión de `code_id` se trata igual: se genera otro código y otro identificador.
- **`find_by_hash` no se usa al crear:** la restricción `UNIQUE` más el reintento cubren activos y
  revocados sin condición de carrera. El método queda en el puerto, como pide el design, para
  `driver_session`.
- **Etiqueta (AC-02):** la regla está en el dominio (`is_valid_driver_code_label`, con
  `str.isprintable`) y la aplica `CreateDriverCode`, antes de generar o guardar nada. Rechaza
  también tabuladores, secuencias de escape y separadores Unicode. Una etiqueta solo de espacios se
  acepta: son caracteres imprimibles y el AC no pide más (lectura literal).
- **`--label` ausente:** la opción es opcional para Typer para dar el mismo mensaje en castellano
  (design §4) en lugar del de Click en inglés. Sale con 2, sin abrir la BD.
- **Logs y `list --json` (AC-04):** `configure_logging` escribe en stdout y, en desarrollo sin
  secreto, `build_cli_container` registra `security.dev_stop_token_secret`, lo que dejaría stdout sin
  ser JSON válido. Con `--json` el comando redirige a stderr los handlers que escriben en stdout, en
  `cli/driver_codes.py`, sin tocar `logging.py` (compartido).
- **Privacidad en `repr`:** `plain_code` y `code_hash` llevan `field(repr=False)`, para que no
  lleguen a un log por accidente. La interfaz del design no cambia.
- **Tabla `driver_code`:** `created_at` queda sin `NOT NULL`, como dice literalmente design §3. El
  repositorio siempre lo escribe. A igual `created_at`, `list_all` desempata por `code_id`.
- **Ficheros fuera de la lista de T-01:** `domain/errors.py` gana las cuatro excepciones nuevas
  (conventions §3 las ubica ahí).
- **`has_open_session`:** `_no_open_session` en `cli/container.py` devuelve `False` hasta que
  `driver_session` T-01 lo sustituya (design §2).

## Bloqueos

Ninguno.

## Verificación

### Ciclo 2 (2026-11-09, tras el commit 3dbc8d9, con el puerto 4173 libre)

`CI=1 ./init.sh verify --e2e`: **todo en verde** (exit 0).

| Paso | Resultado |
|---|---|
| backend: format / lint | OK |
| backend: types (`mypy`) | OK — no issues found in 129 source files |
| backend: architecture (`lint-imports`) | OK — 2 contracts kept, 0 broken |
| backend: tests | OK — 1413 passed, 6 deselected; cobertura `domain` + `application` 99,56 % |
| frontend: format / lint / types | OK |
| frontend: tests | OK — 563 passed, 2 skipped |
| frontend: build + bundle | OK — 5 passed |
| frontend: e2e + a11y | OK — 126 passed |
| harness: `feature_list.json` y trazabilidad AC→test | OK |

**F-01.** `hide_parameters=True` afecta a todos los repositorios que usan el motor. Ningún test ni
módulo lee los parámetros SQL de un error: `tests/integration/test_cli_gtfs.py:147` solo busca el
nombre del tipo `IntegrityError`, y la suite completa pasa. Los mensajes conservan el error y la
sentencia; solo desaparecen los valores.

Tests nuevos, que citan `driver_codes_cli.AC-03`: provocan un `OperationalError` real con el motor
real, porque borran la tabla antes del `INSERT` (sin esperar el `busy_timeout`).
- `test_driver_code_repository.py::test_a_failed_write_exposes_neither_the_hash_nor_the_label`
- `test_cli_driver_codes.py::test_a_failed_write_shows_neither_the_hash_nor_the_label`

Antes de la corrección fallaban los dos (`2 failed`) porque el *hash* aparecía en la traza; después
pasan (`2 passed`).

Prueba con el binario real, `AVISABUS_ENV=prod` y otra conexión con `BEGIN IMMEDIATE`: exit 1,
`database is locked`, `[SQL parameters hidden due to hide_parameters=True]`, y ninguna aparición de
la etiqueta ni de un *hash* de 64 caracteres.

**N-01 y N-02.** Con los tests nuevos, los mutantes A15 (consultar el turno tras revocar) y M7
(rechazar etiquetas solo de espacios) hacen fallar un test cada uno. N-03 y N-04 no se han tocado
por no bloquear; N-05 y N-06 no corresponden al implementer.

### Ciclo 0

`CI=1 ./init.sh verify --e2e` (2026-11-09, rama `feat/driver_codes_cli`, tras el commit ad0914a,
con el puerto 4173 libre): **todo en verde**.

| Paso | Resultado |
|---|---|
| backend: format / lint | OK |
| backend: types (`mypy`) | OK — no issues found in 129 source files |
| backend: architecture (`lint-imports`) | OK — 2 contracts kept, 0 broken |
| backend: tests (`pytest`, sockets desactivados) | OK — 1409 passed, 6 deselected; cobertura `domain` + `application` 99,56 % |
| frontend: format / lint / types | OK (sin cambios en frontend) |
| frontend: tests | OK — 563 passed, 2 skipped |
| frontend: build + bundle | OK — 5 passed |
| frontend: e2e + a11y | OK — 126 passed |
| harness: `feature_list.json` | OK |
| harness: trazabilidad AC→test | OK |

Comandos de tarea (con `--no-cov`, porque ejecutados solos no alcanzan la cobertura global):
- T-01: `uv run pytest tests/unit/test_driver_codes.py` → 39 passed.
- T-02: `uv run pytest tests/integration/test_driver_code_repository.py` → 15 passed.
- T-03: `uv run pytest tests/integration/test_cli_driver_codes.py` → 30 passed.

Prueba manual con el binario real y la BD en el scratchpad, fuera de `data/`: `create` (el código
sale una vez; el log JSON solo lleva `code_id`), `create` sin etiqueta y con etiqueta vacía (exit
2), `list`, `list --json` sin secreto y con stderr descartado (JSON válido), `revoke` (0), repetir
`revoke` (0 con aviso) y `revoke` de un id inexistente (1). En la tabla, `code_hash` mide 64
caracteres y no hay ninguna columna con el código.

Comprobación de que los tests detectan fallos, con mutaciones temporales ya revertidas: dejar los
logs en stdout con `--json`, registrar el código, quitar la separación de dominio, imprimir el
código dos veces, no reintentar y registrar la etiqueta. Todas hacen fallar al menos un test.
