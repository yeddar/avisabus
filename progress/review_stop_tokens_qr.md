# Revisión: stop_tokens_qr
Ciclo: 1 · Fecha: 2026-11-01 · Agente: reviewer · Spec: specs/stop_tokens_qr/ v1.1 (APPROVED) · Rama: `feat/stop_tokens_qr` (12 commits sobre `develop`, `ecbe6f2..e35011a`)

## Veredicto: APPROVED

Ningún hallazgo bloqueante. Los 13 AC tienen tests que comprueban de verdad el comportamiento, y
`./init.sh verify` pasa. Hay tres hallazgos no bloqueantes y tres observaciones sobre la spec, sin
CP-3.

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `tests/unit/test_hmac_stop_token.py::test_token_matches_the_fixed_test_vector`, `::test_token_is_deterministic_22_chars_base64url_without_padding`, `::test_token_depends_on_stop_and_secret` | OK | He recalculado el vector por mi cuenta con `hmac`/`hashlib` fuera del proyecto, y da `83Rg_QTPgamZSDGo9T168g`, que coincide con el fijado en el test. Se usan el secreto y el `stop_id` de design §4. |
| AC-02 | `test_hmac_stop_token.py::test_correct_pair_is_accepted`, `::test_invalid_tokens_are_rejected_without_raising` (12 casos) | OK | Cubre otra parada, token truncado, demasiado largo, vacío, `=`, `+`, no ASCII, surrogate suelto, espacio, mayúsculas/minúsculas cambiadas y `stop_id` que no se puede codificar. Los tests comprueban que `verify` devuelve `False` (`is False`) sin lanzar. |
| AC-03 | `test_hmac_stop_token.py::test_tokens_are_compared_with_compare_digest` (espía), `::test_verification_result_comes_from_compare_digest` (doble que siempre responde `False`) | OK + revisión | Revisión de `hmac_stop_token.py:27-35`. El único filtro previo es la forma del token (`[A-Za-z0-9_-]{22}`), que no depende del secreto, y la decisión final la toma `hmac.compare_digest`. El segundo test fallaría si se comparase con `==`. |
| AC-04 | `tests/unit/test_settings_stop_token.py::test_prod_refuses_to_start_without_a_valid_secret` (sin secreto, vacío, 31 bytes, `"ñ"*15` = 30 bytes), `::test_configuration_error_does_not_reveal_the_secret`, `::test_prod_accepts_a_secret_of_at_least_32_bytes` | OK | Lo he comprobado con la CLI real: con `AVISABUS_ENV=prod` y un secreto corto, `avisabus qr generate` sale con 1 y `ConfigurationError` explícito, no crea nada y el secreto (un canario) no aparece en la salida. La API construye `Settings()` al importar `main.py:10`, así que tampoco arranca. |
| AC-05 | `test_settings_stop_token.py::test_dev_and_test_without_secret_use_the_dev_secret_and_warn` (dev/test × sin secreto/vacío), `::test_dev_with_a_configured_secret_uses_it_without_warning` | OK | Usa el secreto fijo de design §4 y emite el evento `security.dev_stop_token_secret` a nivel `warning`. Ver H-01 (formato del log en ejecución real). |
| AC-06 | `tests/unit/test_stop_url.py` (2 tests, 6 casos) | OK | Base sin barra final, con una o dos barras finales, y base con ruta. |
| AC-07 | `tests/integration/test_cli_qr.py::test_single_stop_writes_an_svg_with_the_url_and_the_label`, `::test_output_directory_defaults_to_qr`; `tests/integration/test_segno_renderer.py::test_svg_encodes_the_url`, `::test_svg_label_shows_name_and_stop_code_below_the_qr`, `::test_svg_label_text_is_escaped`, `::test_svg_long_names_are_wrapped_inside_the_label`, `::test_svg_uses_segno_at_scale_10_on_a_white_background`; `tests/unit/test_generate_stop_qr_codes.py::test_generates_a_qr_per_requested_stop_with_signed_url_and_label` | OK | El SVG se rasteriza y se decodifica con zxing-cpp. La URL coincide con la firmada con el secreto del test. El nombre GTFS y `Parada 508` están debajo del QR (coordenadas `y` comprobadas). |
| AC-08 | `test_cli_qr.py::test_several_stops_write_one_file_each_and_an_index`, `::test_index_is_utf8_with_the_documented_header`, `::test_all_writes_every_stop_of_the_active_feed` (178 paradas comparadas con `stops.txt`); `test_generate_stop_qr_codes.py::test_all_stops_of_the_active_feed_when_no_stop_is_given`, `::test_a_stop_given_twice_is_generated_once` | OK | Comprueba que `index.csv` tiene la cabecera `stop_id,name,url,file`, está en UTF-8 y tiene el contenido completo. |
| AC-09 | `test_cli_qr.py::test_png_format_writes_a_600_px_qr_with_the_label`; `test_segno_renderer.py::test_png_qr_is_at_least_600_px_and_decodes_to_the_url`, `::test_png_has_a_label_band_with_text`, `::test_png_long_name_text_stays_inside_the_image`; `test_generate_stop_qr_codes.py::test_png_format_is_passed_to_the_renderer_and_names_the_file` | OK | La zona del QR mide ≥ 600 px y se decodifica. Debajo hay una banda con texto que cambia con la etiqueta. |
| AC-10 | `test_cli_qr.py::test_missing_stop_is_reported_others_are_generated_and_exit_code_is_2`, `::test_every_missing_stop_is_reported`; `test_generate_stop_qr_codes.py::test_missing_stops_are_reported_and_the_others_still_generated` | OK | Sale con 2, escribe `ERROR: parada 9999 no existe` por stderr y genera las demás paradas. |
| AC-11 | `test_cli_qr.py::test_without_a_feed_exits_1_and_writes_nothing` (`--stop` y `--all`); `test_generate_stop_qr_codes.py::test_without_an_active_feed_it_raises_and_renders_nothing`, `::test_no_active_feed_error_is_a_domain_error` | OK | Sale con 1, muestra un mensaje y no crea el directorio de salida. |
| AC-12 | `test_segno_renderer.py::test_segno_is_called_with_level_m_and_no_micro_qr` (espía de `segno.make`), `::test_error_correction_level_is_m` (svg/png, decodificado), `::test_svg_has_a_quiet_zone_of_4_modules`, `::test_png_has_a_quiet_zone_of_4_modules` | OK | **Nivel M exacto.** El espía exige `boost_error=False`. He comprobado que la URL del segundo test la subiría segno a **Q** con su valor por defecto (`segno.make(c, error="m").error == "Q"`; con `boost_error=False` da `"M"`), así que el test distingue de verdad. |
| AC-13 | `test_segno_renderer.py::test_bundled_font_has_a_glyph_for_every_character_of_gtfs_mini_stop_names` (`cmap` con fontTools, y además exige que `gtfs_mini` contenga `à è é í ò ó ñ ç · À Á` para no pasar en vacío), `::test_dejavu_license_is_shipped_next_to_the_font`, `::test_png_label_is_always_drawn_with_the_bundled_font` (espía `truetype` y prohíbe `load_default`), `::test_png_label_draws_distinct_accented_letters` | OK + revisión | Ver "Revisión de AC-13". |

### Revisión de AC-13 (fuente, licencia y procedencia)

- **Ficheros:** `backend/src/avisabus/adapters/outbound/qr/fonts/DejaVuSans.ttf` (757 076 B) y
  `LICENSE-DejaVu.txt` (8 816 B), en las rutas de design §5. Se cargan con `importlib.resources`
  (`segno_renderer.py:121-127`), sin búsqueda en el sistema ni `load_default`.
- **SHA-256 (comprobados sin red):**
  - `DejaVuSans.ttf` = `7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954`. Coincide
    con lo anotado en `impl` y es idéntico a una copia **independiente** que ya había en la máquina:
    el paquete conda-forge `font-ttf-dejavu-sans-mono-2.37`, cuya receta descarga la release
    oficial `https://sourceforge.net/projects/dejavu/files/dejavu/2.37/dejavu-sans-ttf-2.37.zip`.
    Coincide también con la copia que trae dompdf.
  - `LICENSE-DejaVu.txt` = `7a083b13…e5958a93`. Idéntico al `info/licenses/LICENSE` de ese mismo
    paquete conda-forge.
  - El SHA-256 del tarball anotado (`fa9ca4d1…46e17d7`) coincide con el fichero que el implementer
    dejó en el scratchpad de la sesión. **No lo he podido contrastar con la web oficial**: no he
    usado la red. Aun así, la procedencia de los dos ficheros incluidos queda probada por la
    coincidencia byte a byte con la release oficial que empaqueta conda-forge.
- **Metadatos de la fuente:** `name` id 5 = `Version 2.37`; copyright de Bitstream y de Tavmjong
  Bah, "DejaVu changes are in public domain".
- **Licencia:** es la de Bitstream Vera y Arev. Permite redistribuir y empaquetar la fuente sin
  modificarla, siempre que se acompañe del aviso. Va junto al `.ttf`. Correcta.
- **Empaquetado:** he generado la rueda y el sdist en un directorio temporal
  (`uv build --offline`). Los dos contienen `avisabus/adapters/outbound/qr/fonts/DejaVuSans.ttf` y
  `LICENSE-DejaVu.txt`. `pyproject.toml` los declara en `artifacts`.

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `./init.sh verify` (raíz, rama `feat/stop_tokens_qr`) | **Exit 0**, "verify: todo en verde" |
| ↳ backend: `ruff format --check` / `ruff check` / `mypy` | OK / All checks passed / no issues in 56 files |
| ↳ backend: `lint-imports` | 2 contracts kept, 0 broken |
| ↳ backend: `pytest` (sockets desactivados) | 290 passed, 2 deselected (`slow`); cobertura `domain`+`application` 99,36 % (`generate_stop_qr_codes.py`, `stop_url.py`, `ports/qr.py`, `ports/stop_token.py` al 100 %) |
| ↳ frontend: format / lint / types / tests / build | OK (sin cambios en frontend) |
| ↳ harness: `feature_list.json` / trazabilidad AC→test | OK / OK (AC-01…AC-13 citados) |
| Vector AC-01 recalculado con `python3 -I` | `83Rg_QTPgamZSDGo9T168g` = el del test |
| `segno.make(...)` con y sin `boost_error` | por defecto Q, con `boost_error=False` M (el test de AC-12 distingue) |
| `shasum -a 256` de la fuente y la licencia frente a la copia de conda-forge | idénticos |
| `uv build --wheel --sdist --offline --out-dir <scratchpad>` | fuente y licencia en la rueda y en el sdist |
| CLI real, `AVISABUS_ENV=prod`, secreto corto (cwd y BD en el scratchpad) | exit 1, `ConfigurationError` explícito, secreto ausente de la salida, sin ficheros |
| CLI real, `AVISABUS_ENV=dev`, sin secreto, BD vacía (scratchpad) | exit 1 "No hay ningún feed importado", advertencia emitida (ver H-01) |
| `git status --ignored` y `ls data/` tras la revisión | Sin ficheros nuevos en el repositorio ni en `data/` (solo la entrada de `feature_list.json` que ya estaba sin confirmar, del orquestador) |

## Comprobación de `docs/verification.md` §4

- **Contrato:** las interfaces coinciden con design §3: `StopTokenSigner`, `QrLabel`/`QrRequest`/
  `QrRenderer`, el comando y el resultado, `GenerateStopQrCodes(network, signer, renderer,
  public_base_url)`, `NoActiveFeedError` en `domain/errors.py`, la sinopsis de la CLI, los códigos
  0/1/2, el mensaje `ERROR: parada X no existe` y `ConfigurationError` al construir `Settings`.
  La firma es la de design §3.
- **Arquitectura:** `domain/` no tiene I/O ni dependencias externas (lint-imports). La aplicación
  solo usa puertos. Las clases concretas solo se crean en el punto de composición de la CLI
  (`cli/container.py`). No hay `datetime.now()`.
- **Tests:** sin red ni sleeps. Cada CLI usa una BD temporal importada de `gtfs_mini`. Los tests no
  son tautológicos: hay espías que fallarían con `==`, sin `boost_error=False` o con
  `load_default`, y un test de glifos que fallaba con la v1.0. Las fixtures son las ya
  documentadas de `gtfs_mini`.
- **Privacidad y seguridad:** no se registran identificadores. El único log nuevo es
  `security.dev_stop_token_secret` con `env`. El secreto es `SecretStr` (enmascarado en `repr`,
  con test) y no aparece en los mensajes de `ConfigurationError` (con test, y comprobado con la
  CLI real). `HmacStopTokenSigner` no lo expone. `verify` no lanza con ninguna entrada `str`. El
  secreto solo llega por configuración y está documentado en `.env.example`. RNF-06 no aplica.
- **Frontend / i18n / accesibilidad:** no aplica (sin cambios en frontend). El texto impreso
  `Parada {id}` es idéntico en los dos idiomas, por decisión de la spec. Los nombres de parada
  van tal como vienen en el GTFS.
- **Convenciones:** los nombres siguen el glosario (`Stop`, `stop_id`). Los commits son
  Conventional Commits, con ámbito `stop_tokens_qr` y cita de la tarea. Los de progreso usan el
  ámbito `progress`, como en las features anteriores.
- **Alcance:** fuera de los módulos de la spec solo cambian:
  - `cli/container.py` y `cli/main.py`: solo se añade el cableado;
  - `config.py`: lo pide T-01;
  - `.env.example`, `pyproject.toml` y `uv.lock`: dependencias `segno`, `pillow`, `zxing-cpp` y
    `fonttools`;
  - dos tests de `project_scaffold`: ver la valoración más abajo;
  - los ficheros de `progress/` y `feature_list.json`, en commits `chore(progress)` del
    orquestador.

  No hay refactorizaciones ajenas a la feature.

## Valoración de las decisiones locales

| Decisión | Valoración |
|---|---|
| `execute` síncrono | **Cabe.** design §3 fija `def execute` (no `async`), y `NetworkRepository` es síncrono. Contradice la convención §3 (casos de uso con I/O `async`), pero `conventions.md` dice que, si una convención choca con una spec, manda la spec y se anota en `progress/`. Está anotado. Rompe la simetría con `GetFeedInfo` (`async`). Ver S-02. |
| Deduplicar `--stop` | **Cabe.** Es la lectura literal de AC-08 ("un fichero por parada"). Sin deduplicar, `index.csv` tendría filas repetidas y el fichero se escribiría dos veces. Respeta el orden de la primera aparición, y tiene test. Ver S-03. |
| Exit 2 si faltan `--stop`/`--all` (o se dan ambos) | **Cabe, con reserva.** La sinopsis exige uno de los dos y el design no fija código para un uso incorrecto. 2 es el código estándar de Click para errores de uso, y la CLI falla antes de abrir la BD o escribir nada. El problema es que coincide con el 2 de "parada inexistente" (AC-10), así que un script no puede distinguir los dos casos. El test solo comprueba `!= 0`. Ver S-01. |
| Formato de `index.csv` | **Cabe.** Cumple design §3: UTF-8 y cabecera `stop_id,name,url,file`. Lo demás son detalles que el design deja abiertos: módulo `csv` estándar con `\r\n` (RFC 4180), sin BOM, `file` relativo al directorio de salida, se escribe también con una sola `--stop` (el design no lo condiciona) y, si faltan todas, solo con la cabecera. Nota: Excel abre mal un CSV UTF-8 sin BOM, pero la spec no lo pide. |
| Tests de `project_scaffold` retocados | **Cabe.** Son `tests/unit/test_settings.py:35` y `tests/integration/test_settings_env_file.py:67`. Cada uno gana una sola línea que define un secreto de 32 bytes, la consecuencia mínima e inevitable de AC-04. Lo que verifican (precedencia de variables y ficheros `.env`) no cambia. |

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **H-01 — La advertencia `security.dev_stop_token_secret` no sale en JSON y va a stdout.**
  `backend/src/avisabus/config.py:50` la emite dentro del validador de `Settings`. Los puntos de
  entrada construyen `Settings()` **antes** de `configure_logging`:
  - `adapters/inbound/cli/qr.py:38-39` (el mismo patrón está en `cli/gtfs.py:34-35`);
  - `main.py:10-11`.

  Así, structlog aún usa su configuración por defecto. Ejecución real en dev, sin secreto: por
  **stdout** sale `2026-11-01 00:18:43 [warning  ] security.dev_stop_token_secret env=dev`, en
  formato consola y no JSON. Incumple `docs/conventions.md` §3 ("Logs: structlog en JSON") y
  mezcla un log con la salida normal de la CLI. AC-05 se cumple (el evento se emite), y en `prod`
  nunca ocurre. Arreglo sugerido: emitir la advertencia después de configurar los logs (al
  construir el contenedor o con un método `Settings.warn_if_dev_secret()` llamado tras
  `configure_logging`), o configurar los logs antes.
- **H-02 — Ningún test cita AC-04 a nivel de CLI o API.** Los tests de AC-04 están en `Settings`,
  como permite la spec ("Verificación: unit"). La negativa a arrancar de la CLI y de la API depende
  de que sus puntos de entrada construyan `Settings()`, y hoy lo hacen (`cli/qr.py:38`,
  `main.py:10`). Lo he comprobado a mano con la CLI. Un test de integración (`qr generate` con
  `AVISABUS_ENV=prod` sin secreto, que sale ≠ 0 y no escribe nada) evitaría regresiones.
  Opcional.
- **H-03 — El error de configuración se muestra como traza completa de Typer.** Con `prod` y un
  secreto inválido, la CLI imprime una traza enriquecida de unas 60 líneas antes del mensaje. El
  mensaje es explícito y la traza **no** incluye el secreto: Typer 0.27 no muestra variables
  locales, y lo he comprobado con un canario. Aun así, un mensaje limpio por stderr sería más
  claro para el administrador. Es cosmético.

### Problemas de spec (no requieren CP-3; propuestas para una versión futura)

- **S-01 — Códigos de salida de la CLI (design §3):** la spec no dice qué código corresponde a un
  uso incorrecto (sin `--stop` ni `--all`, o con ambos). Click usa 2, que choca con el 2 de
  "parada inexistente" (AC-10). Convendría fijarlo en la spec: aceptar el 2 de Click y documentarlo,
  o reservar otro código para "parada inexistente".
- **S-02 — `execute` síncrono (design §3) frente a `docs/conventions.md` §3:** la spec se aparta
  de la convención sin decirlo de forma explícita. Bastaría una línea en design §3 que lo
  justifique (`NetworkRepository` es síncrono y el renderizado consume CPU), o pasarlo a `async`
  por coherencia con `GetFeedInfo`.
- **S-03 — `--stop` repetido y detalles de `index.csv`:** la spec no dice qué pasa con una parada
  repetida, ni si `index.csv` se escribe con una sola parada o cuando faltan todas. La
  implementación actual es razonable y conviene recogerla en el design para que no dependa de una
  interpretación.
