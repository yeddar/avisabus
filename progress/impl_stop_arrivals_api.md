# Implementación: stop_arrivals_api
Spec: specs/stop_arrivals_api/ (v1.4, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-11-03

Rama `feat/stop_arrivals_api`. Exploración previa: `progress/explore_destinations.md` (E-01, E-02
y E-03; no se ha repetido ni se ha hecho ninguna petición de red).

## Tareas
- [x] T-01 Modelos `ArrivalView`, `StopArrivals`, `StopView`, `VehicleView`, `ArrivalSource`
      (commit 99435ad)
- [x] T-02 `normalize_destination`, `resolve_direction` (+ `resolve_destination`, con el headsign
      mostrado) con el orden de resolución de la v1.4 y la tabla de casos reales de E-01/E-03
      (AC-05, AC-06, AC-07, AC-09, AC-19, AC-20) (commit 19ab5da)
- [x] T-03 `match_trips` óptimo con orden, tolerancia inclusiva, desempate por `trip_id` y
      duplicados; caso real de la 93 en la 508 (AC-10, AC-11, AC-22) (commit cf2548f)
- [x] T-04 `GetStop` y `StopNotFoundError` (AC-01, AC-02, AC-03) (commit ed2a3c1)
- [x] T-05 `ScheduledArrivalsProvider` (AC-13, AC-14) (commit 52585e7)
- [x] T-05b `SqliteNetworkRepository.scheduled_stop_times` recorre los días de servicio de
      `fecha(at) − 1` a `fecha(at + window)`; copia de `gtfs_mini` con un viaje sintético a las
      00:20 (AC-18); los tests de `gtfs_import` AC-15 siguen en verde (commit e4ce261)
- [x] T-05c `NetworkRepository.departing_directions` sobre `gtfs_stop_time`/`gtfs_trip`, con test en
      las cuatro cabeceras de C2 de `gtfs_mini` (AC-19) (commit c9780c1)
- [x] T-06 `GetStopArrivals` (AC-04, AC-07, AC-08, AC-11, AC-12, AC-13, AC-14, AC-15, AC-21)
      (commit de9ec37)
- [x] T-07 Endpoints, esquemas con ejemplos, errores 404/503, `Cache-Control: no-store`,
      composición en `main.py`, ajustes nuevos en `config.py` y `.env.example`, carga y validación
      de *overrides* y `backend/config/direction_overrides.json` (AC-01–AC-04, AC-16, AC-20, AC-21)
      (commit e008790)
- [x] T-08 Tests de extremo a extremo (`tests/integration/test_stops_api.py`) y de rendimiento
      (`tests/integration/test_stops_api_perf.py`, `slow`) (AC-04, AC-08, AC-12, AC-13, AC-15,
      AC-17) (commit 37f58cc)
- [x] T-09 `./init.sh verify` en verde (commit de este fichero)

Ficheros nuevos de producción: `domain/models/stop_arrivals.py`, `domain/services/direction_resolver.py`,
`domain/services/trip_matcher.py`, `application/get_stop.py`, `application/scheduled_arrivals.py`,
`application/get_stop_arrivals.py`, `application/direction_overrides.py`,
`adapters/inbound/http/container.py`, `adapters/inbound/http/routes/stops.py`,
`backend/config/direction_overrides.json`. Modificados: `domain/errors.py`, `domain/ports/network.py`,
`adapters/outbound/persistence/sqlite_network.py`, `adapters/inbound/http/app.py`,
`adapters/inbound/http/errors.py`, `config.py`, `main.py`, `.env.example`.

Tests nuevos: `tests/unit/test_direction_resolver.py`, `test_trip_matcher.py`, `test_get_stop.py`,
`test_scheduled_arrivals.py`, `test_get_stop_arrivals.py`, `test_direction_overrides.py`;
`tests/integration/test_stops_api.py`, `test_main_stops.py`, `test_stops_api_perf.py` (`slow`),
`test_stops_api_real_feed.py` (`slow`, se omite sin `data/gtfs/emt/`); tests de AC-18 y
`departing_directions` en `tests/integration/test_network_repository.py`. Apoyo:
`tests/support/network.py`, `tests/support/stops.py`. Fixture nueva:
`tests/fixtures/sae_recordings/samples/day_2026-11-03/` (documentada en su README).

## Overrides iniciales (petición de la persona)

Método: partí de los 8 *overrides* de `proposal_full_v2.json` (E-01 + E-03), los traduje de número de
sentido a headsign **con los headsigns de las paradas donde se observaron** y comprobé cada uno con
el algoritmo final (alias v1.4, umbral 0,2, regla del sentido que sale) sobre **todas** las entradas
reales de las muestras nocturnas y diurnas (139 entradas en red), con los candidatos
(`headsigns_at_stop`) y los sentidos que salen calculados sobre el feed completo importado en el
*scratchpad* (sin tocar `data/avisabus.sqlite`).

Resultado: **139/139 resueltas sin ningún override**, y en las 15 observaciones afectadas por algún
override el resultado sin él es el mismo sentido que el override. Ningún override es necesario:
**`config/direction_overrides.json` queda vacío (`{}`)**. Lo demuestra el test parametrizado
`test_proposed_overrides_are_not_needed_with_the_v14_algorithm` (`tests/unit/test_direction_resolver.py`),
que comprueba cada propuesta con y sin override sobre su caso real.

| Override propuesto (E-01/E-03) | Headsign (traducción) | Se resuelve sin él por | Decisión |
|---|---|---|---|
| `99\|La Malva-rosa` → 0 | Mendizábal - Doctor Álvaro López | 2070: sentido único; 2230: sentido que sale (0) | Descartado |
| `99\|P. Congressos` → 1 | Palau de Congressos | 1751: texto (0,25 ≥ 0,2) | Descartado |
| `C3\|Campanar` → 0 | Conselleria d'Educació / Avinguda Campanar - Centre de Salut | 1679, 605: sentido único; 229: texto (0,2); 231: sentido que sale (0) | Descartado |
| `C3\|Ed. Bosca` → 1 | Eduard Boscà - Balears | 1265: texto (alias `ed → eduard`) | Descartado |
| `C3\|C. Benlloch` → 1 | Cardenal Benlloch (imparell) - Port | 1266: texto (0,2, sin el alias `c → carrer`) | Descartado |
| `16\|Vinalesa` → 1 | Vinalesa - Plaça d'Ausiàs March | 2014: texto (0,25); 2281: sentido único | Descartado |
| `26\|Moncada` → 1 | Moncada - Alfara | 2014: texto (0,5); 2281: sentido único | Descartado |
| `C2\|Av. Aragó` → 1 | Estadi de Mestalla (front) | 701: sentido único; 346: sentido que sale (1) | Descartado |

Notas:
- La traducción ingenua "headsign principal del sentido" (`gtfs info --directions`) sería
  **incorrecta** en C3 y C2: sus sentidos agrupan dos medios bucles con headsigns distintos
  (p. ej. `C3|C. Benlloch` → "Eduard Boscà - Balears", que no está en la 1266, y el override se
  ignoraría). Por eso se tradujo con los headsigns de la parada.
- `C3|Campanar` cubre los dos medios bucles del sentido 0, con dos headsigns distintos: con el formato
  por headsign (una clave, un headsign) no se puede expresar con una sola entrada (ver O-2).

## Decisiones locales

Dentro de lo que permite design §8:
- **Tabla de alias:** exactamente `DEFAULT_ALIASES` de design §3 (v1.4); no se añade ninguna entrada.
- ***Overrides*:** fichero inicial vacío (sección anterior).
- **Nombres de los esquemas Pydantic:** `StopResponse`, `StopLineSchema`, `StopArrivalsResponse`,
  `ArrivalSchema`, `VehicleSchema`, `OccupancySchema`, `ProblemSchema`.

Interpretaciones donde la spec no fija el detalle (las anoto para el reviewer; ninguna cambia un
contrato):
1. **Pares de prefijo 1 a 1 (design §3):** primero los tokens idénticos; después, voraz, tokens del
   destino ordenados por (longitud, alfabético), cada uno con el primer token libre del headsign en
   ese mismo orden con el que forma prefijo (el más corto ≥ 3 letras). `|A∪B| = |A| + |B| − pares`.
   Fijado con tests (`test_similarity_pairs_prefix_tokens_one_to_one`, `…prefers_exact_pairs…`).
2. **Headsign mostrado (AC-09):** sentido único → el más frecuente del sentido (como dice el design);
   override → el headsign del override; texto → el ganador; sentido que sale → el headsign más
   parecido al texto del SAE dentro de ese sentido (empate: el más frecuente). Implementado en
   `resolve_destination`, del que `resolve_direction` (firma del design) devuelve solo el sentido.
3. **Desempate final de `match_trips`:** lexicográfico sobre la secuencia de asignaciones en orden de
   llegada, con una llegada emparejada (`trip_id`) antes que una sin emparejar. Llegadas con la misma
   hora conservan el orden de entrada. Comprobado contra fuerza bruta.
4. **Candidatos del emparejamiento:** una consulta `scheduled_stop_times` por (línea, sentido) con la
   ventana de design §3.
5. **Ocupación:** se lee para el instante `clock.now()` tanto en tiempo real como en el respaldo.
6. **`generated_at`** = `clock.now()`; **`refresh_after_s`** = `ceil(AVISABUS_SAE_CACHE_TTL_S)`
   (entero), también con `source = "SCHEDULED"`.
7. **Orden de comprobaciones:** token → feed activo → parada. Con token inválido nunca se consulta
   el SAE (y la respuesta es 404 aunque no haya feed).
8. **Niveles de log:** `arrivals.fallback` warning, `arrivals.direction_unresolved` info,
   `arrivals.trip_unmatched` debug (design §5), `arrivals.override_invalid` warning con `entry`,
   `headsign` y `reason` (`unknown_line`, `unknown_headsign`, `malformed_entry`).
9. **Líneas fuera de la red (AC-08)** no registran `arrivals.direction_unresolved` (no tienen sentido
   que resolver). Una línea de la red que no para en la parada sí (0 candidatos → AC-07).
10. **`departing_directions`:** consulta directa (sin precálculo ni índice nuevo): mediana < 5 ms sobre
    el feed completo (1959/C1 0,45 ms; 2277/C1 4,2 ms), por debajo de los 20 ms de design §3. Solo se
    consulta cuando la línea tiene más de un sentido en la parada.
11. **Validación de *overrides*:** con `FeedInfoSource.direction_report()` (todos los headsigns de
    cada sentido, puerto existente), sin ampliar `NetworkRepository`. 60 ms una vez al arrancar con
    el feed completo.
12. **Fichero de *overrides* ilegible o que no es un objeto JSON de textos** → `ConfigurationError`
    (la API no arranca), como `AVISABUS_SAE_REPLAY_DIR`. Se lee antes de abrir la BD. Una clave sin
    `|` se trata como entrada inválida (`malformed_entry`) y se ignora (ver O-4).
13. **Configuración:** `AVISABUS_DIRECTION_OVERRIDES_FILE` vale vacío por defecto en el código (design
    §6); `.env.example` lo apunta a `config/direction_overrides.json` (relativo a `backend/`).
14. **Composición:** `build_stop_use_cases` en `adapters/inbound/http/container.py` (como
    `cli/container.py`), llamado desde `main.py`; `create_app(..., stops=…)` solo monta las rutas de
    parada si recibe los casos de uso. Así los tests de integración usan la misma composición.
15. **`Logger`:** `Protocol` en `application/get_stop_arrivals.py` (structlog en producción), para no
    depender de structlog en la capa de aplicación.
16. **Hora programada:** `domain/services/occupancy_simulation.service_day_start` (Europe/Madrid), ya
    existente; no se duplica.
17. **Fixture nueva `samples/day_2026-11-03/`:** las respuestas reales de E-03 (cabeceras de C1 y C2)
    unidas en una sesión, igual que se hizo con `night_2026-11-02` (cuerpos sin cambios).
18. **AC-19 con C1 en integración:** `gtfs_mini` no tiene C1. En la suite normal, AC-19 se verifica en
    integración con las cabeceras reales de C2 (346, "Av. Aragó", resuelta por el sentido que sale;
    y T-05c). Las cabeceras de C1 (1959, 2277) con "Cntr.Històric" se comprueban en unit (datos reales
    del feed completo) y en `tests/integration/test_stops_api_real_feed.py` (`slow`, feed real; se
    omite si no está `data/gtfs/emt/`). Ejecutado: 2 passed.

### Observaciones para la spec (no bloqueantes)
- **O-1 (AC-20):** los *overrides* se validan al arrancar; si la API arranca sin feed activo (primera
  instalación), todos se ignoran hasta reiniciar tras importar. Con el fichero vacío no tiene efecto.
- **O-2 (design §4):** el formato `línea|destino → headsign` no puede expresar un texto del SAE que
  cubre dos medios bucles del mismo sentido con headsigns distintos (`C3|Campanar`): solo actúa en las
  paradas donde está ese headsign. Hoy no hace falta (ningún override es necesario). El ejemplo de
  design §4 (`C3|Campanar`, `C2|Av. Aragó`) no se usa en el fichero inicial.
- **O-3 (AC-09):** el design solo fija el headsign mostrado para el sentido único y "el más parecido";
  la regla para override y sentido que sale es la interpretación 2.
- **O-4 (design §4/§6):** no se especifica qué hacer si el fichero de *overrides* no existe o no es
  JSON válido (interpretación 12).
- **O-5 (AC-19):** la verificación cita las cabeceras de C1 en integración, pero `gtfs_mini` no tiene
  C1 (interpretación 18).

## Bloqueos
Ninguno.

## Verificación

`./init.sh verify` (2026-11-03, tras T-08):

```
OK   backend: format
OK   backend: lint
OK   backend: types
OK   backend: architecture          (Contracts: 2 kept, 0 broken)
OK   backend: tests                 853 passed, 6 deselected; cobertura domain+application 99,66 %
                                    (get_stop_arrivals.py 100 %, stop_arrivals.py 100 %)
OK   frontend: format / lint / types / tests (7 passed) / build
OK   harness: feature_list.json
OK   harness: trazabilidad AC→test  (AC-01…AC-22 citados)
OK   verify: todo en verde
```

Tests `slow` (manuales):

```
uv run pytest -m slow tests/integration/test_stops_api_perf.py tests/integration/test_stops_api_real_feed.py -s
AC-17 stop 508: 200 cached requests, median 2.6 ms, p95 2.8 ms, max 3.8 ms
AC-17 stop 2070: 200 cached requests, median 1.7 ms, p95 1.8 ms, max 1.9 ms
4 passed (incluidos los 2 de C1 con el feed real)
```

AC-17: p95 < 100 ms en el equipo de desarrollo (MacBook, ASGI en proceso) y una sola consulta al
SAE para 200 peticiones con la respuesta en caché (también en la suite normal:
`test_cached_stop_never_asks_the_sae_again`).
