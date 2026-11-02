# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-02
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `sae_arrivals_source` — `implementing` (spec v1.1)

## Último paso
Spec `sae_arrivals_source` v1.1 fusionada (PR #15). Implementer: T-01…T-07 y T-09 hechas
(`progress/impl_sae_arrivals_source.md`, decisiones D-01…D-17). `./init.sh verify` en rojo solo por
`test_sae_fixtures.py::test_a_real_peak_session_of_stop_508_shows_a_passage` (falta la grabación
de T-08); 616 tests en verde, cobertura 99,51 %.

## Siguiente paso
1. `sae_arrivals_source`: **T-08 (grabación `stop_508_peak`, ≥ 15 min, intervalo 20 s) el martes
   2026-11-03 a las 7:45 con la persona**, con la CLI de T-07. Comando en `progress/impl_sae_arrivals_source.md`
   (requiere `AVISABUS_SAE_CONTACT` con un correo de contacto, AC-01). Tras grabar: test de fixtures,
   README de fixtures, commit, T-10 (`./init.sh verify`) y reviewer (agente nuevo).
   T-08b (nocturna) es opcional.
2. `stop_arrivals_api` (v1.2) → fin del bloque 1 (CP-6).
3. Fuera de Claude Code: PR de specs para SP-01 (`occupancy_sensor`), S-01 y H-01 (`stop_tokens_qr`)
   — la prepara la persona; specs del bloque 2 (PR #7).

## Pendiente para specs futuras
- **Bloque 4 (`driver_session`/`driver_ui`):** en C2 y C3 cada sentido agrupa dos medios bucles
  con destinos distintos; al elegir línea y sentido, el conductor debe ver **todos** los destinos del
  sentido (no solo el principal), y la comprobación de "fuera de recorrido" debe usar
  `shapes_for_direction` (todas las formas).
- **H-01 (privacidad de logs):** criterio de aceptación en `realtime_events` o `alert_create`
  (bloque 3) según la regla nueva de `docs/conventions.md` §3.
- **H-09:** el primer subcomando de CLI que use configuración debe construir `Settings()`.
- **H-11:** en `deployment_rpi`, pasar la configuración con `env_file`/variables de Compose, no `../.env`.
- **stop_tokens_qr H-01:** el aviso `security.dev_stop_token_secret` sale por stdout sin formato JSON
  porque `Settings()` se construye antes de `configure_logging` (`cli/qr.py`, `main.py`); solo dev/test.
- **stop_tokens_qr S-01…S-03:** código de salida de uso incorrecto de la CLI (2 de Click = 2 de AC-10);
  `execute` síncrono sin justificar frente a conventions §3; `--stop` repetido e `index.csv` no
  especificados (implementado: deduplicar; `index.csv` siempre). H-03: traza de Typer con secreto inválido.
- **occupancy_sensor SP-01 (O-01):** AC-11 choca con las proporciones fijas de forzado (0,20/0,65/0,95)
  si los umbrales no son los de por defecto (p. ej. `full = 0,99` → FULL forzado = MEDIUM). Salidas:
  (c) limitar AC-11 a umbrales por defecto, (b) acotar umbrales en AC-03, (a) derivar `r` de los umbrales.
- **occupancy_sensor SP-02:** design §3 escribe `progress(trip_stop_times, at)` sin día de servicio ni
  la regla "mediodía − 12 h" (implementado con `service_date`).
- **occupancy_sensor → `stop_arrivals_api`:** definir inyección y ciclo de vida del engine/sensor
  expuestos en `main.py` (N-01); la vigencia del forzado usa `clock.now()`, no `at` (N-04).
- occupancy_sensor N-02 (`service_day_start` duplicado), N-03 (`--clear` exige línea existente).
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.
- **gtfs_import N-07 → `deployment_rpi`:** la BD crece al reimportar (68 → 139 MB) sin `VACUUM`.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno. CP-3 de `sae_arrivals_source` resuelto por la persona (2026-11-02): fuente `QR.php`
(ADR-015), cabecera de parada obligatoria (AC-21), `source_format` en las grabaciones (AC-22),
muestras derivadas para "sin llegadas" y `HH:MM`, grabación nocturna opcional (T-08b). Correo
enviado a EMT pidiendo permiso para `getSAE` y preguntando por una API oficial.

## Bloqueos
Ninguno. Pendiente: T-08 (grabación `stop_508_peak`) el martes 2026-11-03 a las 7:45.
