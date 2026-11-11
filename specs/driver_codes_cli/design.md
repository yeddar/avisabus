# Códigos de conductor — design

> Feature: `driver_codes_cli` · Versión: 1.1 · Estado: APPROVED
> Requisitos: RF-24, RF-33, RNF-06, RNF-07 · Casos de uso: CU-13 · Depende de: project_scaffold

## 1. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `models/driver.py` | `DriverCode` |
| domain | `ports/driver.py` | `DriverCodeRepository`, `DriverCodeHasher`, `CodeGenerator` |
| application | `driver_codes.py` | `CreateDriverCode`, `ListDriverCodes`, `RevokeDriverCode` |
| adapters/outbound | `persistence/sqlite_driver_codes.py` | Tabla `driver_code` |
| adapters/outbound | `security/hmac_driver_code_hasher.py` | `HmacDriverCodeHasher` |
| adapters/outbound | `security/secrets_code_generator.py` | `SecretsCodeGenerator` (`secrets.randbelow`) |
| adapters/inbound | `cli/driver_codes.py` | `driver-codes create/list/revoke` |
| adapters/inbound | `cli/main.py`, `cli/container.py` | Registro y composición |

## 2. Interfaces

```python
# domain/models/driver.py
@dataclass(frozen=True, slots=True)
class DriverCode:
    code_id: str                 # "dc-" + 6 caracteres [a-z0-9]
    code_hash: str               # hex
    label: str
    created_at: datetime
    revoked_at: datetime | None
    @property
    def revoked(self) -> bool: ...

# domain/ports/driver.py
class DriverCodeHasher(Protocol):
    def hash(self, code: str) -> str: ...          # code: 8 dígitos sin espacios
class CodeGenerator(Protocol):
    def new_code(self) -> str: ...                 # 8 dígitos, con ceros a la izquierda
    def new_code_id(self) -> str: ...
class DriverCodeRepository(Protocol):
    def add(self, code: DriverCode) -> None: ...    # IntegrityError de hash → el caso de uso reintenta
    def get(self, code_id: str) -> DriverCode | None: ...
    def find_by_hash(self, code_hash: str) -> DriverCode | None: ...
    def list_all(self) -> list[DriverCode]: ...     # por created_at
    def revoke(self, code_id: str, at: datetime) -> DriverCode | None: ...

# application/driver_codes.py
@dataclass(frozen=True, slots=True)
class CreatedDriverCode:
    code: DriverCode
    plain_code: str              # solo para imprimirlo; no se registra
class CreateDriverCode:
    def execute(self, label: str) -> CreatedDriverCode: ...   # hasta 5 reintentos por colisión
class ListDriverCodes:
    def execute(self) -> list[tuple[DriverCode, bool]]: ...   # (código, tiene turno abierto)
class RevokeDriverCode:
    def execute(self, code_id: str) -> tuple[DriverCode, bool]: ...   # (código, tenía turno abierto)
```

"Tiene turno abierto": `ListDriverCodes` y `RevokeDriverCode` reciben un
`Callable[[str], bool]` (`has_open_session(code_id)`); hasta que exista `driver_session`, la CLI
compone uno que devuelve `False`. `driver_session` T-01 lo sustituye por la consulta a la tabla
de sesiones.

`HmacDriverCodeHasher`: `key = HMAC-SHA256(secret, b"avisabus:driver-code:v1")`,
`hash = HMAC-SHA256(key, code).hexdigest()`.

## 3. Datos

Tabla `driver_code`: `code_id` TEXT PK, `code_hash` TEXT UNIQUE NOT NULL, `label` TEXT NOT NULL,
`created_at` TEXT, `revoked_at` TEXT NULL (en `init_db`, `create_all`).

## 4. CLI

```
$ avisabus driver-codes create --label "Tablet 3"
Código creado: dc-k3m9qa  ·  Tablet 3
  Código de acceso: 4821 0937
  Apúntalo ahora: no se volverá a mostrar.

$ avisabus driver-codes list [--json]
CODE_ID    ETIQUETA   CREADO            ESTADO    TURNO
dc-k3m9qa  Tablet 3   2026-11-09 16:40  activo    no

$ avisabus driver-codes revoke dc-k3m9qa
Código dc-k3m9qa revocado. Tenía un turno abierto: se cerrará en menos de 1 minuto.
```

Los mensajes de la CLI van en castellano (como el resto de la CLI).

## 5. Estrategia de test

| AC | Test |
|---|---|
| AC-01, AC-03 | `tests/unit/test_driver_codes.py` (generador falso con colisión; *hasher*) |
| AC-01, AC-02, AC-04, AC-05 | `tests/integration/test_cli_driver_codes.py` (`CliRunner`, BD temporal) |
| AC-03 (logs), AC-06 | logs capturados en integración + logger falso en unitarios |

## 6. Preguntas abiertas

Ninguna.
