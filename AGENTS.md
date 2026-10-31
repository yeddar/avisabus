# AGENTS.md — Cómo trabajan los agentes en AvisaBus

Este fichero es obligatorio para cualquier agente que trabaje en el repositorio.
`CLAUDE.md` lo importa. Si algo aquí contradice a una instrucción puntual de una persona,
manda la persona; si contradice a `CHECKPOINTS.md`, manda `CHECKPOINTS.md`.

## 1. Qué es este proyecto

AvisaBus: PWA para pasajeros y conductores de EMT València (ver `README.md`). Se desarrolla con
**Spec Driven Development, spec first**: **no se escribe código de producción sin una spec
aprobada** en `specs/<feature>/`.

## 2. Jerarquía de fuentes de verdad

1. `docs/vision.md` → `docs/requirements.md` → `docs/use_cases.md` → `docs/architecture.md` → `docs/conventions.md`
2. `specs/<feature>/requirements.md` → `design.md` → `tasks.md` (deben ser coherentes con `docs/`)
3. Código y tests (deben ser coherentes con la spec)

Si detectas una contradicción entre niveles, **no la resuelvas por tu cuenta**: anótala en tu
fichero de `progress/` en la sección "Bloqueos" y detente (ver `CHECKPOINTS.md` CP-3).

## 3. Roles

| Rol | Definición | Escribe en | Nunca toca |
|---|---|---|---|
| **Orquestador** | Sesión principal de Claude Code | `feature_list.json`, `progress/current.md`, `progress/history.md` | Código, specs, `docs/` |
| **explorer** | `.claude/agents/explorer.md` | `progress/explore_<tema>.md` (+ `progress/explore_<tema>_samples/`) | Todo lo demás (solo lectura) |
| **spec-writer** | `.claude/agents/spec-writer.md` | `specs/<feature>/*` | Código, `docs/` |
| **implementer** | `.claude/agents/implementer.md` | `backend/`, `frontend/`, `deploy/`, `progress/impl_<feature>.md` | `specs/`, `docs/`, `feature_list.json` |
| **reviewer** | `.claude/agents/reviewer.md` | `progress/review_<feature>.md` | Todo lo demás (solo lectura + ejecutar verificación) |

Los cambios en `docs/` solo los hace una persona (o un agente con su permiso explícito en la
conversación). Los agentes los **proponen** en su fichero de progreso.

## 4. Ciclo de vida de una feature

Estados en `feature_list.json` (`status`):

```
pending ─▶ spec_draft ─▶ spec_approved ─▶ exploring ─▶ implementing ─▶ in_review ─▶ done
               ▲   ✋CP-1                     │                ▲              │
               │                              │                └──────────────┤ changes_requested
               └──────── spec_blocked ◀───────┴─────────────── (✋CP-3) ◀──────┘ (máx. 2 ciclos → ✋CP-2)
```

| Transición | Quién | Condición |
|---|---|---|
| `pending → spec_draft` | spec-writer | Dependencias con spec al menos en `spec_draft` |
| `spec_draft → spec_approved` | **Persona** (CP-1) | Las tres cabeceras de la spec dicen `Estado: APPROVED` |
| `spec_approved → exploring` | Orquestador | Todas las features de `depends_on` en `done` |
| `exploring → implementing` | Orquestador | Existe `progress/explore_*.md` relevante o la spec indica que no hace falta explorar |
| `implementing → in_review` | Orquestador | `progress/impl_<feature>.md` marca todas las tareas `[x]` y `./init.sh verify` pasa |
| `in_review → done` | Orquestador | `progress/review_<feature>.md` con veredicto `APPROVED` |
| `in_review → changes_requested → implementing` | Orquestador | Veredicto `CHANGES_REQUESTED`; incrementa `review_cycles` |
| `* → spec_blocked` | Cualquiera | Spec ambigua, incorrecta o contradictoria → CP-3 |

Al pasar a `done`: `passes = true` y entrada en `progress/history.md`.

## 5. Protocolo de sesión (orquestador)

**Al empezar:**
1. Lee `progress/current.md`, `feature_list.json` (`./init.sh status`) y `CHECKPOINTS.md`.
2. Comprueba si hay algún checkpoint humano pendiente. Si lo hay, **pregunta y espera**.
3. Elige la siguiente feature: la de menor `order` con estado accionable y dependencias en `done`.

**Durante:** delega en subagentes; no implementes tú. Un subagente por fase. Pasa a cada
subagente solo el `feature_id` y las rutas relevantes; el subagente lee el resto.

**Al terminar (o antes de que se agote el contexto):**
1. Actualiza `feature_list.json`.
2. Reescribe `progress/current.md` (estado actual, siguiente paso, bloqueos).
3. Añade una entrada a `progress/history.md` (append-only).

## 6. Reglas para todos los agentes

- **Spec first:** el implementer solo trabaja sobre specs `APPROVED` y solo hace lo que dice `tasks.md`.
- **Sin improvisar contratos:** si la spec no cubre un caso, se para y se anota; no se inventa comportamiento.
- **TDD:** cada criterio de aceptación (`<feature>.AC-n`) tiene al menos un test que lo cita (ver `docs/conventions.md` §6). Primero el test (en rojo), luego el código.
- **Sin red ni reloj real en tests.** El SAE, el GTFS y el tiempo se simulan con fixtures, replay y `FakeClock`.
- **Arquitectura hexagonal:** `domain/` no importa nada externo; lo verifica `uv run lint-imports`.
- **Accesibilidad e i18n no son opcionales** en ninguna feature de frontend.
- **Privacidad:** nunca registres `device_id`, códigos de conductor ni necesidades asociadas a un identificador.
- **Verificación:** nada pasa a revisión sin `./init.sh verify` en verde.
- **Alcance:** no refactorices código ajeno a la feature salvo que una tarea lo pida.
- **Idiomas:** código en inglés; specs, docs y progreso en castellano.

## 7. Formato de los ficheros de progreso

### `progress/explore_<tema>.md`
```markdown
# Exploración: <tema>
Feature(s): <ids> · Fecha: AAAA-MM-DD · Agente: explorer
## Pregunta(s)
## Hallazgos            (con evidencias: rutas, fragmentos, comandos ejecutados)
## Impacto en la spec   (qué hay que añadir/cambiar y dónde)
## Riesgos
## Recomendación
```

### `progress/impl_<feature>.md`
```markdown
# Implementación: <feature>
Spec: specs/<feature>/ (versión aprobada) · Ciclo de revisión: n
## Tareas
- [x] T-01 … (commit abc123)
- [ ] T-02 …
## Decisiones locales     (dentro de lo que permite el design)
## Bloqueos               (contradicciones o huecos de la spec → CP-3)
## Verificación           (salida resumida de ./init.sh verify)
```

### `progress/review_<feature>.md`
```markdown
# Revisión: <feature>
Ciclo: n · Fecha · Agente: reviewer
## Veredicto: APPROVED | CHANGES_REQUESTED
## Matriz AC → evidencia
| AC | Test(s) | Resultado | Nota |
## Verificación ejecutada  (comandos y resultado)
## Hallazgos              (bloqueantes / no bloqueantes, con fichero:línea)
```

### `progress/current.md`
Estado vivo: fase actual, feature en curso, último paso, siguiente paso, checkpoints pendientes.

### `progress/history.md`
Registro cronológico **append-only**: fecha, feature, transición, resumen en 1–3 líneas.
