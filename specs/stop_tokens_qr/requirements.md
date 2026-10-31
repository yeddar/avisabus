# Tokens de parada y QR — requirements

> Feature: `stop_tokens_qr` · Versión: 1.1 · Estado: APPROVED
> Requisitos: RF-05, RNF-07 · Casos de uso: CU-12 · Depende de: gtfs_import

## Contexto

El pasajero llega a la aplicación escaneando el QR físico de su parada. La URL del QR identifica
la parada y contiene un **token firmado** que impide crear avisos en paradas arbitrarias
cambiando el número en la URL (D4). Esta feature define el firmado/verificación del token y la
generación de los QR por CLI. La validación del token en la API la usa `stop_arrivals_api` y,
después, `alert_create`.

## Alcance

- Puerto `StopTokenSigner` y adaptador HMAC-SHA256.
- Construcción de la URL pública de una parada.
- Comando `avisabus qr generate` (una parada, varias o todas) en SVG (por defecto) o PNG, con
  etiqueta impresa (nombre y código de parada) e índice CSV.

## Fuera de alcance

- Rotación de secretos con varias claves válidas a la vez (cambiar el secreto implica
  regenerar e imprimir los QR).
- Diseño gráfico del cartel de parada.
- Protección contra la reutilización de una foto del QR (limitación aceptada; el rate limit de
  avisos la acota en `alert_create`).

## Criterios de aceptación

### Token

- **stop_tokens_qr.AC-01** — EL SISTEMA DEBERÁ generar para cada `stop_id` un token determinista
  igual a los primeros 16 bytes de `HMAC-SHA256(secreto, "stop:" + stop_id)` codificados en
  base64url sin relleno (22 caracteres).
  *Verificación:* unit (vector de prueba fijo)
- **stop_tokens_qr.AC-02** — CUANDO se verifica un par (`stop_id`, token) correcto, EL SISTEMA
  DEBERÁ aceptarlo; SI el token no corresponde a ese `stop_id`, está truncado, contiene
  caracteres no válidos o está vacío, ENTONCES EL SISTEMA DEBERÁ rechazarlo sin lanzar excepción.
  *Verificación:* unit
- **stop_tokens_qr.AC-03** — EL SISTEMA DEBERÁ comparar tokens en tiempo constante.
  *Verificación:* unit (uso de `hmac.compare_digest`, comprobado con un doble) + revisión
- **stop_tokens_qr.AC-04** — SI `AVISABUS_ENV=prod` y `AVISABUS_STOP_TOKEN_SECRET` no está
  definido o tiene menos de 32 bytes, ENTONCES EL SISTEMA DEBERÁ negarse a arrancar (API y CLI)
  con un error de configuración explícito.
  *Verificación:* unit
- **stop_tokens_qr.AC-05** — MIENTRAS `AVISABUS_ENV` sea `dev` o `test` y no haya secreto
  configurado, EL SISTEMA DEBERÁ usar un secreto de desarrollo fijo y registrar la advertencia
  `security.dev_stop_token_secret`.
  *Verificación:* unit
- **stop_tokens_qr.AC-06** — EL SISTEMA DEBERÁ construir la URL de una parada como
  `{AVISABUS_PUBLIC_BASE_URL}/p/{stop_id}?t={token}` sin barras duplicadas.
  *Verificación:* unit

### Generación de QR

- **stop_tokens_qr.AC-07** — CUANDO el administrador ejecuta
  `avisabus qr generate --stop 508 --out <dir>`, LA CLI DEBERÁ crear `<dir>/508.svg` con un QR
  que codifica la URL de la parada y, debajo, el nombre de la parada (tal como viene en el GTFS)
  y el texto `Parada 508` (idéntico en castellano y valenciano).
  *Verificación:* integration (el SVG se decodifica y la URL coincide; el texto aparece)
- **stop_tokens_qr.AC-08** — CUANDO se indican varias `--stop` o `--all`, LA CLI DEBERÁ generar
  un fichero por parada y un `index.csv` con las columnas `stop_id,name,url,file`.
  *Verificación:* integration
- **stop_tokens_qr.AC-09** — CUANDO se indica `--format png`, LA CLI DEBERÁ generar PNG de al
  menos 600×600 px para el código QR con la misma etiqueta.
  *Verificación:* integration (dimensiones y decodificación)
- **stop_tokens_qr.AC-10** — SI una parada indicada no existe en el feed activo, ENTONCES LA CLI
  DEBERÁ informar del error para esa parada, continuar con las demás y terminar con código 2.
  *Verificación:* integration
- **stop_tokens_qr.AC-11** — SI no hay feed importado, ENTONCES LA CLI DEBERÁ indicarlo y
  terminar con código 1 sin generar ficheros.
  *Verificación:* integration
- **stop_tokens_qr.AC-12** — EL SISTEMA DEBERÁ generar los QR con corrección de errores
  **exactamente** de nivel M (sin subirlo automáticamente aunque quepa) y zona de silencio de 4
  módulos.
  *Verificación:* unit (parámetros pasados a la librería)

- **stop_tokens_qr.AC-13** — LA ETIQUETA de los PNG DEBERÁ dibujarse con la fuente DejaVu Sans
  incluida en el repositorio (no con fuentes del sistema), de modo que se muestren correctamente
  todos los caracteres de los nombres de parada (`à é í ó ú ç ñ l·l`, etc.); y EL REPOSITORIO
  DEBERÁ incluir el texto de su licencia junto al fichero de la fuente.
  *Verificación:* unit (la fuente contiene un glifo para cada carácter de todos los nombres de
  parada de `gtfs_mini`) + revisión (licencia)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-05 QR por parada con token firmado | AC-01, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-13 |
| RNF-07 Seguridad (HMAC, secretos por configuración) | AC-01, AC-02, AC-03, AC-04, AC-05 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-10-31 | Versión inicial aprobada (PR #2) | — |
| 1.1 | 2026-10-31 | AC-13: fuente DejaVu Sans incluida en el repositorio para la etiqueta PNG. AC-12: nivel de corrección exactamente M (`boost_error=False`). | Bloqueos B-01 (la fuente por defecto de Pillow no tiene tildes, cedillas ni eñes; 620 de 1 117 paradas afectadas) y B-02 del implementer. Aprobada por la persona. |
