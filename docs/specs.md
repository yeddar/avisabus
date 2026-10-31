# Specs — formato e índice

> Estado: **APROBADO** (v1.0 · 2026-10-31). Define cómo se escriben las specs de `specs/<feature>/`.

## 1. Principios (spec first)

1. Ninguna línea de código de producción sin spec `APPROVED` (CHECKPOINTS CP-1).
2. La spec es el **contrato**: el implementer no la cambia; si está mal, se bloquea (CP-3) y se corrige.
3. Trazabilidad completa: `RF/RNF (docs) → AC (requirements.md) → tarea (tasks.md) → test`.
4. Cada AC es verificable automáticamente; las excepciones se justifican.

## 2. Estructura de cada feature

```
specs/<feature_id>/
├── requirements.md   # QUÉ: alcance, historias, criterios de aceptación EARS, trazabilidad
├── design.md         # CÓMO: componentes, interfaces, datos, errores, configuración, tests
└── tasks.md          # PASOS: exploración (si aplica) y tareas atómicas ordenadas
```

Cabecera obligatoria en los tres ficheros:

```markdown
# <Título> — <requirements|design|tasks>
> Feature: `<feature_id>` · Versión: x.y · Estado: DRAFT | APPROVED
> Requisitos: RF-xx, RNF-yy · Casos de uso: CU-zz · Depende de: <ids>
```

## 3. `requirements.md`

Secciones: **Contexto**, **Alcance**, **Fuera de alcance**, **Historias de usuario** (si aplica),
**Criterios de aceptación**, **Trazabilidad**.

### Criterios de aceptación en EARS (castellano)

| Patrón | Plantilla |
|---|---|
| Ubicuo | `EL SISTEMA DEBERÁ <respuesta>.` |
| Evento | `CUANDO <disparador>, EL SISTEMA DEBERÁ <respuesta>.` |
| Estado | `MIENTRAS <estado>, EL SISTEMA DEBERÁ <respuesta>.` |
| No deseado | `SI <condición>, ENTONCES EL SISTEMA DEBERÁ <respuesta>.` |
| Opcional | `DONDE <característica>, EL SISTEMA DEBERÁ <respuesta>.` |
| Complejo | `MIENTRAS <estado>, CUANDO <disparador>, EL SISTEMA DEBERÁ <respuesta>.` |

"EL SISTEMA" puede concretarse en el componente (`LA CLI`, `LA API`, `LA VISTA DE PARADA`…).

Formato de cada AC:

```markdown
- **<feature_id>.AC-01** — CUANDO …, EL SISTEMA DEBERÁ …
  *Verificación:* unit | integration | e2e | gate | revisión | manual (detalle)
```

| Tipo | Significado | ¿Exige test que cite el AC? |
|---|---|---|
| `unit`, `integration`, `e2e` | Test automático | **Sí** (lo comprueba `scripts/check_traceability.py`) |
| `gate` | Lo cubre un paso de `./init.sh verify` (lint, tipos, build…) | No |
| `revisión` | Lo comprueba el reviewer leyendo código o configuración | No |
| `manual` | Medición o acción humana; la evidencia queda en `progress/` | No |

Si una línea combina tipos (p. ej. `unit + revisión`), basta con que aparezca uno automático
para que se exija el test.

## 4. `design.md`

Secciones (omitir las que no apliquen, nunca dejar vacías):
1. **Resumen** de la solución.
2. **Componentes** afectados por capa (domain / application / adapters / background / frontend).
3. **Interfaces**: firmas exactas (Python con tipos; TS con tipos), endpoints, eventos, comandos CLI.
4. **Datos**: tablas, ficheros, formatos, ejemplos.
5. **Flujos**: secuencia (mermaid si ayuda).
6. **Errores**: qué se lanza / qué se devuelve.
7. **Configuración**: variables `AVISABUS_*` nuevas, con default.
8. **Estrategia de test**: fixtures, fakes, qué AC cubre cada tipo de test.
9. **Decisiones locales permitidas**: lo que el implementer puede decidir.
10. **Preguntas abiertas** (deben estar vacías para aprobar, salvo las delegadas a exploración).

## 5. `tasks.md`

```markdown
## Exploración            (solo si hace falta; la hace el explorer antes de implementar)
- E-01 — <pregunta concreta> → progress/explore_<tema>.md

## Tareas
- [ ] **T-01** — <acción concreta>
  - AC: <feature>.AC-01, AC-02
  - Ficheros: `backend/src/avisabus/...`
  - Verificación: `cd backend && uv run pytest tests/unit/test_x.py`
```

Reglas: tareas de ≤ ~1 h de trabajo de agente; ordenadas por dependencia; la última tarea es
siempre "Verificación completa" (`./init.sh verify`). Cada AC aparece en al menos una tarea.

## 6. Versionado

- `DRAFT` → `APPROVED` lo decide la persona (CP-1).
- Cualquier cambio posterior a la aprobación: subir versión (`1.0 → 1.1`), volver a `DRAFT`,
  añadir al final de `requirements.md` una sección **Historial** con el cambio y su motivo.

## 7. Índice de features

| # | Feature | Bloque | Spec |
|---|---|---|---|
| 1 | `project_scaffold` | 1 | [specs/project_scaffold](../specs/project_scaffold/) |
| 2 | `gtfs_import` | 1 | [specs/gtfs_import](../specs/gtfs_import/) |
| 3 | `stop_tokens_qr` | 1 | [specs/stop_tokens_qr](../specs/stop_tokens_qr/) |
| 4 | `sae_arrivals_source` | 1 | [specs/sae_arrivals_source](../specs/sae_arrivals_source/) |
| 5 | `occupancy_sensor` | 1 | [specs/occupancy_sensor](../specs/occupancy_sensor/) |
| 6 | `stop_arrivals_api` | 1 | [specs/stop_arrivals_api](../specs/stop_arrivals_api/) |
| 7 | `frontend_i18n` | 2 | [specs/frontend_i18n](../specs/frontend_i18n/) |
| 8 | `passenger_stop_view` | 2 | [specs/passenger_stop_view](../specs/passenger_stop_view/) |
| 9 | `position_estimation` | 2 | [specs/position_estimation](../specs/position_estimation/) |
| 10 | `passenger_map_view` | 2 | [specs/passenger_map_view](../specs/passenger_map_view/) |
| 11 | `realtime_events` | 3 | pendiente |
| 12 | `alert_create` | 3 | pendiente |
| 13 | `alert_cancel` | 3 | pendiente |
| 14 | `alert_expiry` | 3 | pendiente |
| 15 | `passenger_alert_ui` | 3 | pendiente |
| 16 | `driver_codes_cli` | 4 | pendiente |
| 17 | `driver_session` | 4 | pendiente |
| 18 | `driver_demand` | 4 | pendiente |
| 19 | `driver_ui` | 4 | pendiente |
| 20 | `driver_gps_simulator` | 4 | pendiente |
| 21 | `deployment_rpi` | 5 | pendiente |
| 22 | `nfr_validation` | 5 | pendiente |

El estado vivo de cada feature está en `feature_list.json` (`./init.sh status`).
