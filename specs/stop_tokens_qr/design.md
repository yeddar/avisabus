# Tokens de parada y QR — design

> Feature: `stop_tokens_qr` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-05, RNF-07 · Casos de uso: CU-12 · Depende de: gtfs_import

## 1. Resumen

Un `HmacStopTokenSigner` firma `stop:<stop_id>` con un secreto de configuración. La CLI
`qr generate` obtiene las paradas del `NetworkRepository`, construye la URL con
`StopUrlBuilder` y genera el QR con **segno** (SVG/PNG sin dependencias nativas); la etiqueta
se compone en SVG y, para PNG, con Pillow.

## 2. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `ports/stop_token.py` | `StopTokenSigner` (Protocol) |
| domain | `services/stop_url.py` | `build_stop_url(base_url, stop_id, token) -> str` |
| application | `generate_stop_qr_codes.py` | `GenerateStopQrCodes` |
| application | `ports` | `QrRenderer` (Protocol en `domain/ports/qr.py`) |
| adapters/outbound | `security/hmac_stop_token.py` | `HmacStopTokenSigner` |
| adapters/outbound | `qr/segno_renderer.py` | `SegnoQrRenderer` |
| adapters/inbound | `cli/qr.py` | `avisabus qr generate` |
| config | `config.py` | `stop_token_secret: SecretStr \| None`, validación por entorno |

## 3. Interfaces

```python
# domain/ports/stop_token.py
class StopTokenSigner(Protocol):
    def sign(self, stop_id: str) -> str: ...
    def verify(self, stop_id: str, token: str) -> bool: ...   # nunca lanza

# domain/ports/qr.py
@dataclass(frozen=True, slots=True)
class QrLabel:
    title: str            # nombre de la parada (GTFS)
    subtitle: str         # "Parada 508"
@dataclass(frozen=True, slots=True)
class QrRequest:
    content: str          # URL
    label: QrLabel
    format: Literal["svg", "png"]
class QrRenderer(Protocol):
    def render(self, request: QrRequest) -> bytes: ...

# application/generate_stop_qr_codes.py
@dataclass(frozen=True, slots=True)
class GenerateStopQrCodesCommand:
    stop_ids: Sequence[str] | None     # None = todas
    format: Literal["svg", "png"]
@dataclass(frozen=True, slots=True)
class GeneratedQr:   stop_id: str; name: str; url: str; filename: str; content: bytes
@dataclass(frozen=True, slots=True)
class QrGenerationResult:
    generated: list[GeneratedQr]
    missing_stop_ids: list[str]
class GenerateStopQrCodes:
    def __init__(self, network: NetworkRepository, signer: StopTokenSigner,
                 renderer: QrRenderer, public_base_url: str) -> None: ...
    def execute(self, cmd: GenerateStopQrCodesCommand) -> QrGenerationResult: ...
```

Raise: `NoActiveFeedError` (definida en `domain/errors.py`) si `network.active_feed()` es `None`.

Subtítulo de la etiqueta: `Parada {stop_id}` (la palabra es idéntica en castellano y valenciano).

### CLI

```
avisabus qr generate (--stop ID ... | --all) [--format svg|png] [--out DIR=./qr]
```

Escribe los ficheros (la escritura a disco es responsabilidad de la CLI, no del caso de uso) y
`index.csv` (UTF-8, cabecera `stop_id,name,url,file`). Códigos de salida: `0` todo bien,
`1` sin feed, `2` alguna parada inexistente.

### Firma

```python
digest = hmac.new(secret, f"stop:{stop_id}".encode(), hashlib.sha256).digest()[:16]
token  = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()     # 22 caracteres
verify = len(token) == 22 and hmac.compare_digest(sign(stop_id), token)
```

## 4. Datos

- Vector de prueba (AC-01): con secreto `b"test-secret-0123456789abcdef0123"` y `stop_id="508"`,
  el implementer calcula el token una vez con la fórmula anterior y lo fija en el test.
- Secreto de desarrollo fijo: `b"avisabus-dev-only-secret-do-not-use!"`.

## 5. Renderizado

- `segno.make(content, error="m", micro=False)`; `border=4`.
- SVG: el SVG de segno (escala 10) se incrusta en un SVG contenedor más alto con dos `<text>`
  (título 28 px, subtítulo 22 px, `font-family="sans-serif"`, centrados, texto escapado).
- PNG: QR a escala que garantice ≥ 600 px de lado; Pillow añade una banda inferior blanca con
  el texto (fuente por defecto de Pillow o DejaVuSans si está disponible).

## 6. Errores

| Situación | Resultado |
|---|---|
| Producción sin secreto válido | `ConfigurationError` al construir `Settings` → la app/CLI no arranca |
| Parada inexistente | se añade a `missing_stop_ids`; la CLI imprime `ERROR: parada 9999 no existe` |
| Sin feed | `NoActiveFeedError` → exit 1 |

## 7. Configuración

| Variable | Default | Notas |
|---|---|---|
| `AVISABUS_STOP_TOKEN_SECRET` | — | Obligatoria en `prod` (≥ 32 bytes) |
| `AVISABUS_PUBLIC_BASE_URL` | `http://localhost:5173` | Ya existe (scaffold) |

## 8. Estrategia de test

- Unit: firma (vector), verificación (casos válidos e inválidos), `compare_digest` (monkeypatch
  para comprobar que se llama), `build_stop_url` (barras), validación de `Settings` por entorno,
  parámetros de segno (doble del renderer o espía).
- Integration: CLI con BD importada desde `gtfs_mini` en `tmp_path`; decodificación del QR con
  `zxing-cpp` (dependencia de test; decisión local permitida usar otra librería decodificadora
  pura si `zxing-cpp` no tiene rueda para la plataforma).

## 9. Decisiones locales permitidas

- Maquetación exacta de la etiqueta (márgenes, tamaños) mientras sea legible e incluya los textos.
- Librería de decodificación en tests.

## 10. Preguntas abiertas

Ninguna.
