# Estado actual

> Fichero vivo: lo reescribe el orquestador al final de cada sesión.

**Fecha:** 2026-11-02
**Fase:** Implementación — Bloque 1 (Cimientos y datos)
**Feature en curso:** `sae_arrivals_source` — `spec_blocked` (CP-3 tras E-01)

## Último paso
PR #13 (`occupancy_sensor`) y PR #14 (`stop_tokens_qr`) fusionadas: 4/6 features del bloque 1 en
`done`. La persona da paso a `sae_arrivals_source`: rama `feat/sae_arrivals_source`, exploración E-01
completada (`progress/explore_sae.md`, muestras en `progress/explore_sae_samples/`) → CP-3.

## Siguiente paso
1. `sae_arrivals_source`: **la persona decide el CP-3** → spec-writer o PR de spec → CP-1 → implementer. **T-08 (grabación `stop_508_peak`, ≥ 15 min
   en hora punta) se coordina con la persona** (se graba con la CLI de T-07).
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
- **CP-3 · sae_arrivals_source (E-01)** — detalle en `progress/explore_sae.md`:
  1. Fuente: el XML `getSAE` de la spec (`emtvlcapi`) está cerrado a terceros ("Temporalmente no
     disponible desde el plano…"). La fuente usable es la página HTML
     `https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}` (campo `proximas_llegadas` de la capa
     226 del geoportal, CC BY 4.0). Propuesta: cambiar «Contexto», design §4/§7 (URL por defecto y
     reglas del parser HTML con `html.parser`), AC-04 (`Próximo`); interfaces sin cambios.
  2. Parada inexistente = HTTP 200 sin entradas (se confunde con "sin llegadas"). Propuesta: respuesta
     válida solo si la cabecera casa con `^{stop_id} - .+`; si no → `unparseable`.
  3. AC-19 (b)/(c): sin muestras reales de "sin llegadas" ni `HH:MM` → muestras derivadas
     documentadas, y/o grabación nocturna real (~23:30, 508, línea N4).
  4. Aviso legal de EMT: prohíbe reproducir contenidos/enlazar sin consentimiento escrito (no
     menciona scraping). Valorar pedir permiso a EMT o tratarlo en la memoria del TFM.
  5. `docs/requirements.md` RF-11 cita `minutos`/`horaLlegada` (cambio de redacción, CP-4).

## Bloqueos
- `sae_arrivals_source` en `spec_blocked` (CP-3 arriba). `stop_arrivals_api` depende de ella.
