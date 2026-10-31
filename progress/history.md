# Historial

> Append-only. Una entrada por transición relevante: fecha · feature · transición · resumen.

## 2026-10-31 · Proyecto · Fase de definición
- Visión, objetivos (OBJ-01…09) y decisiones D1–D12 aprobadas (`docs/vision.md`).
- Requisitos RF-01…RF-35 y RNF-01…RNF-15 aprobados (`docs/requirements.md`).
- Casos de uso CU-01…CU-14 y limitaciones LIM-01…LIM-04 aprobados (`docs/use_cases.md`).
- Arquitectura hexagonal, SQLite, proceso único, despliegue en Raspberry Pi tras Nginx Proxy
  Manager; ADR-001…ADR-010 (`docs/architecture.md`). Convenciones (`docs/conventions.md`).
- Hallazgo: los `stop_id` del GTFS coinciden con los códigos de parada del SAE (parada 2070).
- No existe feed público de posiciones de EMT València → posición estimada (ADR-005).

## 2026-10-31 · Bloque 1 · pending → spec_draft
- Specs redactadas: project_scaffold, gtfs_import, stop_tokens_qr, sae_arrivals_source,
  occupancy_sensor, stop_arrivals_api.

## 2026-10-31 · gtfs_import, stop_arrivals_api · spec_draft (revisión antes de CP-1)
- Cabeceras reales del feed: `trips.txt` no trae `direction_id`. Se añade la derivación de
  sentidos por extremos/orientación del trazado (gtfs_import AC-23…AC-27, T-03b) y la resolución
  del destino del SAE contra todos los headsigns de la parada (stop_arrivals_api AC-06).
- `shape_dist_traveled` disponible en metros (útil para `position_estimation`).

## 2026-10-31 · Bloque 1 · spec_draft → spec_approved (CP-1)
- La persona aprueba las specs de project_scaffold, gtfs_import, stop_tokens_qr,
  sae_arrivals_source, occupancy_sensor y stop_arrivals_api (versión 1.0).

## 2026-10-31 · project_scaffold · spec_approved → implementing → in_review → done
- Implementadas T-01…T-12 (rama `feat/project_scaffold`); `./init.sh verify --e2e` en verde.
- Revisión ciclo 1: APPROVED sin bloqueantes. Problemas de spec menores para la persona:
  H-02 (`include_external_packages = True` en `.importlinter`, falta en design §4) y
  H-03 (`.env` en la raíz no se lee porque el backend arranca desde `backend/`).

## 2026-10-31 · project_scaffold · done (v1.0) → spec_draft (v1.1)
- Hallazgos de revisión resueltos por la persona: H-02 (design §4 `include_external_packages`)
  y H-03 (`.env` único en la raíz, AC-23) → spec v1.1. H-01 → regla nueva en
  `docs/conventions.md` §3, a especificar en el bloque 3. H-04…H-08 descartados.

## 2026-10-31 · project_scaffold · spec_draft → spec_approved (v1.1, CP-1)
- La persona aprueba la spec v1.1. Pendiente: implementar T-13 y T-14 y revisión (ciclo 2).

## 2026-10-31 · project_scaffold v1.1 · spec_approved → implementing → in_review → done
- Implementadas solo T-13 (AC-23: `.env` único en la raíz, con prioridad de `backend/.env` y del
  entorno) y T-14 en `feat/project_scaffold-v1.1`; `./init.sh verify` en verde.
- Revisión ciclo 2: APPROVED sin bloqueantes. Cierra H-02 y H-03. Nuevos no bloqueantes: H-09
  (la CLI aún no usa `Settings`), H-10 (aislamiento de los tests de AC-09), H-11 (`../.env` en Docker).
- Rama remota `main` borrada a petición de la persona (estaba contenida en `develop`; sin datos GTFS).

## 2026-10-31 · gtfs_import · spec_approved → exploring → spec_blocked (CP-3)
- E-01 (`progress/explore_gtfs_feed.md`): §4.3 da 2 sentidos en las 42 líneas con viajes; ninguna
  circular por la regla de 500 m (C1/C2/C3 partidas en medios bucles) → la integración de AC-25
  con C2 es incumplible. Propuestas: opción A, formas por sentido, recorte de headsigns, línea 98 en `gtfs_mini`.

## 2026-10-31 · gtfs_import · spec_blocked → spec_approved (v1.1, CP-3 + CP-1)
- La persona resuelve el CP-3 de E-01: circulares de EMT como medios bucles (opción A), todas las
  formas por sentido (AC-29), solo líneas con viajes (AC-28), recorte de `trip_headsign` (AC-07),
  línea 98 en `gtfs_mini`. `stop_arrivals_api` v1.1: E-01 pregunta por los destinos del SAE en
  las circulares.

## 2026-10-31 · gtfs_import v1.1 · spec_approved → implementing → spec_blocked (CP-3)
- T-01…T-03b implementadas (AC-07, AC-08, AC-14, AC-19, AC-20, AC-24/25 en unit).
- B-01 en T-04: con la fecha de referencia del design §8 (2026-11-04), `gtfs_mini` no incluye el
  `route_id` 1055 de la 98 (solo fines de semana) → AC-24/AC-29 incumplibles para la 98.

## 2026-10-31 · gtfs_import · spec_blocked → spec_approved (v1.2, CP-1) → implementing
- CP-3 B-01 resuelto por la persona (PR #9): `gtfs_mini` con `--date 2026-11-09` (lunes + domingo),
  límite < 2,5 MB; `gtfs import` sin `--yes`. Sin cambios en los AC.
- `feat/gtfs_import` rebasada sobre `develop`; se reanuda la implementación desde T-04.

## 2026-10-31 · gtfs_import · implementing → in_review → done
- T-04…T-12 implementadas (T-01…T-03b ya hechas); `./init.sh verify` y tests `slow` en verde.
  Feed real: 4,6 s / 75 MB; 42 líneas × 2 sentidos derivados, coincidentes con E-01.
- Revisión ciclo 1: APPROVED sin bloqueantes. Huecos de spec no bloqueantes S-1…S-3 y
  observaciones N-01…N-07 en `progress/review_gtfs_import.md`. Pendiente: validación de sentidos por la persona.

## 2026-10-31 · occupancy_sensor · spec_approved → implementing
- Sin exploración (tasks.md: "No necesaria"). Rama `feat/occupancy_sensor` desde `develop`.
  (`stop_tokens_qr` queda en `spec_blocked` en su rama, a la espera de la spec v1.1.)

## 2026-11-01 · occupancy_sensor · implementing → in_review → done
- T-01…T-06 implementadas; `./init.sh verify` en verde (422 tests, cobertura 99,44 %).
- Revisión ciclo 1: APPROVED sin bloqueantes. Problemas de spec no bloqueantes SP-01 (AC-11 vs
  proporciones fijas de forzado con umbrales no por defecto) y SP-02 (firma de `progress`).

## 2026-10-31 · gtfs_import v1.3 / stop_arrivals_api v1.2 · specs (PR #11) · validación de sentidos
- La persona valida los sentidos derivados de `gtfs_import` (PR #10 fusionada).
- `gtfs_import` v1.3 documenta S-1…S-3 (sin cambios de código; sigue `done`). `stop_arrivals_api`
  v1.2 añade AC-18/T-05b (horarios del día de servicio siguiente si la ventana cruza la medianoche).

## 2026-10-31 · stop_tokens_qr · spec_approved → implementing
- Sin exploración (tasks.md: "No necesaria"). Rama `feat/stop_tokens_qr` desde `develop`.

## 2026-10-31 · stop_tokens_qr · implementing → spec_blocked (CP-3)
- T-01…T-03 hechas; T-04 detenida. B-01: la fuente por defecto de Pillow 13 no tiene glifos con
  tilde/cedilla/eñe (620/1 117 nombres afectados) y DejaVuSans no está garantizada → etiqueta PNG
  incumple AC-07/AC-09. B-02 (menor): `boost_error` de segno vs nivel M exacto de AC-12.

## 2026-10-31 · stop_tokens_qr · CP-3 decidido (spec v1.1 pendiente de PR)
- B-01 → incluir DejaVuSans.ttf y su licencia + test de cobertura de caracteres. B-02 → nivel QR
  "exactamente M" (`boost_error=False`). La persona prepara la spec v1.1 en una PR aparte.

## 2026-11-01 · stop_tokens_qr · spec_blocked → spec_approved (v1.1, CP-1) → implementing
- Spec v1.1 (PR #12) resuelve B-01/B-02. `feat/stop_tokens_qr` rebasada sobre `develop`; se
  reanuda desde T-04. (`occupancy_sensor` cerrada en su rama, PR #13.)

## 2026-11-01 · stop_tokens_qr · implementing → in_review → done
- T-04 (fuente DejaVu 2.37 incluida + licencia + test de cobertura), T-05…T-07; `./init.sh verify` en verde.
- Revisión ciclo 1: APPROVED sin bloqueantes; no bloqueantes H-01…H-03 y propuestas de spec S-01…S-03.
