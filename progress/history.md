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
