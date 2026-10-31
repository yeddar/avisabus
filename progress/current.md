# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-10-31
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** ninguna. `stop_tokens_qr` y `occupancy_sensor` en `done`, con PR abiertas (sin fusionar)

## Último paso
`occupancy_sensor` aprobada (ciclo 1) → PR #13. `stop_tokens_qr` v1.1 (T-04…T-07 tras el rebase sobre
la spec v1.1) aprobada (ciclo 1, `progress/review_stop_tokens_qr.md`) → PR abierta contra `develop`.
Las dos PR chocan en `config.py` (`ConfigurationError`), probablemente en `cli/container.py` y
`cli/main.py`, y en `feature_list.json`/`progress/`: la segunda en fusionarse necesita rebase.

## Siguiente paso
1. La persona fusiona las PR de `occupancy_sensor` (#13) y `stop_tokens_qr`; rebase de la segunda
   (resolver conflictos de `config.py`, CLI, `feature_list.json` y `progress/`).
2. `sae_arrivals_source`: **preguntar a la persona antes de empezar E-01** (requiere red y la
   grabación de 15 min en la parada 508 en hora punta, `stop_508_peak`).
3. `stop_arrivals_api` (v1.2).
4. En paralelo (fuera de Claude Code): specs del bloque 2 (PR #7).

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
- H-10 (aislamiento de los tests de AC-09 frente a `tmp_path/../.env`): no bloqueante, sin acción.
- **gtfs_import N-07 → `deployment_rpi`:** la BD crece al reimportar (68 → 139 MB) sin `VACUUM`.

## Notas
- Cabeceras reales confirmadas (2026-10-31): `trips.txt` **sin `direction_id`** → sentidos
  derivados (`specs/gtfs_import/design.md` §4.3). `shape_dist_traveled` en metros disponible.
- Node local v26 (convención: 22 LTS, fijada en `.nvmrc`); todo pasa.

## Checkpoints pendientes
Ninguno. CP-3 de `stop_tokens_qr` resuelto con la spec v1.1 (PR #12): AC-13 incluye DejaVuSans.ttf y su
licencia como dato del paquete; AC-12 exige exactamente el nivel M (`boost_error=False`).

## Bloqueos
Ninguno.
