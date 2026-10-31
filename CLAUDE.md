# CLAUDE.md

@AGENTS.md

## Específico de Claude Code

### Eres el orquestador
En la sesión principal actúas como **orquestador** (AGENTS.md §3 y §5). No implementas ni
redactas specs: delegas en los subagentes con la herramienta de agentes.

| Fase | Subagente (`subagent_type`) | Prompt mínimo |
|---|---|---|
| Redactar / corregir spec | `spec-writer` | `Feature: <id>. Redacta (o corrige según <motivo>) specs/<id>/.` |
| Explorar | `explorer` | `Feature: <id>. Explora: <preguntas de la sección "Exploración" de tasks.md>.` |
| Implementar | `implementer` | `Feature: <id>. Implementa specs/<id>/tasks.md. Ciclo de revisión: <n>.` |
| Revisar | `reviewer` | `Feature: <id>. Revisa la implementación contra specs/<id>/. Ciclo: <n>.` |

Lanza el **reviewer siempre como agente nuevo** (nunca continúes la conversación del
implementer): la independencia de la revisión es un requisito del proceso.

Ejecuta los subagentes de uno en uno y en primer plano: cada fase depende de la anterior.

### Comandos
- Estado: `./init.sh status`
- Verificación completa: `./init.sh verify`
- Backend: ver `docs/conventions.md` §8.

### Checkpoints
Antes de cualquier transición marcada con ✋ en AGENTS.md §4, **detente y pregunta a la persona**
(ver `CHECKPOINTS.md`). No marques specs como `APPROVED` tú mismo.

### Contexto
Si el contexto se está llenando, actualiza `progress/current.md` y `progress/history.md` antes de
continuar o de pedir a la persona que abra una sesión nueva.
