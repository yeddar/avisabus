# AvisaBus

Aplicación web progresiva (PWA) accesible que conecta a los **pasajeros** y a los **conductores**
de EMT València:

- El **pasajero** escanea el código QR de su parada y ve, sin registrarse ni instalar nada,
  cuánto falta para cada línea, por dónde va el autobús y cómo de lleno viene. Si lo necesita,
  **avisa al conductor** de que le espera e indica si necesita rampa, más tiempo para subir o un
  asiento.
- El **conductor** ve en una tablet cuántas personas le esperan en sus próximas paradas y quién
  necesita ayuda para subir. Recibe una alerta si no va a caber todo el mundo.

Es un proyecto académico (Trabajo Fin de Máster) desarrollado con **Spec Driven Development
(spec first)** y agentes de IA (Claude Code). Ninguna línea de código de producción se ha escrito
sin una especificación aprobada antes por una persona.

> **Estado (noviembre de 2026).** 21 de las 22 features están terminadas, revisadas y
> desplegadas. Falta `nfr_validation`: pruebas de carga, accesibilidad y tiempos de respuesta.
> **EMT retiró el 12 de noviembre de 2026 la página pública `QR.php`** de la que AvisaBus leía
> los tiempos de llegada en tiempo real. Desde entonces la aplicación usa el horario del GTFS e
> indica "Sin datos en tiempo real", que es el comportamiento de respaldo previsto (RF-09). Para
> demostrar el tiempo real se usa una sesión real grabada (`AVISABUS_ARRIVALS_SOURCE=replay`, ver
> [Tiempo real](#tiempo-real-sae-y-modo-replay)). El análisis está en
> [`progress/explore_sae_v2.md`](progress/explore_sae_v2.md).

## Contenido

- [Funcionalidades](#funcionalidades)
- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Requisitos previos](#requisitos-previos)
- [Instalación](#instalación)
- [Ejecución en local](#ejecución-en-local)
- [Verificación y tests](#verificación-y-tests)
- [Despliegue](#despliegue)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Metodología: Spec Driven Development con agentes](#metodología-spec-driven-development-con-agentes)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Fuentes de datos y atribución](#fuentes-de-datos-y-atribución)

## Funcionalidades

### Pasajero (móvil, a través del QR de la parada)

| Funcionalidad | Requisitos |
|---|---|
| Vista de parada por QR firmado (HMAC): nombre de la parada y líneas que pasan | RF-05, RF-06 |
| Próximas llegadas en tiempo real (SAE de EMT, caché de 20 s), con refresco automático | RF-07, RF-08, RF-10, RF-11 |
| Respaldo con el horario programado del GTFS cuando no hay tiempo real, indicado en pantalla | RF-09 |
| Mapa con el trazado de la línea y la posición estimada del autobús | RF-12, RF-13 |
| Nivel de ocupación de cada autobús (libre, medio, lleno) y asientos libres | RF-14, RF-15 |
| Aviso al conductor ("espero la línea X") para el autobús elegido, con necesidades opcionales | RF-16, RF-17, RF-20 |
| Perfil de accesibilidad guardado solo en el dispositivo | RF-18 |
| Un aviso activo por dispositivo, parada y línea; cancelación; confirmación de entrega | RF-19, RF-22, RF-23 |
| Caducidad automática: cuando el autobús pasa, al llegar a la parada siguiente o por tiempo | RF-21 |

### Conductor (tablet)

| Funcionalidad | Requisitos |
|---|---|
| Acceso con código de conductor (sin cuentas ni contraseñas) | RF-24 |
| Elección de línea, sentido y salida (expedición) | RF-25 |
| Próximas paradas calculadas a partir del GPS de la tablet | RF-26 |
| Personas esperando en las 3 próximas paradas y sus necesidades, en tiempo real (WebSocket) | RF-27, RF-28 |
| Alerta de capacidad cuando no van a caber todos | RF-29 |
| Fin de turno, que borra la sesión y la posición | RF-30 |

### Administración (CLI `avisabus`)

| Comando | Para qué sirve |
|---|---|
| `avisabus gtfs import <zip o carpeta>` / `gtfs info` | Importar o renovar el feed GTFS de EMT y consultar su vigencia |
| `avisabus qr generate --stop <id> \| --all` | Generar los QR de las paradas (SVG o PNG) y su `index.csv` con las URL |
| `avisabus driver-codes create --label <texto>` / `list` / `revoke` | Gestionar los códigos de acceso de los conductores |
| `avisabus simulate --line <L> --direction <D>` | Simular el recorrido GPS de un conductor por el trazado real de una línea |
| `avisabus sae fetch` / `sae record` | Consultar el SAE y grabar sesiones reales para reproducirlas |
| `avisabus occupancy override` | Forzar el nivel de ocupación de una línea (demostraciones) |
| `avisabus openapi export` | Exportar el contrato OpenAPI con el que se generan los tipos del frontend |

### Transversales

- **Accesibilidad (WCAG 2.1 AA):** comprobada con axe en los tests end-to-end. Zonas táctiles de
  44 px o más, lectores de pantalla y tipografía Atkinson Hyperlegible.
- **Idiomas:** castellano y valenciano, con selector en la interfaz. Los nombres de paradas y
  líneas se muestran tal como vienen en el GTFS.
- **PWA:** instalable y con *service worker*. Pensada para Safari iOS y Chrome Android, y los
  tests end-to-end se ejecutan con perfiles de iPhone, Pixel y iPad.
- **Privacidad por diseño:** sin cuentas ni datos personales. El dispositivo se identifica con un
  hash, las necesidades de accesibilidad se borran cuando caduca el aviso y ningún log guarda IP
  ni identificadores.
- **Seguridad:** HTTPS, tokens de parada firmados, límite de peticiones por dispositivo e IP y
  bloqueo tras varios códigos de conductor erróneos.

## Arquitectura

Monolito modular con **arquitectura hexagonal (puertos y adaptadores)**: el dominio no conoce
HTTP, SQL ni el SAE, y toda fuente externa (SAE, ocupación, GPS, reloj) entra por un puerto. Un
único proceso sirve la API REST, los WebSockets y las tareas de fondo, con SQLite y eventos en
memoria (ADR-003). La CLI comparte el mismo paquete.

```mermaid
flowchart LR
  P([Pasajero<br/>móvil, vía QR]) -->|HTTPS| WEB
  C([Conductor<br/>tablet]) -->|HTTPS + WSS| WEB
  A([Administrador]) -->|CLI| BE
  subgraph Servidor[Raspberry Pi · Docker Compose]
    WEB[web<br/>nginx: PWA + proxy /api y /ws]
    BE[backend<br/>FastAPI · uvicorn<br/>tareas de fondo]
    DB[(SQLite · WAL)]
    WEB --> BE --> DB
  end
  BE -->|HTTP| SAE[(SAE EMT València)]
  BE -.->|importación| GTFS[(GTFS EMT)]
  P & C -->|teselas| OSM[(OpenStreetMap)]
```

El detalle (capas, API, eventos, modelo de datos, ADR y riesgos) está en
[`docs/architecture.md`](docs/architecture.md).

## Stack tecnológico

| Capa | Tecnologías |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2 y pydantic-settings, SQLAlchemy 2 sobre SQLite (WAL), httpx, structlog (logs JSON), Typer (CLI), segno y Pillow (QR) |
| **Frontend** | React 19, TypeScript, Vite, React Router, TanStack Query, i18next, Leaflet y React Leaflet, Tailwind CSS 4, vite-plugin-pwa |
| **Calidad backend** | uv, pytest (con pytest-asyncio, Hypothesis y pytest-socket para impedir la red), Ruff, mypy, import-linter (reglas de la arquitectura hexagonal) |
| **Calidad frontend** | Vitest y Testing Library, Playwright con axe-core (end-to-end y accesibilidad), ESLint (con jsx-a11y e i18next), Prettier, tipos generados desde OpenAPI |
| **Despliegue** | Docker Compose, imágenes `linux/arm64`, nginx (contenedor `web`), Nginx Proxy Manager (TLS) en una Raspberry Pi |
| **Desarrollo** | Claude Code con subagentes (explorer, spec-writer, implementer, reviewer), GitHub (ramas y pull requests) |

## Requisitos previos

- **Python 3.12** y **[uv](https://docs.astral.sh/uv/)**
- **Node.js 22 o superior** y npm
- **Docker** con Compose y buildx, solo para construir las imágenes de producción. En macOS
  sirve, por ejemplo, Colima.
- El **feed GTFS de EMT València** (zip), publicado en los datos abiertos del Ajuntament de
  València. No se versiona en el repositorio.

## Instalación

```bash
git clone https://github.com/yeddar/avisabus.git
cd avisabus
./init.sh setup                         # uv sync, npm ci, crea data/ y .env desde .env.example
(cd frontend && npx playwright install chromium webkit)   # solo para los tests end-to-end
```

Coloca el feed GTFS descomprimido en `data/gtfs/emt/` e impórtalo en la base de datos local
(`data/avisabus.sqlite`):

```bash
cd backend
uv run avisabus gtfs import ../data/gtfs/emt
uv run avisabus gtfs info               # comprueba la vigencia del feed
cd ..
```

La configuración se hace con variables `AVISABUS_*` en el fichero `.env` de la raíz. Todas
tienen un valor por defecto seguro para desarrollo y están documentadas en
[`.env.example`](.env.example).

## Ejecución en local

```bash
./init.sh dev       # backend en http://localhost:8000 y frontend en http://localhost:5173
```

El servidor de desarrollo de Vite reenvía `/api` y `/ws` al backend.

**Como pasajero**, abre la URL firmada de una parada. Para obtenerla, genera su QR (la URL queda
en `index.csv`) y ábrela en el navegador o escanéala con el móvil:

```bash
cd backend
uv run avisabus qr generate --stop 508 --out ../data/qr-dev
cat ../data/qr-dev/index.csv            # http://localhost:5173/p/508?t=<token>
```

**Como conductor**, crea un código y entra en `http://localhost:5173/driver`:

```bash
uv run avisabus driver-codes create --label "Tablet de pruebas"
```

En un ordenador sin GPS, la posición se puede fijar con las herramientas de desarrollo del
navegador (Chrome: *Sensors → Location*). El simulador recorre una línea completa sin
interfaz con un código de conductor; es útil para ver los avisos llegar sin moverse:

```bash
AVISABUS_SIM_CODE=<código> uv run avisabus simulate --line 93 --direction 0
```

### Tiempo real: SAE y modo replay

La fuente de tiempos de llegada se elige con `AVISABUS_ARRIVALS_SOURCE`:

| Valor | Comportamiento |
|---|---|
| `http` (por defecto en dev y prod) | Consulta el SAE de EMT. Desde el 12/11/2026 la página ya no existe, así que se cae siempre al horario del GTFS. |
| `replay` (por defecto en tests) | Reproduce una sesión real grabada en hora punta (`stop_508_peak`, parada 508). Es la opción para demostraciones. |

```bash
# en .env
AVISABUS_ARRIVALS_SOURCE=replay
```

## Verificación y tests

```bash
./init.sh verify          # formato, lint, tipos, arquitectura y tests de backend y frontend
./init.sh verify --e2e    # además, tests end-to-end con Playwright y axe
./init.sh verify-deploy   # construye las imágenes de producción y las inspecciona (requiere Docker)
./init.sh status          # estado de cada feature según feature_list.json
```

- **Sin red ni reloj real:** pytest bloquea los sockets, el SAE se simula con grabaciones reales
  y el tiempo con un reloj falso. Así los tests son deterministas.
- **Trazabilidad:** cada criterio de aceptación de las specs (`<feature>.AC-n`) tiene al menos un
  test que lo cita, y `scripts/check_traceability.py` lo comprueba.
- **Cobertura:** mínimo del 80 % en `domain` y `application`.
- **Revisión:** ninguna feature se da por terminada sin `./init.sh verify` en verde y la revisión
  de un agente independiente ([`docs/verification.md`](docs/verification.md)).

## Despliegue

Producción en una **Raspberry Pi (arm64)** con Docker Compose, detrás de un Nginx Proxy Manager
que termina TLS:

- Las imágenes se construyen en el Mac y se envían por SSH con `deploy/ship.sh`, que admite
  `--rollback`.
- El GTFS se renueva con `deploy/gtfs-update.sh`.
- `deploy/smoke.sh <url>` comprueba el despliegue: rutas, cabeceras de seguridad, caché y
  WebSocket.

La guía completa (primer despliegue, actualizaciones, copias de seguridad y logs) está en
[`deploy/README.md`](deploy/README.md).

## Estructura del repositorio

```
.
├── README.md · AGENTS.md · CLAUDE.md · CHECKPOINTS.md
├── docs/                     # Fuente de verdad: visión → requisitos → casos de uso → arquitectura
├── specs/<feature>/          # Una spec por feature: requirements.md · design.md · tasks.md
├── progress/                 # Memoria de trabajo de los agentes: exploraciones, implementación, revisiones
├── feature_list.json         # Estado de cada feature (ciclo de vida spec → done)
├── init.sh                   # setup · dev · verify · verify-deploy · status
├── .claude/agents/           # Definición de los subagentes de Claude Code
├── backend/
│   ├── src/avisabus/
│   │   ├── domain/           # Modelos, servicios y puertos (sin dependencias externas)
│   │   ├── application/      # Casos de uso
│   │   ├── adapters/
│   │   │   ├── inbound/      # http (FastAPI), ws (WebSockets), cli (Typer)
│   │   │   └── outbound/     # gtfs, sae, persistence, occupancy, qr, security, events…
│   │   ├── background/       # Tareas periódicas (avisos, turnos, caducidad del GTFS, estadísticas del SAE)
│   │   └── main.py           # Composición de la aplicación
│   └── tests/                # unit · integration · fixtures (GTFS reducido, grabaciones del SAE)
├── frontend/
│   ├── src/
│   │   ├── features/passenger/   # Vista de parada, mapa, avisos, perfil de necesidades
│   │   ├── features/driver/      # Acceso, elección de salida, turno y demanda
│   │   ├── shared/               # API tipada, componentes de interfaz, utilidades
│   │   └── locales/              # es · ca-valencia
│   └── e2e/                  # Playwright + axe
├── deploy/                   # compose.yaml, nginx, ship.sh, gtfs-update.sh, smoke.sh, guía
├── scripts/                  # Comprobación de trazabilidad AC → tests
└── data/                     # (no versionado) GTFS, base de datos local
```

## Metodología: Spec Driven Development con agentes

Cada funcionalidad (*feature*) sigue el mismo ciclo, con puntos de control humanos
([`CHECKPOINTS.md`](CHECKPOINTS.md)):

```
pending → spec_draft →(aprobación humana)→ spec_approved → exploring → implementing → in_review → done
```

1. **spec-writer** redacta la spec de la feature a partir de `docs/`: requisitos con criterios de
   aceptación en formato EARS, diseño y tareas. **Una persona la revisa y la aprueba.**
2. **explorer** investiga lo necesario antes de implementar: datos reales del GTFS y del SAE,
   código existente, librerías.
3. **implementer** implementa con TDD exactamente lo que dicen las tareas. Si la spec no cubre
   un caso, se detiene y lo anota.
4. **reviewer**, un agente nuevo sin el contexto del implementer, comprueba cada criterio de
   aceptación con evidencias y emite un veredicto.
5. Cada feature se integra mediante una pull request que fusiona una persona.

| Documento | Contenido |
|---|---|
| [`docs/vision.md`](docs/vision.md) | Contexto, problema, actores, objetivos |
| [`docs/requirements.md`](docs/requirements.md) | Requisitos funcionales (RF-01…RF-35) y no funcionales (RNF-01…RNF-15) |
| [`docs/use_cases.md`](docs/use_cases.md) | Casos de uso y limitaciones conocidas |
| [`docs/architecture.md`](docs/architecture.md) | Arquitectura, API, despliegue, ADR, riesgos |
| [`docs/conventions.md`](docs/conventions.md) | Convenciones de código, glosario, tests, git |
| [`docs/design.md`](docs/design.md) | Guía visual: tipografía, color, componentes y textos |
| [`docs/specs.md`](docs/specs.md) | Formato de las specs e índice de features |
| [`docs/verification.md`](docs/verification.md) | Definición de terminado y proceso de revisión |
| [`AGENTS.md`](AGENTS.md) | Roles de los agentes, ciclo de vida y protocolo de sesión |

## Limitaciones conocidas

- **Tiempo real:** EMT retiró la página pública de llegadas el 12/11/2026 y no ofrece una API
  abierta ni GTFS-RT. La aplicación funciona con el horario programado hasta que haya una fuente
  autorizada ([`progress/explore_sae_v2.md`](progress/explore_sae_v2.md)).
- **Ocupación simulada:** EMT no publica datos de ocupación, así que se genera de forma
  determinista detrás de un puerto que podría conectarse a sensores reales (RF-14).
- **Posición estimada:** la posición del autobús en el mapa del pasajero se estima a partir del
  tiempo de llegada y del trazado. No es GPS real.
- **Vigencia del GTFS:** el feed de EMT caduca periódicamente y hay que renovarlo a mano.
  `/api/v1/health` indica los días que quedan y los logs avisan con 7 días de antelación.
- **Escala:** un único proceso con SQLite y eventos en memoria, dimensionado para una demostración
  de unos 200 clientes simultáneos.

## Fuentes de datos y atribución

- Datos de la red (GTFS): **EMT València**, publicados en los datos abiertos del **Ajuntament de
  València**.
- Tiempos de llegada: sistema SAE de **EMT València**.
- Mapas: © colaboradores de **OpenStreetMap**.
