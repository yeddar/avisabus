# Exploración: destinos del SAE frente a headsigns del GTFS, y tolerancia de emparejamiento
Feature(s): stop_arrivals_api (v1.3, E-01 y E-02) · Fecha: 2026-11-02 · Agente: explorer

## Pregunta(s)

- **E-01:** comparar el `destino` del SAE con los headsigns GTFS de esa línea en la parada (tabla
  `línea | destino SAE | headsigns GTFS | ¿un solo sentido?`). Hay que medir qué porcentaje resuelve
  el algoritmo de design §3 con `min_score = 0.34`, proponer alias y *overrides* y ver qué destino
  da el SAE en las circulares C1, C2 y C3.
- **E-02:** con `stop_508_peak` y `gtfs_mini`, distribución de `|arrival_at − scheduled_at|` del
  mejor candidato. Confirmar la tolerancia de 20 min o proponer otra.

## Hallazgos

### Método y fuentes (todo reproducible; scripts en `progress/explore_destinations_samples/`)

- **BD de exploración (fuera del repo).** Importé el feed completo `data/gtfs/emt/` y `gtfs_mini` con
  la CLI del proyecto, cada uno en una SQLite del *scratchpad*: `AVISABUS_DATABASE_URL=sqlite:///<scratchpad>/full.sqlite uv run --frozen avisabus gtfs import ../data/gtfs/emt`.
  - Resultado: 42 líneas, 1 117 paradas, 20 598 viajes y 508 134 horarios de parada.
  - Así los sentidos y `stop_line_headsign` son exactamente los que deriva `gtfs_import`.
  - No se ha tocado `data/avisabus.sqlite`.
- **Algoritmo.** `resolver_prototype.py` transcribe literalmente design §3 (`normalize_destination`,
  `resolve_direction`, `DEFAULT_ALIASES`). Los candidatos salen de
  `SqliteNetworkRepository.headsigns_at_stop`.
  - El Jaccard con prefijos lo interpreto así: emparejamiento 1-1 de tokens (exactos primero, luego
    prefijos de longitud ≥ 3); `|A∩B|` = pares emparejados.
- **Arneses:**
  - `analyze_recordings.py <db> <dirs…> [--lenient] [--proposal f.json]` (E-01);
  - `tolerance_e02.py`, `matching_stability_e02.py` y `series_e02.py` (E-02);
  - `dump_night.py`, que vuelca las llegadas y las entradas descartadas.
  - Se ejecutan desde `backend/` con `uv run --frozen python ../progress/explore_destinations_samples/<script> …`.
  - Las salidas están guardadas en `out_*.txt`.
- **Datos SAE:**
  1. `tests/fixtures/sae_recordings/stop_508_peak`: real, lunes 2026-11-02 de 20:42 a 21:07 (hora de Madrid), paradas 508 y 2070, 150 respuestas.
  2. `samples/e01_2026-11-02`: real, hacia las 12:00.
  3. **Consultas nuevas**: 22 paradas, **1 consulta por parada** (22 en total), separadas unos 3 s entre sí, entre las 23:31:57 y las 23:33:09 (hora de Madrid) del 2026-11-02.
     - Se hicieron con la CLI del proyecto (`uv run avisabus sae record --stop <id> --interval 20 --duration 1 --out …`, un solo ciclo, para guardar el HTML en bruto). El User-Agent sale del `.env` raíz.
     - No se ha usado ningún endpoint cerrado ni se ha falseado ninguna cabecera.
     - Las respuestas están en `explore_destinations_samples/night_20261102/<stop>/` (formato de grabación, sin datos de contacto).
     - Paradas: 508, 2070; cabeceras 2277, 2312, 2230, 1751, 2271, 487, 2403, 2014, 1959 (C1) y 166 (C2); C3 1265, 1266, 229, 231 (cabeceras), 1679 y 605 (mitad de bucle); otras 2281, 1349, 2203 y 830.
  - **Limitación:** las consultas se hicieron a las 23:32 porque esa era la hora de la sesión. C1 (último servicio a las 22:13) y C2 (22:37) ya no circulaban. Sí había C3 (hasta las 02:37) y otras 22 líneas (`lastrun` sobre el GTFS del lunes).

### H-1. Estructura del GTFS: el 91,6 % de las pasadas tiene un único sentido en su parada

Agrupé `stop_line_headsign` del feed completo por `(stop_id, línea)`:

| Sentidos en la parada | Pares (parada, línea) | Pasadas programadas |
|---|---|---|
| 1 | 1 930 | 465 583 (91,6 %) |
| 2 | 98 | 42 551 (8,4 %) |

- **89 de esos 98 pares son cabeceras** (primera o última parada de algún viaje de la línea). Los
  otros 9 son paradas compartidas por ambos sentidos en ramales de las líneas 24, 25 y 26 (1706,
  2203, 2177, 1329, 1485, 1562, 2262, 290).
- En las líneas lineales, cada sentido usa paradas distintas (parell/imparell), así que
  **AC-05 (sentido único) resuelve la inmensa mayoría sin comparar textos**. La comparación de
  textos (AC-06) solo actúa en cabeceras y en esos 9 casos.
- En las cabeceras, el GTFS incluye los viajes que **terminan** allí (headsign = la propia
  cabecera). El SAE también los muestra: en 2312, la 9 aparece con `Est.del Nord -` (llega) y con
  `Forn d'Alcedo -` (sale). Por eso **no conviene** quitar de los candidatos los viajes que
  terminan en la parada.

### H-2. Tabla E-01 (datos reales; feed completo; algoritmo de design §3 con `DEFAULT_ALIASES` y `min_score = 0.34`)

"n" = número de llegadas observadas. Para las de la noche cuento todas las entradas, también las
que el parser descarta (ver H-5), porque el destino sí aparece.

| Parada | Línea | Destino SAE | Headsigns GTFS en la parada (sentido: headsign) | ¿Un solo sentido? | Resultado (default) | n |
|---|---|---|---|---|---|---|
| 508 | 70 | Alboraia | 1: Alboraia | sí | 1 | 157 |
| 508 | 93 | Pass. Marítim | 0: Passeig Marítim - Hospital Malva-rosa | sí | 0 | 161 |
| 2070 | 73 | Sant Isidre | 1: Sant Isidre | sí | 1 | 153 |
| 2070 | 95 | Tres Creus | 1: Tres Creus (imparell) - Hospital General | sí | 1 | 158 |
| 2070 | 98 | Av. Cid | 1: Cid - Pere Maria Orts | sí | 1 | 152 |
| 2070 | 99 | La Malva-rosa | 0: Mendizábal - Doctor Álvaro López | sí | 0 | 160 |
| 2281 | 4 / 8 / 16 / 26 / 70 / 81 | Natzaret / Pta.de la Mar / Vinalesa / Moncada / Alboraia / Blasco Ibáñez | 1: Natzaret / 0: Porta de la Mar - Glorieta / 1: Vinalesa - Plaça d'Ausiàs March / 1: Moncada - Alfara / 1: Alboraia / 1: Blasco Ibáñez - Serradora | sí (todas) | resuelto | 11 |
| 1349 | 27 / 64 | La Torre / Hosp. La Fe | 1: La Torre / 0: Bulevard Sud (imparell) - Hospital La Fe | sí | resuelto | 3 |
| 830 | 19 | Est.del Nord | 0: Periodista Azzati - Plaça de l'Ajuntament | sí | 0 | 2 |
| 166 | 81 | Blasco Ibáñez | 1: Blasco Ibáñez - Serradora | sí | 1 | 2 |
| 487 | 93 | Av. Cid | 1: Avinguda del Cid | sí | 1 | 1 |
| 1265 / 1266 / 2312 | 60 | Est.del Nord / Torrefiel | 0: Sant Agustí / 1: Torrefiel | sí | resuelto | 3 |
| 2312 | 62 / 7 | Benimàmet / Fta. S.Lluis | 1: Terramelar / 1: Fonteta de Sant Lluís | sí | resuelto | 3 |
| 1679 | C3 | Campanar | 0: Conselleria d'Educació | sí | 0 | 1 |
| 605 | C3 | Campanar | 0: Avinguda Campanar - Centre de Salut | sí | 0 | 1 |
| 2271 | 93 | Av. Cid | 0: Passeig Marítim - Hospital Malva-rosa; 1: Avinguda del Cid | **no** | 1 (0,667 frente a 0) | 1 |
| 2277 | 72 | Sant Isidre | 0: Xàtiva - Institut Lluís Vives; 1: Sant Isidre | **no** | 1 (1,0) | 2 |
| 2312 | 9 | Est.del Nord | 0: Sant Pau - Estació del Nord; 1: Forn d'Alcedo | **no** | 0 (0,6) | 1 |
| 2312 | 9 | Forn d'Alcedo | ídem | **no** | 1 (1,0) | 1 |
| 2403 | 4 | Natzaret | 0: Plaça de l'Ajuntament - Ateneu; 1: Natzaret | **no** | 1 (1,0) | 2 |
| 2014 | 26 | Moncada | 0: Poeta Querol - Teatre Principal; 1: Moncada - Alfara | **no** | 1 (0,5) | 2 |
| 2014 | 16 | Vinalesa | 0: Poeta Querol - Teatre Principal; 1: Vinalesa - Plaça d'Ausiàs March | **no** | **None** (0,2) | 2 |
| 1751 | 99 | P. Congressos | 0: Mendizábal - Doctor Álvaro López; 1: Palau de Congressos | **no** | **None** (0,25) | 2 |
| 2230 | 99 | La Malva-rosa | 0: Mendizábal - Doctor Álvaro López; 1: Palau de Congressos | **no** | **None** (0 / 0) | 2 |
| 1265 | C3 | Ed. Bosca | 0: Conselleria d'Educació; 1: Eduard Boscà - Balears | **no** | **None** (0,25) | 1 |
| 1266 | C3 | C. Benlloch | 0: Avinguda Campanar - Centre de Salut; 1: Cardenal Benlloch (imparell) - Port | **no** | **None** (0,2) | 1 |
| 229 | C3 | Campanar | 0: Avinguda Campanar - Centre de Salut; 1: Cardenal Benlloch (imparell) - Port | **no** | **None** (0,2) | 1 |
| 231 | C3 | Campanar | 0: Conselleria d'Educació; 1: Eduard Boscà - Balears | **no** | **None** (0 / 0) | 1 |

Fuentes:
- `out_e01_recordings_full.txt` (grabaciones);
- `out_e01_night_lenient_default.txt` (noche);
- `out_night_dump.txt` (llegadas brutas por parada).

Las paradas 1959 (C1) y 2203 (24/25) no daban llegadas a esa hora.

Observaciones:
- **Los destinos del SAE son los extremos abreviados de `route_long_name`.** Por ejemplo, `99 - PALAU
  DE CONGRESSOS - LA MALVA-ROSA` da "P. Congressos" y "La Malva-rosa". No coinciden con
  `trip_headsign`, que es la última parada.
- **Con un solo sentido**, la discrepancia de textos no importa (2070/99: "La Malva-rosa" frente a
  "Mendizábal - Doctor Álvaro López").
- **Con dos sentidos**, la puntuación Jaccard falla por tres causas:
  - (a) penaliza headsigns largos frente a un destino corto ("Vinalesa" frente a 5 tokens);
  - (b) las abreviaturas de 1–2 letras no cuentan como prefijo ("Ed.", "P.");
  - (c) el alias por defecto `c → carrer` es **incorrecto** en el único caso observado: "C. Benlloch" es *Cardenal* Benlloch.
- En los 7 casos sin resolver, el otro sentido puntúa 0. Nunca hay empate entre dos sentidos con puntuación positiva: falla el umbral, no la discriminación.

### H-3. Porcentaje de resolución

| Conjunto | Llegadas en red | Resueltas (default) | % |
|---|---|---|---|
| `stop_508_peak` + `samples/e01` con el feed completo | 935 | 935 | **100 %** (todas con sentido único) |
| `stop_508_peak` con `gtfs_mini` (70, 93 y 98 en red; 73, 95 y 99 fuera) | 439 | 439 | **100 %** |
| Noche, 22 paradas, solo llegadas que acepta el parser | 37 | 29 | 78,4 % |
| Noche, 22 paradas, todas las entradas (`--lenient`) | 52 | 42 | 80,8 % |
| **Todas las observaciones reales** (parser estricto) | 972 | 964 | **99,2 %** |
| **Estimación ponderada por pasadas en toda la red** (H-1): 91,6 % de sentido único + 8,4 % × 6/13 (tasa observada en cabeceras con el default) | — | — | **≈ 95,5 %** (cota inferior 91,6 % aunque fallen todas las cabeceras) |

- La muestra nocturna está sesgada a propósito hacia las cabeceras: 14 de las 22 paradas son
  cabeceras de alguna línea. Por eso su porcentaje es bajo y no es representativo de la red.
- **Ninguna estimación baja del 90 %**, así que el umbral de CP-3 de E-01 no se dispara.

Con propuestas (ver "Impacto en la spec"):

| Configuración | Noche (`--lenient`, 52) | Fichero |
|---|---|---|
| Solo alias nuevos (palabras vacías → `""`, `pta`, `fta`, `s`, `ed`; quitar `c`) | 43/52 = 82,7 % | `out_e01_night_lenient_aliases.txt` |
| Alias + `min_score = 0.2` | 49/52 = 94,2 % | `out_e01_night_lenient_aliases_min020.txt` |
| Alias + *overrides* (7 entradas) | **52/52 = 100 %** | `out_e01_night_lenient_full_proposal.txt` |
| Alias + *overrides* sobre `stop_508_peak` | 883/883 = 100 % (sin regresiones) | `out_e01_recordings_full_proposal.txt` |

### H-4. Circulares C1, C2 y C3

- **C3 (observada):** el SAE **no** da "Circular", sino un nombre de zona por sentido:
  - **sentido 0 → "Campanar"** en los dos medios bucles (1679, del bucle 1074, cuyo headsign es "Conselleria d'Educació"; y 605, del bucle 1075, headsign "Avinguda Campanar - Centre de Salut");
  - **sentido 1 → "Ed. Bosca"** (cabecera 1265, bucle 1074) y **"C. Benlloch"** (cabecera 1266, bucle 1075).
  - La relación (línea, destino SAE) → sentido es estable, así que **se resuelve con *overrides* globales** (`C3|Campanar → 0`, `C3|C. Benlloch → 1`) y el alias `ed → eduard` (o un *override* `C3|Ed. Bosca → 1`).
- **Garantía del GTFS:** en C1, C2 y C3, las únicas paradas con dos sentidos son las cabeceras (H-1).
  Las demás son de sentido único y se resuelven por AC-05 **sea cual sea el texto del SAE**:

  | Línea | Paradas | Paradas con 2 sentidos | Pasadas en esas paradas |
  |---|---|---|---|
  | C1 | 15 | 2 (1959, 2277) | 656 / 2 787 (23,5 %) |
  | C2 | 56 | 4 (166, 346, 691, 1057) | 430 / 3 221 (13,4 %) |
  | C3 | 72 | 4 (229, 231, 1265, 1266) | 3 678 / 34 966 (10,5 %) |

- **C1 y C2: no observadas** (sin servicio a la hora de la consulta). En las paradas intermedias se
  resuelven seguro. En sus 6 cabeceras depende del texto:
  - si, como en C3, es un nombre de medio bucle o de zona → alias/*overrides*;
  - si es genérico ("Circular", "Centre Històric") → en la cabecera es ambiguo de verdad. Un *override* (línea, destino) no sirve, porque el sentido que **sale** es 0 en una cabecera y 1 en la otra. Quedaría `direction_id = null` y `can_alert = false` (AC-07). Es una degradación acotada, no un bloqueo.
  - El ejemplo `"C2|Circular": 0` de design §4 no tiene base observada.

### H-5. Hallazgo colateral (afecta a `sae_arrivals_source`, ya `done`): formatos no previstos en la página del SAE

En las 22 respuestas nocturnas, el parser descarta **15 de 52 entradas (29 %)** con `sae.unparsed_entry`
(`out_night_dump.txt`):

- **Hora con segundos `HH:MM:SS`** para llegadas a más de unos 60 minutos. Ejemplos: `99 La Malva-rosa - 00:42:28`
  (2070, a las 23:32), `81 Blasco Ibáñez - 00:33:05` (2281) y `27 La Torre - 00:51:07` (1349).
  - El mayor `N min.` observado es 58.
  - Esas horas coinciden con el horario GTFS con un margen de −120 a +169 s: son el horario programado.
  - design §4 de `sae_arrivals_source` (y la muestra derivada `derived_clock_time`) suponían `HH:MM`.
- **Entradas sin tiempo** `"{destino} -"` en una cabecera: 2312 da 5 de 6 entradas así
  (`Est.del Nord -`, `Forn d'Alcedo -`, …), y el parser las descarta ("no separator").
- No apareció ninguna línea nocturna (N*) un lunes a las 23:32.

### H-6. E-02: distribución de `|arrival_at − scheduled_at|` del mejor candidato (`stop_508_peak`)

Para cada llegada, el candidato más próximo de su línea y sentido, sin restricción (`out_e02_tolerance_*.txt`):

| BD | n | Mediana | p90 | p95 | Máx. | ≤ 5 min | ≤ 10 min |
|---|---|---|---|---|---|---|---|
| `gtfs_mini` (70, 93, 98) | 439 | 2,2 | 5,4 | 5,9 | 6,6 | 85,0 % | **100 %** |
| feed completo (6 líneas) | 883 | 2,2 | 4,6 | 5,4 | 6,6 | 92,2 % | **100 %** |

- Desviación media con signo por línea: entre −1,8 min (70) y +2,4 min (99).
- Sesión de tarde (20:42–21:07), no de hora punta.
- **Emparejadas con `match_trips` de design §3 (voraz)**, `gtfs_mini`:

  | Tolerancia | Emparejadas |
  |---|---|
  | 5 min | 81,8 % |
  | 8 min | 96,4 % |
  | 10 min | 97,0 % |
  | 12 min | 99,5 % |
  | ≥ 15 min | 100 % |

  Con el feed completo: 88,9 / 98,0 / 98,5 / 99,8 / 100 %.
- **Inestabilidad del algoritmo voraz** (`out_e02_series_508_93.txt`): en 508/93 hay dos autobuses
  agrupados (ETA 20:55 y 20:56; horario 20:50:35, 20:59:08 y 21:08:08). El voraz asigna a la 1.ª
  llegada el viaje más próximo (…_123, −4,1 min) y a la 2.ª el siguiente libre posterior,
  **…_124 a −12,1 min** (erróneo). En el refresco siguiente (ETA 20:54) cambia a …_122/…_123. La
  identidad del autobús oscila entre refrescos, y con ella la ocupación mostrada.
- Para medirlo conté los cambios del viaje asignado a la **primera** llegada de cada línea y sentido
  entre instantáneas consecutivas (`out_e02_stability_*.txt`). "Hacia atrás" = el viaje nuevo es
  anterior al previo: es siempre un error, porque un autobús que ha pasado no vuelve.

  | BD | Algoritmo | Tolerancia 10 / 15 / 20 | Cambios | Hacia atrás |
  |---|---|---|---|---|
  | `gtfs_mini` | voraz (design §3) | 97,0 / 100 / 100 % emparejadas | 22 | 8 |
  | `gtfs_mini` | óptimo con orden (máx. emparejadas, luego mín. Σ\|Δ\|) | 100 % en las tres | **8** | **1** |
  | completo | voraz | 98,5 / 100 / 100 % | 35 | 11 |
  | completo | óptimo con orden | 100 % | **21** | **4** |

  Pasos de autobús reales en la sesión: 3 en la 508 y 8 en la 2070 (README de la fixture).
- **La tolerancia (entre 10 y 20) apenas cambia el resultado; el algoritmo sí.** Con el voraz, una
  tolerancia mayor que la mitad del intervalo de paso (93: 8–9 min por la tarde) produce
  emparejamientos erróneos silenciosos (−12 min) en vez de `vehicle = null`.
- Coherencia de fecha: `gtfs_mini` tiene servicio el lunes 2026-11-02 (`calendar.txt`, de lunes a
  jueves/viernes, del 20261016 al 20261122). Los resultados de 70, 93 y 98 son idénticos con
  `gtfs_mini` y con el feed completo: no hace falta regenerar `gtfs_mini` (design §7).

## Impacto en la spec

Ningún hallazgo bloquea implementar `stop_arrivals_api` tal como está escrita. Los AC-05 a AC-11 se
pueden cumplir. Propuestas:

1. **Decisión local permitida (design §3/§8): tabla de alias.** Añadir:
   - **palabras vacías mapeadas a `""`**, que se descartan según design §3: `de`, `d`, `del`, `dels`, `la`, `l`, `el`, `els`, `les`, `i`, `y`;
   - abreviaturas: `pta → porta`, `fta → fonteta`, `s → sant`, `ed → eduard`, `j → joaquin`.
   - Fichero: `proposal_aliases_only.json`.
2. **Decisión local permitida: *overrides*** (`proposal_full.json`):
   ```json
   {"99|La Malva-rosa": 0, "99|P. Congressos": 1, "C3|Campanar": 0, "C3|Ed. Bosca": 1,
    "C3|C. Benlloch": 1, "16|Vinalesa": 1, "26|Moncada": 1}
   ```
   - Con 1 y 2, 52/52 en la muestra nocturna y 883/883 en `stop_508_peak`.
   - Estos casos sirven como tabla de casos reales para T-02 (AC-06, design §7).
   - Ojo: los sentidos son los que deriva `gtfs_import` sobre el feed `23-10-2026`. Si un feed nuevo invierte la referencia, los *overrides* por número de sentido dejan de valer (ver Riesgos).
3. **Requiere cambio de spec (menor, no bloqueante): quitar `"c": "carrer"` de `DEFAULT_ALIASES`**
   (design §3). La única "C." observada es *Cardenal*, y la regla local solo permite **añadir**
   entradas. Si no se quita, el *override* `C3|C. Benlloch` lo cubre igualmente.
4. **Opcional, CP-3 si se quiere (design §3, puntuación):** Jaccard penaliza los destinos cortos
   frente a headsigns largos. Dos alternativas:
   - (a) `AVISABUS_DIRECTION_MIN_SCORE = 0.2` (configurable, sin tocar el código): 49/52 sin *overrides* y sin falsos positivos, porque en todos los casos el otro sentido puntuó 0;
   - (b) cambiar la medida por la de contención `|A∩B| / min(|A|,|B|)`.

   Con los *overrides* del punto 2 no es imprescindible, pero cada destino corto nuevo en una cabecera necesitará otro *override*.
5. **E-02 / AC-10 / design §3 `match_trips` (propuesta, decide la persona → CP-3 ligero):**
   - sustituir la asignación voraz por la **asignación óptima con orden**: maximizar las llegadas emparejadas y, a igualdad, minimizar Σ|Δ|, cada viaje una vez, con horas estrictamente crecientes. Con 2 llegadas por línea y sentido, basta la fuerza bruta;
   - el texto de AC-10 ("la más próxima… respetando el orden temporal") encaja si se lee como conjunto, pero design §3 prescribe literalmente el voraz;
   - si se mantiene el voraz, **bajar `AVISABUS_TRIP_MATCH_TOLERANCE_MIN` a 10**: evita los emparejamientos a −12 min, aunque no las oscilaciones;
   - si se adopta el óptimo, 20 min no hace daño en los datos observados, pero también propongo **10 min** (máximo observado 6,6 min; mejor `vehicle = null` que un viaje equivocado). Revisarlo con una grabación de hora punta real.
6. **design §4, ejemplo `"C2|Circular": 0`:** sustituirlo por un caso real (`"C3|Campanar": 0`).
   No hay ninguna evidencia de que el SAE use "Circular".
7. **Fuera de esta feature (`sae_arrivals_source`, `done`) → CP-3 para esa spec:** el SAE usa
   `HH:MM:SS` (no `HH:MM`) para las llegadas a más de unos 60 min, y `"{destino} -"` sin tiempo en
   las cabeceras (H-5). Hoy se descartan el 29 % de las entradas nocturnas. Propuestas:
   - aceptar `^\d{1,2}:\d{2}(:\d{2})?$` como CLOCK_TIME;
   - decidir qué hacer con "sin tiempo" (descartar en silencio a nivel debug, o un tipo nuevo);
   - sustituir `derived_clock_time` por la muestra real `night_20261102/2070`.

   Afecta a AC-04 de esta feature ("una entrada por llegada del SAE") solo a través del parser.

## Riesgos

- **Sesgo de la muestra:** solo hay datos de tarde (20:42–21:07) y de noche (23:32) de un lunes. No
  hay hora punta, ni C1/C2, ni fin de semana. El porcentaje ponderado (≈ 95,5 %) extrapola 13 casos
  de cabecera a 98 pares.
- **C1/C2 en cabeceras:** si el SAE usa un texto genérico, quedan 6 paradas con `direction_id = null`
  (el 23,5 % de las pasadas de C1 y el 13,4 % de las de C2). Recomiendo 6–8 consultas diurnas
  (1959, 2277, 166, 346, 691, 1057 y dos paradas intermedias), ≤ 1 cada 20 s por parada, antes de
  cerrar T-02 o en T-08.
- ***Overrides* atados al número de sentido derivado:** `direction_id` se deriva al importar (sentido 0
  = patrón más frecuente). Un feed nuevo puede intercambiar 0 y 1, y un *override* quedaría
  invertido en silencio. Mitigaciones posibles: validar los *overrides* al cargar (el sentido debe
  existir y su headsign debe ser coherente) o expresarlos por headsign. Esto último sería un cambio
  de spec.
- **AC-09:** el pasajero verá el headsign GTFS ("Mendizábal - Doctor Álvaro López"), no lo que rotula
  el autobús ("La Malva-rosa"). Es correcto según RF-32, pero puede confundir. Es una nota de UX
  para `passenger_stop_view`.
- **Interpretación del Jaccard con prefijos:** design §3 no fija cómo se cuentan los pares de prefijo
  (1-1 o todos contra todos). Aquí he usado 1-1 voraz. Conviene que el implementer lo documente y lo
  fije con un test.
- **Consultas al SAE:** 22 en esta exploración, 1 por parada. Sin errores (todas HTTP 200).

## Recomendación

Implementar `stop_arrivals_api` tal cual, con la tabla de alias y los *overrides* de los puntos 1
y 2, que son decisiones locales permitidas. Como tabla de casos reales de T-02, usar las filas de
H-2.

Antes de implementar, que la persona decida en un **CP-3 ligero, no bloqueante para empezar
T-01/T-04/T-05/T-05b**:
- (a) si se quita `c → carrer`;
- (b) si se cambia `match_trips` a la asignación óptima con orden, o se mantiene el voraz con tolerancia 10;
- (c) si se abre CP-3 sobre `sae_arrivals_source` por `HH:MM:SS` y las entradas sin tiempo.

Programar una consulta diurna corta a las cabeceras de C1 y C2.

---
**Resumen para el orquestador:**
- El 91,6 % de las pasadas del GTFS está en paradas donde la línea tiene un solo sentido, así que AC-05 las resuelve sin texto. Resolución observada: 99,2 % (964/972); estimación ponderada en la red ≈ 95,5 % (mínimo 91,6 %). **No se dispara el CP-3 del 90 %.**
- Los fallos se concentran en las cabeceras. Se arreglan con alias y 7 *overrides* (52/52 y 883/883).
- C3 da destinos de zona ("Campanar", "Ed. Bosca", "C. Benlloch"), no "Circular", y se resuelve. C1 y C2 no se pudieron observar (sin servicio a las 23:32): solo sus 6 cabeceras dependen del texto.
- E-02: |Δ| máximo de 6,6 min (p95 5,4). Propongo una tolerancia de 10 min y cambiar el emparejamiento voraz por uno óptimo con orden, porque el voraz hace oscilar la identidad del autobús.
- La spec puede implementarse tal cual. Hay un **CP-3 ligero opcional** (alias `c`, algoritmo de emparejamiento) y un **CP-3 aparte para `sae_arrivals_source`** (`HH:MM:SS` y entradas sin tiempo: 29 % de entradas descartadas de noche).
