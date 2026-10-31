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
