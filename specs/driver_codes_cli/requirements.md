# Códigos de conductor — requirements

> Feature: `driver_codes_cli` · Versión: 1.1 · Estado: APPROVED
> Requisitos: RF-24, RF-33, RNF-06, RNF-07 · Casos de uso: CU-13 · Depende de: project_scaffold

## Contexto

El conductor entra en su vista con un **código de acceso** (RF-24). Los códigos los gestiona el
administrador por la CLI (RF-33, CU-13): crearlos, listarlos y revocarlos. El código en claro se
muestra **una sola vez** al crearlo; el sistema guarda solo un *hash* con clave del servidor
(ADR-017), para poder buscarlo con un índice y que, sin el secreto, la base de datos no sirva
para adivinarlo. El límite de intentos al iniciar turno (CU-08 2a) lo pone `driver_session`.

Los códigos no se asocian a personas: llevan una etiqueta libre (p. ej. "Tablet 3" o
"Conductor 12") elegida por el administrador.

## Alcance

- Modelo `DriverCode`, puerto `DriverCodeRepository` y su implementación SQLite.
- Generador de códigos y *hasher* con clave del servidor.
- Comandos `avisabus driver-codes create | list | revoke`.

## Fuera de alcance

- Validación del código al iniciar turno y cierre de sesiones de códigos revocados
  (`driver_session`).

## Criterios de aceptación

- **driver_codes_cli.AC-01** — CUANDO se ejecuta `avisabus driver-codes create --label <texto>`,
  EL SISTEMA DEBERÁ generar un código de 8 dígitos con un generador criptográfico, guardarlo con
  un `code_id` corto (`dc-` + 6 caracteres) y su *hash*, e imprimir **una sola vez** el código
  agrupado en dos bloques ("1234 5678") junto al `code_id` y la etiqueta. SI el código generado ya
  existe (activo o revocado), ENTONCES DEBERÁ generar otro.
  *Verificación:* unit (generador con fuente aleatoria inyectada) + integration (CLI con
  `CliRunner`)
- **driver_codes_cli.AC-02** — LA ETIQUETA DEBERÁ ser obligatoria, de 1 a 40 caracteres
  imprimibles, sin saltos de línea; SI no lo es, ENTONCES el comando DEBERÁ terminar con código
  de salida distinto de 0 y un mensaje claro, sin crear nada.
  *Verificación:* integration
- **driver_codes_cli.AC-03** — EL *HASH* DEBERÁ ser HMAC-SHA256 del código con una clave derivada
  de `AVISABUS_STOP_TOKEN_SECRET` con separación de dominio (distinta de la del dispositivo);
  EL CÓDIGO EN CLARO NO DEBERÁ guardarse ni aparecer en ningún log ni (v1.1) en las trazas de
  error de la CLI: la aplicación Typer fija `pretty_exceptions_show_locals=False` de forma
  explícita, con un test que lo comprueba.
  *Verificación:* unit + integration (inspección de la tabla y de los logs capturados)
- **driver_codes_cli.AC-04** — CUANDO se ejecuta `avisabus driver-codes list`, EL SISTEMA DEBERÁ
  mostrar una tabla con `code_id`, etiqueta, fecha de creación, estado (`activo`/`revocado`) y si
  tiene un turno abierto, sin mostrar el código ni su *hash*; con `--json`, la misma información
  en JSON.
  *Verificación:* integration
- **driver_codes_cli.AC-05** — CUANDO se ejecuta `avisabus driver-codes revoke <code_id>`, EL
  SISTEMA DEBERÁ marcarlo como revocado (con fecha) e informar de si tenía un turno abierto, que
  `driver_session` cerrará; SI el `code_id` no existe, ENTONCES DEBERÁ terminar con código de
  salida 1; revocar uno ya revocado DEBERÁ ser inocuo (salida 0, aviso).
  *Verificación:* integration
- **driver_codes_cli.AC-06** — EL SISTEMA DEBERÁ registrar `driver_code.created` y
  `driver_code.revoked` con `code_id` y sin la etiqueta ni el código.
  *Verificación:* unit (logger falso)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-24 Código de acceso | AC-01, AC-03 |
| RF-33 CLI de códigos | AC-01, AC-02, AC-04, AC-05 |
| RNF-06 Privacidad | AC-03, AC-06 |
| RNF-07 Seguridad | AC-01, AC-03 |
| CU-13 | AC-01 … AC-05 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-09 | Versión inicial aprobada (PR #46). | CP-1 del bloque 4. Aprobada por la persona. |
| 1.1 | 2026-11-11 | AC-03: trazas de la CLI sin variables locales, fijado de forma explícita (no por el valor por defecto de Typer). T-05. | N-07 de la revisión de `driver_codes_cli`. Pendiente de aprobación. |
