# Implementación: driver_codes_cli
Spec: specs/driver_codes_cli/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-09

## Tareas
- [x] T-01 `DriverCode`, puertos, `HmacDriverCodeHasher`, `SecretsCodeGenerator` y casos de uso (AC-01, AC-03, AC-06) (commit 6eaec64)
- [x] T-02 Tabla `driver_code` y `SqliteDriverCodeRepository` (AC-01, AC-03, AC-05) (commit 681d227)
- [x] T-03 Comandos `driver-codes create/list/revoke` y composición en la CLI (AC-01 – AC-06) (commit ad0914a)
- [x] T-04 Verificación completa: `CI=1 ./init.sh verify --e2e` en verde (commit de este fichero)

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
