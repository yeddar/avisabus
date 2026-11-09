# Simulador de recorrido del conductor — design

> Feature: `driver_gps_simulator` · Versión: 1.0 · Estado: APPROVED
> Requisitos: RF-34, RNF-07 · Casos de uso: CU-14 · Depende de: driver_session

## 1. Componentes

| Capa | Módulo | Contenido |
|---|---|---|
| domain | `services/route_simulation.py` | `simulate_route` (puro) |
| adapters/inbound | `cli/simulate.py` | Comando `simulate` y cliente HTTP (`httpx`) |
| adapters/inbound | `cli/main.py` | Registro |

El trazado y las paradas del viaje los lee de la base de datos local (`NetworkRepository`, como
el resto de la CLI): el simulador se ejecuta en la misma máquina que el servidor, contra la misma
red activa. Todo lo demás pasa por la API.

## 2. Interfaces

```python
# domain/services/route_simulation.py
@dataclass(frozen=True, slots=True)
class SimulatedFix:
    elapsed_s: float; lat: float; lon: float; distance_m: float; at_stop: str | None

def simulate_route(shape: Sequence[ShapePoint], stops: Sequence[tuple[str, float]],   # (stop_id, distancia)
                   speed_mps: float, interval_s: float, dwell_s: float,
                   noise_m: float = 0.0, seed: int | None = None) -> Iterator[SimulatedFix]: ...
# avanza speed·interval por paso con point_at_distance; al cruzar una parada se queda en ella
# ceil(dwell/interval) pasos; termina con un fix en la última parada. Ruido: desplazamiento
# uniforme en un disco de radio noise_m con random.Random(seed).
```

```python
# adapters/inbound/cli/simulate.py
@sim_app.callback(invoke_without_command=True)
def simulate(line: str, direction: int, code: str = typer.Option(..., envvar="AVISABUS_SIM_CODE"),
             departure: str | None = None, trip: str | None = None, speed_kmh: float = 20.0,
             interval_s: float = 5.0, dwell_s: float = 15.0, noise_m: float = 0.0,
             seed: int | None = None, base_url: str = "http://localhost:8000") -> None: ...
# sleep inyectable (tests); try/finally garantiza DELETE de la sesión (AC-03, AC-04)
```

`recorded_at` de cada posición: la hora actual del reloj del simulador. User-Agent:
`AvisaBus-simulator/<versión>`.

## 3. Estrategia de test

| AC | Test |
|---|---|
| AC-02 | `tests/unit/test_route_simulation.py` (trazado sintético) |
| AC-01, AC-03–AC-05 | `tests/integration/test_cli_simulate.py`: `CliRunner` + app en proceso (`httpx.ASGITransport`, sin sockets), código creado con el caso de uso, `sleep` falso; interrupción con `KeyboardInterrupt` lanzado desde el `sleep` falso |

## 4. Preguntas abiertas

Ninguna.
