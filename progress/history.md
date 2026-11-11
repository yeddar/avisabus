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

## 2026-11-03 · PR #20 fusionada · stop_arrivals_api · spec_approved → implementing (v1.4)
- Exploración E-01…E-03 ya en `develop` (PR #19). Implementer con todas las tareas de v1.4; overrides
  iniciales = los de la exploración traducidos a headsign, solo los que un test demuestre necesarios.

## 2026-11-03 · stop_arrivals_api · implementing → in_review
- T-01…T-09 (+T-05b, T-05c); verify en verde (853 tests, cobertura 99,66 %). Ningún override
  necesario: las 139 entradas reales se resuelven con alias, umbral 0,2 y sentido que sale.

## 2026-11-03 · stop_arrivals_api · in_review → done · bloque 1 completo
- Revisión ciclo 1 (v1.4): APPROVED sin bloqueantes; overrides vacíos verificados de forma
  independiente. PR contra `develop` sin fusionar. Bloque 1: 6/6 en `done` → CP-6.

## 2026-11-03 · bloque 1 · CP-6 aprobado (cierre del bloque)
- La persona aprueba el bloque 1 (PR #21 fusionada) y la recomendación sobre el destino: en
  pantalla, el texto del SAE; en el texto accesible, el headsign del GTFS.
- Specs del bloque 2 actualizadas en la PR #7 con la guía visual (`docs/design.md`, del boceto
  revisado) y ajustes solo documentales de `sae_arrivals_source` 1.4, `occupancy_sensor` 1.3 y
  `stop_arrivals_api` 1.5. Pendiente de CP-1.

## 2026-11-03 · bloque 2 · spec_draft → spec_approved (CP-1)
- La persona aprueba la PR #7: `frontend_i18n`, `passenger_stop_view`, `position_estimation` y
  `passenger_map_view` v1.0, guía visual `docs/design.md` v1.0 y los ajustes documentales del
  bloque 1 (`sae_arrivals_source` 1.4, `occupancy_sensor` 1.3, `stop_arrivals_api` 1.5).

## 2026-11-03 · CP-6 bloque 1 superado · frontend_i18n · spec_approved → implementing
- PR #21 fusionada (bloque 1: 6/6). PR #7 fusionada: specs del bloque 2 (CP-1) y `docs/design.md`.
- `frontend_i18n` no necesita exploración; rama `feat/frontend_i18n`.

## 2026-11-03 · frontend_i18n · implementing → in_review
- T-01…T-08; `./init.sh verify --e2e` en verde (150 Vitest, 24 e2e en 3 perfiles). 4 desviaciones
  del design anotadas en el impl (i18next 26, huecos de `eslint-plugin-i18next`, test de AC-15 de
  `project_scaffold`). Capturas e2e en `frontend/e2e-captures/frontend_i18n/` (no versionadas).

## 2026-11-03 · frontend_i18n · in_review → done
- Revisión ciclo 1: APPROVED; las 4 desviaciones del design no requieren CP-3 (N-01 para la spec).
  PR contra `develop` sin fusionar. Bloque 2: 1/4 en `done`.

## 2026-11-03 · frontend_i18n PR #22 fusionada (AC-17 validado) · passenger_stop_view · spec_approved → implementing
- Sin exploración según su `tasks.md`; rama `feat/passenger_stop_view`.

## 2026-11-03 · passenger_stop_view · implementing → in_review
- T-01…T-10; `CI=1 ./init.sh verify --e2e` en verde (861 backend, 278 Vitest, 60 e2e, JS inicial
  138,7 KB gzip). 4 desviaciones a validar (TS 6 con `openapi-typescript`, rojo EMT `#e50000`, aviso
  de horario, `avisabus.lastStop` frente a `docs/conventions.md` §4).

## 2026-11-03 · passenger_stop_view · in_review → done
- Revisión ciclo 1: APPROVED; desviaciones sin CP-3. CP-4 pendiente (`docs/conventions.md` §4 por
  `avisabus.lastStop`). PR contra `develop` sin fusionar. Bloque 2: 2/4 en `done`.

## 2026-11-03 · passenger_stop_view PR #23 fusionada · position_estimation · spec_approved → implementing
- CP-4 y `passenger_stop_view` v1.1 en la PR #24 (pendiente). `position_estimation` sin exploración.

## 2026-11-03 · position_estimation · implementing → spec_blocked (CP-3)
- T-01…T-06 hechas. AC-17 (distancia a la parada no aumenta > 50 m) falla con `stop_508_peak` cuando
  el SAE retrasa la llegada (5 casos). Propuesta recomendada: limitar la propiedad a minutos no crecientes.

## 2026-11-03 · position_estimation · spec_blocked → spec_approved (v1.1, PR #25) → implementing
- Opción 1: AC-17 limitado a pares de instantes con minutos del SAE no crecientes. Se reanuda en T-07.

## 2026-11-03 · position_estimation · implementing → in_review
- T-07 (sesión real, 139 pares válidos, 5 excluidos) y T-08; firma alineada con design v1.1.
  `CI=1 ./init.sh verify --e2e` en verde (969 backend, 278 Vitest, 60 e2e).

## 2026-11-03 · position_estimation · in_review → done
- Revisión ciclo 1 (v1.1): APPROVED; H-01…H-05 no bloqueantes. PR contra `develop` sin fusionar.
  Bloque 2: 3/4 en `done` (falta `passenger_map_view`; antes, `passenger_stop_view` v1.1 tras la #24).

## 2026-11-03 · position_estimation PR #27 fusionada · passenger_stop_view · done → implementing (v1.1)
- Solo T-11 (AC-17, AC-24), en `feat/passenger_stop_view-v1.1` desde `specs/ajustes-bloque-2` (PR #24,
  aprobada, sin fusionar). La persona fusionará la #24 y la PR de T-11 seguidas.

## 2026-11-03 · passenger_stop_view v1.1 · implementing → in_review
- T-11 (AC-17, AC-24): anuncio y foco tras acciones manuales; `CI=1 ./init.sh verify --e2e` en verde
  (969 backend, 287 Vitest, 60 e2e).

## 2026-11-03 · passenger_stop_view v1.1 · in_review → done
- Revisión ciclo 1 de la v1.1: APPROVED; N-7/N-8 (foco) para la spec v1.2. PR contra `develop` sin
  fusionar (después de la #24). Bloque 2: 3/4 en `done`.

## 2026-11-04 · passenger_stop_view · done → implementing (v1.2, solo T-12)
- Spec v1.2 (PR #29): N-7/N-8 de foco. Rama `feat/passenger_stop_view-v1.2` desde `develop`.

## 2026-11-04 · passenger_stop_view v1.2 · implementing → in_review
- T-12: foco al `h1` tras 404 en acción manual; foco a "Actualizar" tras refresco automático con
  éxito; el aviso de error se mantiene durante reintentos automáticos sin datos. Verify --e2e en verde.

## 2026-11-04 · passenger_stop_view v1.2 · in_review → done
- Revisión ciclo 1 de la v1.2: APPROVED (13 mutaciones detectadas); N-9/N-10 para la spec. PR sin fusionar.

## 2026-11-04 · PR #24 y #28 fusionadas · passenger_map_view · spec_approved → exploring
- Rama `feat/passenger_map_view`; E-01 (Leaflet y teselas OSM). PR #29 (specs v1.2 de
  `passenger_stop_view` y `position_estimation`) pendiente de la persona.

## 2026-11-04 · passenger_map_view · exploring → implementing
- E-01: react-leaflet 5.0.0 + leaflet ^1.9.4; política de teselas de OSM cumplida en la demo (sin CP-3).

## 2026-11-04 · passenger_map_view · implementing → spec_blocked (CP-3)
- T-01 hecha (enlace "Ver en el mapa"). AC-04: B-01 (primera parada en `NOT_STARTED` no disponible) y
  B-02 ("Llega en {tiempo}" con `CLOCK_TIME`). O-1…O-4 para la misma revisión de spec.

## 2026-11-04 · passenger_map_view · spec_blocked → spec_approved (v1.1, PR #29) → implementing
- B-01 opción A (primera parada del trazado), B-02 con la regla de `passenger_stop_view.AC-06`,
  O-1…O-4 como se proponían. PR #29 trae también `passenger_stop_view` v1.2 (T-12) y
  `position_estimation` v1.2 (T-09). Rama actualizada con `develop` (merge).

## 2026-11-04 · passenger_map_view · implementing → in_review
- T-02…T-07 (v1.1); `CI=1 ./init.sh verify --e2e` en verde (392 Vitest, 84 e2e, JS inicial 141,2 KB
  gzip; Leaflet en fragmento diferido de 50,2 KB). Sin red en tests (teselas locales).

## 2026-11-04 · passenger_map_view · in_review → changes_requested → implementing (ciclo 2)
- Revisión ciclo 1: CHANGES_REQUESTED por B-01 (AC-10: `panBy` con flechas anima 0,25 s con
  movimiento reducido; el test solo comprueba opciones). Arreglo local, sin CP-3.

## 2026-11-04 · passenger_map_view · implementing → in_review (ciclo 2)
- B-01 corregido (`panBy` sin animación con movimiento reducido, tests unitarios y e2e que fallaban
  antes); N-01 resuelto. Verify --e2e en verde (395 Vitest, 87 e2e).

## 2026-11-04 · passenger_map_view · in_review → done
- Revisión ciclo 2: APPROVED (B-01 corregido; mutaciones detectadas). PR contra `develop` sin fusionar.
  Bloque 2: 4/4 en `done`; quedan `passenger_stop_view` T-12 y `position_estimation` T-09 (v1.2) → CP-6.

## 2026-11-04 · passenger_stop_view v1.2 PR #31 abierta · position_estimation · done → implementing (v1.2, T-09)
- Spec v1.2 (PR #29): H-01 (`AT_STOP` si la parada objetivo es la primera) y H-02 (`NO_VEHICLE` con
  `position.estimate_failed` en vez de 500). Rama `feat/position_estimation-v1.2` desde `develop`.

## 2026-11-04 · position_estimation v1.2 · implementing → in_review
- T-09 (AC-04 `AT_STOP` en la primera parada; AC-11 `NO_VEHICLE` + `position.estimate_failed`, sin 500).
  Verify --e2e en verde (988 backend). Aviso: `bundle-budget.test.ts` lee `frontend/dist/` antes del build.

## 2026-11-04 · position_estimation v1.2 · in_review → done · bloque 2 completo
- Revisión ciclo 1 de la v1.2: APPROVED; H-01…H-03 para la spec, H-04 del harness (tests de bundle
  leen `dist/` antes del build). PR sin fusionar. Bloque 2: 4/4 en `done` → CP-6.

## 2026-11-04 · passenger_stop_view v1.2 PR #31 fusionada
- `feat/position_estimation-v1.2` actualizada con `develop` (merge sin conflictos) para la PR #32.

## 2026-11-04 · bloque 2 · CP-6 aprobado (cierre del bloque)
- La persona revisa el bloque 2 (textos, lector de pantalla, foco y aspecto) sin incidencias.
- Ajustes de cierre en specs: `passenger_map_view` 1.2 (N-03: sin insignia si no hay posición;
  N-01; N-05), `position_estimation` 1.3 (H-01…H-03), `passenger_stop_view` 1.3 (H-04 del arnés:
  presupuesto de bundle solo sobre un `dist/` recién construido). Aprobados en la PR #33.

## 2026-11-04 · CP-6 bloque 2 aprobado · PR #32 y #33 fusionadas · passenger_stop_view · done → implementing (v1.3)
- Ajustes previos al bloque 3: `passenger_stop_view` T-13 (H-04), `passenger_map_view` T-08,
  `position_estimation` T-10, cada una con revisión y PR propias.

## 2026-11-04 · passenger_stop_view v1.3 · implementing → in_review
- T-13: el presupuesto de bundle solo se comprueba con `npm run test:bundle` (build + test,
  `AVISABUS_BUNDLE_CHECK=1`), que `init.sh` ejecuta con y sin `--e2e`. Verify --e2e en verde.

## 2026-11-04 · passenger_stop_view v1.3 · in_review → done
- Revisión ciclo 1 de la v1.3: APPROVED (escenarios de `dist/` borrado, manipulado y fuente rota
  reproducidos). CP-4 propuesto para `docs/verification.md`. PR sin fusionar.

## 2026-11-04 · passenger_stop_view v1.3 PR #34 abierta · passenger_map_view · done → implementing (v1.2, T-08)

## 2026-11-04 · passenger_map_view v1.2 · implementing → in_review
- T-08: sin posición no se muestra insignia (`badge: null`); el e2e espera `moveend`/`zoomend` en lugar
  de `waitForTimeout(400)`. Verify --e2e en verde; e2e del mapa estable (54/54 ×2).

## 2026-11-04 · passenger_map_view v1.2 · in_review → done
- Revisión ciclo 1 de la v1.2: APPROVED (mutaciones de AC-05 y AC-10 detectadas). PR sin fusionar.

## 2026-11-04 · passenger_map_view v1.2 PR #35 abierta · position_estimation · done → implementing (v1.3, T-10)

## 2026-11-04 · position_estimation v1.3 · implementing → in_review
- T-10: tests de la segunda parada (mata el mutante `k <= 1`) y del `shape_id` del viaje en el log.
  Verify --e2e en verde (998 backend).

## 2026-11-04 · position_estimation v1.3 · in_review → done · ajustes previos al bloque 3 terminados
- Revisión ciclo 1 de la v1.3: APPROVED (16/16 mutantes). PRs #34, #35 y la de `position_estimation`
  v1.3 abiertas. Siguiente: specs del bloque 3 (spec-writer).

## 2026-11-04 · passenger_stop_view v1.3 PR #34 fusionada
- `feat/passenger_map_view-v1.2` (#35) y `feat/position_estimation-v1.3` (#36) actualizadas con `develop`
  y con `progress/` idéntico en ambas para que se fusionen sin conflicto en cualquier orden.

## 2026-11-04 · bloque 3 · spec_draft → spec_approved (CP-1)
- La persona aprueba la PR #37: `realtime_events`, `alert_create`, `alert_cancel`, `alert_expiry`
  y `passenger_alert_ui` v1.0, `stop_arrivals_api` 1.6, ADR-016 y los cambios de `docs/`.
  Decisiones: solicitud al autobús elegido, necesidad `VISUAL` y confirmación siempre.

## 2026-11-04 · PR #35, #36 y #37 fusionadas · bloque 3 · realtime_events · spec_approved → implementing
- Specs del bloque 3 aprobadas (CP-1, PR #37). Se implementa por orden con PR por feature.

## 2026-11-04 · realtime_events · implementing → spec_blocked (CP-3)
- T-01…T-05 hechas, verify en verde. AC-11: con uvicorn el cliente recibe `1012` (no `1001`) al apagar.
  La persona elige la opción (c): AC-11 admite `1001` o `1012`. Spec-writer para la v1.1.

- La v1.1 la aporta la persona en la PR #38; el borrador del spec-writer (PR #39) se cierra sin fusionar.

## 2026-11-04 · realtime_events · spec_blocked → spec_approved (v1.1, PR #38) → in_review
- Sin cambios de código: la implementación ya cumple AC-11 v1.1. Rama actualizada con `develop`.

## 2026-11-04 · realtime_events · in_review → done
- Revisión ciclo 1 (v1.1): APPROVED (28/33 mutantes detectados; los 5 restantes tocan una sola capa
  redundante del filtro de logs). PR sin fusionar.

## 2026-11-04 · realtime_events PR #40 abierta · alert_create · spec_approved → implementing
- Rama `feat/alert_create` apilada sobre `feat/realtime_events` (PR #40 sin fusionar).

## 2026-11-04 · alert_create · implementing → in_review
- T-01…T-06; `can_alert` con `alert_max_lead` (stop_arrivals_api 1.6, 3 tests adaptados). Verify --e2e
  en verde (1209 backend). Tres lecturas de la spec señaladas al reviewer (orden 200/404, AC-08, `last_seen_at`).

## 2026-11-04 · alert_create · in_review → done
- Revisión ciclo 1: APPROVED (31/33 mutantes, 2 equivalentes); las tres lecturas caben en la spec.

## 2026-11-04 · alert_create PR #41 abierta · alert_cancel · spec_approved → implementing

## 2026-11-04 · alert_cancel · implementing → in_review
- T-01…T-03 (`DELETE /alerts/{id}`, 204/404, evento `alert.cancelled`); H-1 de `alert_create` corregido
  (`no-store` en todos los 500). Verify --e2e en verde (1232 backend).

## 2026-11-04 · alert_cancel · in_review → done
- Revisión ciclo 1: APPROVED (15/17 mutantes, 2 equivalentes). PR sin fusionar.

## 2026-11-04 · alert_cancel PR #42 abierta · alert_expiry · spec_approved → exploring
- E-01: detección de paso con `stop_508_peak` y `gtfs_mini` → `progress/explore_passage.md`.

## 2026-11-04 · alert_expiry · exploring → implementing
- E-01 (`progress/explore_passage.md`): ventana de 2 min sin pasos prematuros; sin CP-3.

## 2026-11-04 · alert_expiry · implementing → in_review
- T-01…T-06; AC-11 con `stop_508_peak` coincide con E-01 (2 PASSED, 0 NEXT_STOP, 0 TIMEOUT).
  `GetStopArrivals.for_stop` añadido (autorizado). Verify --e2e en verde (1325 backend).

## 2026-11-04 · alert_expiry · in_review → done
- Revisión ciclo 1: APPROVED (21/21 mutaciones de producción detectadas; T-05 reproduce E-01).

## 2026-11-04 · alert_expiry PR #43 abierta · passenger_alert_ui · spec_approved → implementing

## 2026-11-05 · passenger_alert_ui · implementing → in_review
- T-01…T-08 (interrumpido una vez por el límite de uso y reanudado); verify --e2e en verde (555 Vitest,
  126 e2e, JS inicial 146,92 KB gzip). Decisiones D-1…D-12 a confirmar por el reviewer.

## 2026-11-05 · passenger_alert_ui · in_review → done · bloque 3 completo
- Revisión ciclo 1: APPROVED (25/28 mutantes; los 3 restantes son huecos de test con código correcto).
  PR sin fusionar, apilada sobre la #43. Bloque 3: 5/5 en `done` → CP-6.

## 2026-11-09 · bloque 3 · CP-6 aprobado (cierre del bloque)
- La persona prueba el bloque 3 con datos en tiempo real (solicitar, cancelar, caducidad, lector de
  pantalla) sin incidencias y sigue las recomendaciones: título del diálogo con el headsign GTFS
  (H-07) y LIM-02 documentada (traslado del viaje al autobús siguiente).
- Ajustes de cierre: `alert_expiry` 1.1, `alert_create` 1.1, `passenger_alert_ui` 1.1 (T-09),
  `realtime_events` 1.2 (T-06, `pytest-timeout`), `docs/` (LIM-02, limitador, guía §7).
  Aprobados en la PR #45.

## 2026-11-09 · bloque 4 · spec_draft → spec_approved (CP-1)
- La persona aprueba la PR #46: `driver_codes_cli`, `driver_session`, `driver_demand`, `driver_ui`
  y `driver_gps_simulator` v1.0, ADR-017 y ADR-018 y los cambios de `docs/`. Decisiones: el
  conductor elige su salida, la demanda cuenta solo su autobús, tono breve silenciable y resalte,
  y se mantiene la alerta de asientos.

## 2026-11-09 · Bloque 3 fusionado · CP-6 bloque 3 y CP-1 bloque 4 (PR #45, #46) · realtime_events · done → implementing (v1.2, T-06)
- Ajustes previos al bloque 4: `realtime_events` T-06 y `passenger_alert_ui` T-09; después, bloque 4 por orden.

## 2026-11-09 · realtime_events v1.2 · implementing → in_review
- T-06: `pytest-timeout` (30 s) y 47 esperas de WebSocket acotadas. Verify --e2e en verde (1325 backend).

## 2026-11-09 · realtime_events v1.2 · in_review → done
- Revisión ciclo 1 de la v1.2: APPROVED. Las ramas siguientes se apilan para evitar conflictos en `progress/`.

## 2026-11-09 · realtime_events v1.2 PR #47 abierta · passenger_alert_ui · done → implementing (v1.1, T-09)

## 2026-11-09 · passenger_alert_ui v1.1 · implementing → in_review
- T-09 (AC-11): el diálogo se cierra con `alert.registered`/`alert.delivered` y el foco va a "Cancelar
  solicitud". Verify --e2e en verde (563 Vitest, 126 e2e). Hueco señalado: `alerts.snapshot` con el diálogo abierto.

## 2026-11-09 · passenger_alert_ui v1.1 · in_review → done
- Revisión ciclo 1 de la v1.1: APPROVED (17 de 23 mutantes, 3 equivalentes, 3 huecos de test). PR sin fusionar.

## 2026-11-09 · passenger_alert_ui v1.1 PR abierta · bloque 4 · driver_codes_cli · spec_approved → implementing

## 2026-11-09 · driver_codes_cli · implementing → in_review
- T-01…T-04: `driver-codes create/list/revoke`, código solo como hash en la BD. Verify --e2e en verde (1409 backend).

## 2026-11-09 · driver_codes_cli · in_review → changes_requested → implementing (ciclo 2)
- Revisión ciclo 1: CHANGES_REQUESTED por F-01: un fallo de escritura distinto de `IntegrityError` imprime
  hash y etiqueta (parámetros de SQLAlchemy en la traza). Corrección: `hide_parameters=True` y test.

## 2026-11-09 · driver_codes_cli · implementing → in_review (ciclo 2)
- F-01 corregido (`hide_parameters=True`, tests con `OperationalError` real). Verify --e2e en verde (1413 backend).

## 2026-11-09 · driver_codes_cli · in_review → done
- Revisión ciclo 2: APPROVED (F-01 corregido y reproducido con el binario real; 21/22 mutantes).

## 2026-11-09 · driver_codes_cli PR abierta · driver_session · spec_approved → implementing

## 2026-11-09 · driver_session · implementing → in_review
- T-01…T-07; `list_lines`/`departures` añadidos a la red (autorizado). Verify --e2e en verde (1667 backend).
  Avisos: destinos de C2/C3 según la spec, IP en el log de acceso fuera de `/driver`, riesgo de AC-09 con GPS real.

## 2026-11-09 · driver_session · in_review → changes_requested → spec_blocked (CP-3)
- Revisión ciclo 1: CHANGES_REQUESTED. F-01 (AC-08, fechas extremas → 500) y P-01 (AC-09: la regla falla
  con trazados reales, saltos > 300 m con ruido GPS sintético en la mayoría de los 94 trazados).

## 2026-11-09 · driver_session · spec_blocked → spec_approved (v1.1, PR #50) → implementing (ciclo 2)
- AC-09 con ventana limitada por `20 m/s × Δt + 50 m`. Pendiente: F-01 (AC-08) y T-08. Rama actualizada con `develop`.

## 2026-11-09 · driver_session · implementing → spec_blocked (CP-3, T-08)
- F-01 corregido y N-02 cubierto. T-08 sin commit: `shape_dist_traveled` no son metros (factor 1,64–4,25,
  mediana 2,97) y, en metros reales, σ 10 m supera el umbral de AC-09. Afecta también a `position_estimation`.

## 2026-11-09 · CP-3 driver_session resuelto (PR #51) · position_estimation · done → implementing (v1.4, T-11)
- Distancias en metros reales (`feed_to_metres`). Después, T-08 de `driver_session` con la v1.2 (umbral 150 m).

## 2026-11-09 · position_estimation v1.4 · implementing → in_review
- T-11: `feed_to_metres`, forma siempre con `cumulative_distances`, `shape_distances` retirada. AC-17 sin
  cambios en sus recuentos (139/5). Verify --e2e en verde (1426 backend).

## 2026-11-09 · position_estimation v1.4 · in_review → done
- Revisión ciclo 1 de la v1.4: APPROVED (feed real: 8070 estimaciones coherentes; 15/19 mutantes). PR sin fusionar.

## 2026-11-09 · position_estimation v1.4 PR #52 abierta · driver_session · spec_blocked → implementing (v1.2)
- `feat/driver_session` actualizada con `develop` y con la rama de T-11 (PR #52 sin fusionar). Se remata T-08.

## 2026-11-09 · driver_session v1.2 · implementing → in_review (ciclo 2)
- F-01 y T-08 en metros reales; trazados reales dentro de 150 m con la semilla del test. Aviso: con otras semillas
  a σ 10 m correlado hay casos fuera (hasta 422 m por detrás). Verify --e2e y `slow` en verde (1711 backend).

## 2026-11-09 · driver_session · in_review → done
- Revisión ciclo 2 (v1.2): APPROVED (25/26 mutantes); N-05: el umbral de 150 m depende de la semilla.

## 2026-11-09 · driver_session PR #53 abierta · driver_demand · spec_approved → implementing

## 2026-11-10 · driver_demand · implementing → in_review → done
- Ciclo 1 CHANGES_REQUESTED (B-01: AC-08 sin tests de cierre `4429` y `1001` en `/ws/driver`); ciclo 2 APPROVED.
- `CI=1 ./init.sh verify --e2e` en verde: 1846 backend, 563 Vitest, 126 e2e. Abiertos N-01…N-08.

## 2026-11-10 · driver_demand PR #54 abierta · driver_ui · spec_approved → implementing

## 2026-11-10 · driver_ui · implementing → in_review → spec_blocked
- Ciclo 1 CHANGES_REQUESTED: B-01 (posición, `wakeLock` y socket se cortan tras fin de recorrido), B-02 (foco al cerrar el diálogo).
- CP-3 P-01: AC-04 "enviar la última cada 5 s" frente al cálculo de `STALE` con `last_position_at`.

## 2026-11-11 · CP-3 driver_ui resuelto (PR #55) · driver_session · done → implementing (v1.3, T-09)
- `driver_session` 1.3: `last_seen_at` (señal de vida, `IDLE`) y `last_fix_at` (fijo nuevo, `STALE`). `driver_ui` 1.1:
  reenvío cada 5 s y `getCurrentPosition` si `watchPosition` calla 10 s. `driver_ui` sigue `spec_blocked` hasta su ciclo 2.

## 2026-11-11 · driver_session v1.3 · implementing → in_review → done
- T-09: `last_seen_at` (`IDLE`) y `last_fix_at` (`STALE`); reenvíos sin proyección ni aviso. Contrato HTTP sin cambios.
- Revisión ciclo 1 de la v1.3: APPROVED (12/12 mutantes). Verify --e2e y `slow` en verde (1857 backend).

## 2026-11-11 · driver_session v1.3 PR #56 abierta · driver_ui · spec_blocked → implementing (v1.1, ciclo 2)
- `feat/driver_ui` actualizada con `feat/driver_session` (T-09 y specs v1.1). AC-04 v1.1, B-01 y B-02.

## 2026-11-11 · driver_ui v1.1 · implementing → in_review → done
- Ciclo 2 APPROVED: AC-04 v1.1 (reenvío 5 s, `getCurrentPosition` tras 10 s), B-01 (`useDriverShift`), B-02 (foco).
  Probado contra el backend real v1.3. Verify --e2e en verde (1857 backend, 660 Vitest, 132 e2e). P-05 → CP-4 (CU-08).

## 2026-11-11 · driver_ui PR #57 abierta · driver_gps_simulator · spec_approved → implementing

## 2026-11-11 · driver_gps_simulator v1.0 · implementing → in_review → done · bloque 4 completo
- Revisión ciclo 1 APPROVED (15/17 mutantes; ejecución real contra backend local: cierre siempre, sin filtrar código
  ni token). Verify --e2e en verde (1913 backend). N-05 de `driver_session` re-medido: fallan semillas 2 y 4. CP-6 pendiente.

## 2026-11-11 · PR #56, #57 y #58 fusionadas · bloque 4 · CP-6 aprobado (cierre del bloque)
- Demo de la persona en el Mac (Chrome DevTools, SAE real, línea 93): acceso, salida, próximas paradas, solicitud y
  entrega, fin de recorrido y siguiente salida, GPS perdido, fin de turno y simulador. Bloque 5 solo con la persona.

## 2026-11-11 · bloque 5 · deployment_rpi pending → spec_draft (y cierre de pendientes del bloque 4)
- Spec de `deployment_rpi` v1.0 en borrador. Decisiones de la persona: imágenes construidas en el
  Mac (Apple Silicon) y llevadas por SSH; Raspberry con Docker y NPM con dominio; SAE real con poco
  volumen y paso a `replay` sin reconstruir; GTFS renovado a mano con un comando y aviso de
  caducidad.
- Pendientes del bloque 4 resueltos en spec: `driver_session` 1.4 (criterio por percentil, giros
  en U), `driver_ui` 1.2 (textos, plurales, estado), `driver_codes_cli` 1.1 (`show_locals`),
  `passenger_map_view` 1.3 (fixtures), CU-08 (permiso antes de la salida), IP en logs →
  `deployment_rpi` AC-09. Aprobados por la persona en la PR #60.

## 2026-11-11 · PR #60 fusionada · driver_codes_cli · done → implementing (v1.1, T-05)
- Ajustes del bloque 4 por orden (`driver_codes_cli` T-05, `driver_session` T-10, `driver_ui` T-08, `passenger_map_view`
  T-09) y después `deployment_rpi`. `nfr_validation` la prepara la persona.

## 2026-11-11 · driver_codes_cli v1.1 · implementing → in_review → done
- T-05: `pretty_exceptions_show_locals=False` explícito y test de traza con el código en una variable local. Revisión
  ciclo 1 APPROVED (mutante `True` detectado; N-10 el test del fuente acepta un comentario). Verify --e2e en verde.

## 2026-11-11 · driver_codes_cli PR #61 abierta · driver_session · done → implementing (v1.4, T-10)
