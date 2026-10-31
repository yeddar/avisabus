# Implementación: stop_tokens_qr
Spec: specs/stop_tokens_qr/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-10-31

> **Detenida en T-04 por el bloqueo B-01 (CP-3).** T-04 está implementada tal como dice el design
> y sus tests pasan, pero la etiqueta PNG no puede mostrar bien los nombres reales con la fuente
> que permite el design. T-05 y T-06 no se han empezado.

## Tareas
- [x] T-01 Configuración del secreto, validación por entorno y advertencia de desarrollo (AC-04, AC-05) (commit c5bc0c0)
- [x] T-02 `StopTokenSigner` y `HmacStopTokenSigner` (AC-01, AC-02, AC-03) (commit 89808c2)
- [x] T-03 `build_stop_url` (AC-06) (commit e30bd75)
- [ ] T-04 `QrRenderer` y `SegnoQrRenderer` (AC-07, AC-09, AC-12). **Bloqueada por B-01** (y B-02
      menor). El código sigue el design al pie de la letra y está en el commit de T-04. Falta cerrar
      la fuente de la etiqueta PNG.
- [ ] T-05 Caso de uso `GenerateStopQrCodes` (AC-08, AC-10, AC-11)
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
- **Decodificación en tests:** `zxing-cpp` (tiene rueda para macOS arm64). zxing solo lee
  imágenes raster, así que `tests/support/qr.py` rasteriza el `<path>` de segno (trazos `h`
  por fila) a una imagen y la decodifica. No hace falta cairo ni otra dependencia nativa.
- **Dependencias nuevas:** `segno` y `pillow` (runtime), `zxing-cpp` (dev).

## Bloqueos

### B-01 — La fuente por defecto de Pillow no muestra las letras acentuadas de los nombres de parada (CP-3)
- **Spec:** design §5 dice "Pillow añade una banda inferior blanca con el texto (fuente por
  defecto de Pillow o DejaVuSans si está disponible)". AC-07 y AC-09 exigen que la etiqueta
  muestre "el nombre de la parada (tal como viene en el GTFS)".
- **Realidad:**
  - La fuente por defecto de Pillow 13 (`ImageFont.load_default(size)` → *Aileron Regular*) no
    tiene glyph para ninguno de estos caracteres:
    `à è é í ï ò ó ú ü ç ñ À È É Í Ï Ò Ó Ú Ü Ç Ñ ª º`. Comprobado comparando cada máscara con la
    de un carácter inexistente.
  - En el feed real (`data/gtfs/emt/stops.txt`), **620 de 1117** nombres de parada llevan alguno
    de estos caracteres: `· À Á Ò à á ç è é í ï ñ ò ó ú ü`.
  - Ejemplo: "Institut Obrer de València…" sale impreso como "Val□ncia".
  - DejaVuSans no viene con macOS ni con las imágenes Docker *slim*, así que el design solo
    funciona donde DejaVuSans ya está instalada (p. ej. Debian con `fonts-dejavu-core`).
  - Los tests actuales no lo detectan: comprueban dimensiones, decodificación y que haya texto en
    la banda, no qué glyphs se dibujan.
- **Impacto:** en el PNG, más de la mitad de las paradas tendrían el nombre mal escrito en el
  cartel. El SVG no se ve afectado: el visor o la impresora usan una fuente `sans-serif` del
  sistema.
- **Propuesta (para el spec-writer / la persona):**
  1. *(Recomendada)* Incluir DejaVuSans.ttf en el paquete
     (`adapters/outbound/qr/fonts/`, unos 750 KB, licencia libre Bitstream Vera/DejaVu) y usarla
     siempre para el PNG. El resultado es igual en cualquier máquina y se puede probar. Añadir un
     AC o una línea de verificación: "la fuente de la etiqueta PNG tiene glyph para todos los
     caracteres de los nombres de `gtfs_mini`", con un test unitario de cobertura de glyphs.
  2. *(Alternativa)* Buscar varias fuentes del sistema (DejaVuSans, LiberationSans, Arial,
     Helvetica). Si ninguna cubre el texto, fallar con un error explícito en vez de usar Aileron.
     Exigir `fonts-dejavu-core` en la imagen de `deployment_rpi`. Es menos determinista y en CI
     depende de la máquina.

### B-02 — `boost_error` de segno frente a "nivel M" (menor; lo propongo para la misma revisión de spec)
- design §5 indica `segno.make(content, error="m", micro=False)`. Con el valor por defecto de
  segno (`boost_error=True`), la librería **sube** el nivel a Q o H si cabe en la misma versión.
  Ejemplo: una URL de 44 caracteres sale con nivel Q. AC-12 exige "corrección de errores nivel M".
- He implementado `boost_error=False`, que cumple AC-12 a la letra. Los tests comprueban el nivel
  con zxing en una URL que segno subiría a Q por defecto.
- **Propuesta:** que design §5 diga explícitamente `boost_error=False`, o que AC-12 diga "nivel M
  como mínimo" si se prefiere aprovechar el boost. Con la URL de producción típica (≈ 50
  caracteres) el resultado actual es M en ambos casos.

## Verificación
Pendiente. No se ha ejecutado `./init.sh verify` porque la feature está detenida en T-04. Al
detenerse, `uv run pytest`, `ruff check`, `ruff format --check`, `mypy` y `lint-imports` pasan:
267 tests, cobertura de `domain` + `application` 99,31 %.
