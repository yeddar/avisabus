# Implementación: stop_tokens_qr
Spec: specs/stop_tokens_qr/ (v1.1, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-01

> Retomada en T-04 tras la spec v1.1 (PR #12), que resuelve los bloqueos B-01 y B-02. La rama se
> rebasó sobre `develop`, así que los hashes de T-01 a T-04 son los posteriores al rebase.

## Tareas
- [x] T-01 Configuración del secreto, validación por entorno y advertencia de desarrollo (AC-04, AC-05) (commit dbe22bd)
- [x] T-02 `StopTokenSigner` y `HmacStopTokenSigner` (AC-01, AC-02, AC-03) (commit 6d57ee2)
- [x] T-03 `build_stop_url` (AC-06) (commit 9663d6f)
- [x] T-04 `QrRenderer` y `SegnoQrRenderer` (AC-07, AC-09, AC-12, AC-13) (commits 24c5d2b y T04HASH:
      el primero, de la v1.0, con el renderer; el segundo, de la v1.1, con la fuente incluida, su
      licencia y el test de cobertura de caracteres)
- [x] T-05 Caso de uso `GenerateStopQrCodes` (AC-08, AC-10, AC-11) (commit T05HASH)
- [ ] T-06 CLI `avisabus qr generate` (AC-07 – AC-11)
- [ ] T-07 Verificación completa

## Decisiones locales
- **`ConfigurationError`** se define en `config.py`, junto a `Settings`. El design no dice dónde
  va. No hereda de `ValueError`, así que pydantic no la envuelve en `ValidationError` y sale tal
  cual al construir `Settings()`. El mensaje nombra la variable pero no incluye el valor.
- **Secreto efectivo:** el campo sigue siendo `stop_token_secret: SecretStr | None` (design §2).
  El método `Settings.stop_token_secret_bytes()` devuelve el secreto configurado o, en dev/test,
  `DEV_STOP_TOKEN_SECRET`. Un valor vacío (`AVISABUS_STOP_TOKEN_SECRET=`) cuenta como "no
  configurado": en prod falla y en dev/test usa el secreto de desarrollo y avisa. La longitud se
  mide en bytes UTF-8.
- **Advertencia `security.dev_stop_token_secret`:** se registra al construir `Settings` (validador
  `after`) en dev/test cuando no hay secreto. Incluye el campo `env` y nunca el secreto.
- **Tests de `project_scaffold` adaptados (T-01):**
  `tests/unit/test_settings.py::test_environment_variables_with_prefix_override_defaults` y
  `tests/integration/test_settings_env_file.py::test_process_environment_takes_precedence_over_both_dotenv_files`
  ponían `AVISABUS_ENV=prod` sin secreto. Con AC-04 eso ya no arranca, así que ahora definen un
  secreto de 32 bytes. Es el único cambio y no altera lo que verifican.
- **`.env.example`:** `AVISABUS_STOP_TOKEN_SECRET` va comentada. Si estuviera vacía y activa,
  se leería como cadena vacía. La entrada documenta el requisito en prod y cómo generar el secreto.
- **`HmacStopTokenSigner.verify`:** antes de `hmac.compare_digest` comprueba la forma del token
  con `[A-Za-z0-9_-]{22}`. Esa comprobación no depende del secreto. Así `compare_digest` siempre
  recibe `str` ASCII: con caracteres no ASCII lanzaría `TypeError`, y AC-02 exige que no lance.
  Un `stop_id` que no se puede codificar en UTF-8 devuelve `False`.
- **Etiqueta SVG (maquetación, §9):** el QR de segno (escala 10, borde 4) va en un SVG
  contenedor del mismo ancho, con fondo blanco. Debajo hay dos `<text>` (28 px y 22 px,
  `sans-serif`, centrados, escapados). Los nombres largos (hasta 60 caracteres en el feed real) se
  parten por palabras en varias `<tspan>`, con un ancho medio estimado de 0,5 em por carácter.
- **Etiqueta PNG (maquetación, §9):** la escala es `ceil(600 / módulos)`, así que el QR mide
  ≥ 600 px de lado. Los tamaños de letra son proporcionales al lado (40/32 px para 615 px). El
  título se parte por palabras midiendo con la fuente real.
- **Fuente de la etiqueta PNG (v1.1, AC-13):** `SegnoQrRenderer` lee
  `adapters/outbound/qr/fonts/DejaVuSans.ttf` con `importlib.resources` (bytes cacheados una vez
  por proceso) y crea cada tamaño con `ImageFont.truetype(BytesIO(...))`. Ya no hay búsqueda en
  el sistema ni vuelta a `ImageFont.load_default`.
- **Origen de la fuente:** release oficial del proyecto DejaVu, **versión 2.37**,
  `https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2`
  (SHA-256 del archivo `fa9ca4d1…46e17d7`). Se han copiado sin cambios:
  - `ttf/DejaVuSans.ttf` como `fonts/DejaVuSans.ttf` (757 076 bytes, SHA-256 `7da195a7…ed848954`);
  - `LICENSE` como `fonts/LICENSE-DejaVu.txt` (8 816 bytes, SHA-256 `7a083b13…e5958a93`): licencia
    de Bitstream Vera y Arev; los cambios de DejaVu son de dominio público.
- **Dato del paquete:** hatchling ya metía los ficheros de `src/avisabus/` en la rueda. Aun así,
  se declaran explícitamente en `pyproject.toml` (`[tool.hatch.build.targets.wheel] artifacts`),
  como pide el design §5. Comprobación manual (en el scratchpad, fuera del repositorio): la rueda
  y el sdist contienen los dos ficheros, y una rueda instalada en un venv limpio genera un PNG con
  la fuente incluida.
- **Test de cobertura de caracteres (AC-13):** con `fontTools` (nueva dependencia de desarrollo),
  usando el `cmap` de la fuente. El test comprueba también que `gtfs_mini` contiene los caracteres
  problemáticos (`à è é í ò ó ñ ç · À Á`), para que no pase en vacío. Los tests de AC-13 van en
  `tests/integration/test_segno_renderer.py`, el fichero que fija T-04, para que el comando de
  verificación de la tarea los ejecute. Se añaden dos tests de comportamiento:
  - un espía de `ImageFont.truetype` / `load_default` (solo se carga la fuente incluida);
  - "València", "Valéncia", "Valencia", "Calassanç" y "Calassanc" producen bandas distintas. Con
    una fuente sin esos glifos, è y é salen con la misma caja de sustitución. Este test fallaba
    con el código de la v1.0.
- **`GenerateStopQrCodes.execute` es síncrono**, como fija design §3 (`def execute`), porque
  `NetworkRepository` es síncrono. La convención general (casos de uso con I/O `async`) cede ante
  la spec.
- **Parada repetida en `--stop` (AC-08, "un fichero por parada"):** se genera una sola vez, en el
  orden de su primera aparición. Es lectura literal del AC, no un comportamiento nuevo. Las
  inexistentes se listan en `missing_stop_ids` en el orden en que se pidieron.
- **`NoActiveFeedError`** (en `domain/errors.py`, subclase de `DomainError`) no lleva argumentos,
  y su mensaje fijo ("no active GTFS feed") no incluye identificadores.
- **`--all`** usa el orden de `NetworkRepository.list_stop_ids()`: `stop_id` ordenado como
  texto en el adaptador SQLite.
- **Decodificación en tests:** `zxing-cpp` (tiene rueda para macOS arm64). zxing solo lee
  imágenes raster, así que `tests/support/qr.py` rasteriza el `<path>` de segno (trazos `h`
  por fila) a una imagen y la decodifica. No hace falta cairo ni otra dependencia nativa.
- **Dependencias nuevas:** `segno` y `pillow` (runtime), `zxing-cpp` y `fonttools` (dev).

## Bloqueos

Ninguno abierto.

- **B-01 — RESUELTO en la spec v1.1.** La fuente por defecto de Pillow no tenía glifos para las
  letras acentuadas: 620 de las 1 117 paradas del feed real estaban afectadas. AC-13 y design §5
  piden ahora la fuente DejaVu Sans incluida en el paquete, con su licencia, y un test de
  cobertura de caracteres. Implementado en T-04 (v1.1).
- **B-02 — RESUELTO en la spec v1.1.** `boost_error` de segno frente al nivel M. AC-12 exige
  ahora exactamente M, y design §5 pide `boost_error=False`. La v1.0 ya lo implementaba así, y los
  tests lo comprueban con una URL que segno subiría a Q.

## Verificación
Pendiente (T-07).
