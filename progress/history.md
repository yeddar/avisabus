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

## 2026-11-01 · stop_tokens_qr · integración con occupancy_sensor (rebase de la PR #14)
- PR #13 fusionada; `feat/stop_tokens_qr` rebasada sobre `develop`. Conflictos de código resueltos
  conservando ambas features; fix solo de tests (0128582) por el aviso del secreto de desarrollo en
  tests de `occupancy_sensor` que comparan stdout.

## 2026-11-02 · stop_tokens_qr · PR #14 fusionada · sae_arrivals_source · spec_approved → exploring
- PR #14 fusionada tras el rebase (bloque 1: 4/6 en `done`).
- La persona da paso a `sae_arrivals_source`; rama `feat/sae_arrivals_source`, exploración E-01.

## 2026-11-02 · sae_arrivals_source · exploring → spec_blocked (CP-3)
- E-01 (`progress/explore_sae.md`, 14 peticiones ≤ 1/20 s por parada): `getSAE` (XML) cerrado a
  terceros; la fuente usable es el HTML `QR.php?sec=est&p={id}`. Parada inexistente = 200 sin
  entradas. Sin muestras de `HH:MM` ni "sin llegadas". Aviso legal de EMT a valorar.

## 2026-11-02 · sae_arrivals_source · spec_blocked → spec_approved (v1.1, CP-3 + CP-1)
- E-01: `getSAE` (XML) cerrado a terceros; la fuente es `QR.php` (HTML), enlazada por el
  Ajuntament. La persona aprueba la v1.1 (ADR-015, AC-21, AC-22, T-08b) y envía un correo a EMT
  solicitando permiso para `getSAE` y preguntando por una API oficial.

## 2026-11-02 · sae_arrivals_source · spec_approved → implementing
- E-01 ya hecha (no se repite). Implementer con T-01…T-07 y T-09; T-08 (grabación en hora punta)
  queda para el martes 2026-11-03 a las 7:45 con la persona; T-08b opcional.

## 2026-11-02 · sae_arrivals_source · implementing (T-01…T-07, T-09 hechas)
- Parser `QR.php`, fuente HTTP, caché, grabación/replay, CLI `sae fetch`/`record` y composición.
  Verify en rojo solo por el test de AC-19 (a), que espera la grabación `stop_508_peak` (T-08, 2026-11-03 7:45).

## 2026-11-02 · sae_arrivals_source · implementing → in_review
- T-08 adelantada a petición de la persona: grabación real de 25 min (lunes 20:42–21:07, fuera de
  hora punta), paradas 508 y 2070, 0 fallos; 3 pasos en la 508 (70, 93, 70). Test de AC-19 (a)
  relajado a "508 ∈ stops" (D-18). `./init.sh verify` en verde (617 tests, cobertura 99,51 %).

## 2026-11-02 · sae_arrivals_source · in_review → done
- Revisión ciclo 1: APPROVED (22 AC con evidencia, verify en verde). No bloqueantes NB-1…NB-8
  anotados en `current.md`. PR contra `develop` abierta, sin fusionar. Bloque 1: 5/6 en `done`.

## 2026-11-02 · stop_tokens_qr, sae_arrivals_source, occupancy_sensor · done → spec_approved → implementing
- PR #16 fusionada. PR #17 (ajustes de cierre del bloque 1): `occupancy_sensor` v1.1 (SP-01, AC-03),
  `stop_tokens_qr` v1.2 (S-01, H-01), `sae_arrivals_source` v1.2 (NB-1, NB-4, NB-6, NB-7),
  `stop_arrivals_api` v1.3 (nota sobre la parada 2070). Rama única `fix/bloque-1-ajustes`.

## 2026-11-02 · stop_tokens_qr, sae_arrivals_source, occupancy_sensor · implementing → in_review
- Tareas nuevas hechas (T-08/T-09, T-11…T-13, T-07/T-08); `./init.sh verify` en verde (645 tests,
  cobertura 99,52 %). Forzados por defecto pasan de 18/58/86 a 22/61/83 plazas (SP-01).

## 2026-11-02 · stop_tokens_qr, sae_arrivals_source, occupancy_sensor · in_review → done
- Revisión ciclo 1 (v1.2 / v1.2 / v1.1): APPROVED las tres, con pruebas de mutación; verify en verde.
  No bloqueantes anotados en `current.md`. PR de `fix/bloque-1-ajustes` contra `develop`, sin fusionar.

## 2026-11-02 · fix/bloque-1-ajustes fusionada (PR #18) · stop_arrivals_api · spec_approved → exploring
- Rama `feat/stop_arrivals_api`. Exploración E-01 y E-02 → `progress/explore_destinations.md`;
  se para al terminar para revisarla con la persona.

## 2026-11-02 · stop_arrivals_api · exploring (E-01, E-02 completadas; pendiente de revisión)
- Resolución de sentido 99,2 % de 972 llegadas reales (≈ 95,5 % en red): sin CP-3 por umbral.
  Propuestas: quitar alias `c → carrer`, asignación óptima y tolerancia 10 min. Detectado en
  `sae_arrivals_source`: formatos `HH:MM:SS` y `"{destino} -"` no reconocidos (29 % nocturno).

## 2026-11-03 · stop_arrivals_api · exploring (E-03 completada)
- 10 consultas diurnas (C1/C2): C2 resuelta con alias + `C2|Av. Aragó`; C1 da "Cntr.Històric"
  genérico y no se resuelve en sus cabeceras 1959/2277 con la spec actual (opciones a/b/c en
  `explore_destinations.md`). Pendiente: PR de specs de la persona con las decisiones del CP-3.

## 2026-11-03 · stop_arrivals_api · CP-3 tras E-01/E-02/E-03 → spec v1.4 aprobada
- Resolución de sentido observada: 99,2 %. C1 usa "Cntr.Històric" en ambos sentidos → regla del
  sentido que sale (opción c). Emparejamiento óptimo con orden y tolerancia de 10 min.
- Reabiertas `sae_arrivals_source` (v1.3) y `occupancy_sensor` (v1.2); `stop_tokens_qr` v1.3 sin código.

## 2026-11-03 · CP-3 stop_arrivals_api resuelto (PR #19) · sae_arrivals_source, occupancy_sensor · → implementing
- Opción (c) "sentido que sale" para C1 (`stop_arrivals_api` v1.4). Reabiertas `sae_arrivals_source`
  v1.3 (T-14/T-15) y `occupancy_sensor` v1.2 (T-09/T-10) en la rama `fix/sae-occupancy-v1.3`.

## 2026-11-03 · sae_arrivals_source v1.3, occupancy_sensor v1.2 · implementing → in_review
- T-14/T-15 (`HH:MM:SS`, entradas sin tiempo, muestra nocturna real 2070+2312) y T-09/T-10 (test de
  composición AC-15); `./init.sh verify` en verde (665 tests).

## 2026-11-03 · sae_arrivals_source v1.3, occupancy_sensor v1.2 · in_review → done
- Revisión ciclo 1: APPROVED las dos (mutaciones incluidas). No bloqueantes y SP anotados en
  `current.md`. PR de `fix/sae-occupancy-v1.3` contra `develop`, sin fusionar.
