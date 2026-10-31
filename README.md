# AvisaBus

Aplicación web accesible para pasajeros y conductores de **EMT València**:

- El **pasajero** escanea el QR de su parada y ve cuánto falta para cada línea, por dónde va el
  autobús (posición estimada) y cómo de lleno viene. Puede **avisar al conductor** de que le
  espera, indicando si necesita rampa, más tiempo para subir o asiento.
- El **conductor** ve en una tablet cuánta gente le espera en sus próximas paradas, quién necesita
  ayuda para subir, y recibe una alerta si no va a caber todo el mundo.

Proyecto académico (TFM) desarrollado con **Spec Driven Development (spec first)** y agentes IA
(Claude Code).

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/vision.md`](docs/vision.md) | Contexto, problema, actores, decisiones, objetivos |
| [`docs/requirements.md`](docs/requirements.md) | Requisitos funcionales y no funcionales |
| [`docs/use_cases.md`](docs/use_cases.md) | Casos de uso y limitaciones conocidas |
| [`docs/architecture.md`](docs/architecture.md) | Arquitectura, API, despliegue, ADR, riesgos |
| [`docs/conventions.md`](docs/conventions.md) | Convenciones de código, glosario, tests, git |
| [`docs/specs.md`](docs/specs.md) | Formato de las specs e índice de features |
| [`docs/verification.md`](docs/verification.md) | Definición de terminado y proceso de revisión |
| [`AGENTS.md`](AGENTS.md) | Roles de los agentes y flujo de trabajo |
| [`CHECKPOINTS.md`](CHECKPOINTS.md) | Puntos de control humanos |
| [`feature_list.json`](feature_list.json) | Estado de cada feature |

## Estructura

```
.
├── AGENTS.md · CLAUDE.md · CHECKPOINTS.md · README.md
├── .claude/agents/          # Subagentes de Claude Code (explorer, spec-writer, implementer, reviewer)
├── docs/                    # Fuente de verdad global (visión → requisitos → arquitectura)
├── specs/<feature>/         # requirements.md · design.md · tasks.md
├── progress/                # Memoria de trabajo de los agentes
├── feature_list.json        # Estado de las features
├── init.sh                  # setup · verify · dev · status
├── backend/                 # Python 3.12 · FastAPI · SQLite (hexagonal)
├── frontend/                # React · TypeScript · Vite · PWA
├── deploy/                  # docker compose · nginx (web)
└── data/                    # (git-ignored) feed GTFS real, base de datos local
```

## Inicio rápido

```bash
./init.sh setup     # instala dependencias de backend y frontend
./init.sh status    # estado de las features
./init.sh verify    # lint + tipos + tests + arquitectura (lo mismo que exige la revisión)
./init.sh dev       # backend en :8000 y frontend en :5173
```

Coloca el feed GTFS de EMT descomprimido en `data/gtfs/emt/` (no se versiona).

## Fuentes de datos

Datos de red: GTFS de EMT València. Tiempos de llegada: sistema SAE de EMT València.
Datos abiertos del Ajuntament de València. Mapas © colaboradores de OpenStreetMap.
