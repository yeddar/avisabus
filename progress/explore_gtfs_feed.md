# Exploración: feed GTFS real de EMT y derivación de sentidos
Feature(s): gtfs_import (E-01) · Fecha: 2026-10-31 · Agente: explorer

## Pregunta(s)

E-01 de `specs/gtfs_import/tasks.md`, sobre `data/gtfs/emt/` (feed_version `23-10-2026`, vigencia
2026-10-16 → 2026-11-22):

1. Número de filas por fichero.
2. ¿Todos los viajes tienen `shape_id` y `trip_headsign`?
3. `arrival_time` máximo: ¿hay horas ≥ 24:00:00?
4. ¿Qué líneas sirven las paradas 508 y 2070?
5. Patrones (`shape_id`) por línea, con primera y última parada y nº de viajes.
6. ¿Qué líneas son circulares (extremos < 500 m)?
7. Significado aparente de `trip_id` y `shape_id` (solo informativo).
8. Aplicar a mano el algoritmo de design §4.3 a todas las líneas. Listar las que no den
   exactamente dos sentidos, o uno si son circulares de un solo giro.

## Hallazgos

### Scripts (solo lectura, Python 3.9 de sistema, sin dependencias)

Están en `progress/explore_gtfs_feed_samples/`. Se ejecutan desde la raíz del repo:

```
python3 -I progress/explore_gtfs_feed_samples/01_basic_stats.py data/gtfs/emt
python3 -I progress/explore_gtfs_feed_samples/02_derive_directions.py data/gtfs/emt --json <tmp>/derived.json
python3 -I progress/explore_gtfs_feed_samples/03_checks.py data/gtfs/emt
python3 -I progress/explore_gtfs_feed_samples/04_loops_and_coverage.py data/gtfs/emt
python3 -I progress/explore_gtfs_feed_samples/05_directions_table.py data/gtfs/emt <tmp>/derived.json
python3 -I progress/explore_gtfs_feed_samples/06_fixture_size.py data/gtfs/emt
```

Cada uno tarda menos de 2 s. `02` implementa §4.3 literalmente: patrón = `shape_id`; referencia
= más viajes (empate → `shape_id` menor); umbral circular 500 m; haversine; área por *shoelace*
sobre proyección equirrectangular; área despreciable < 1 000 m².

### 1. Filas por fichero (sin cabecera) — `01_basic_stats.py`

| Fichero | Filas |
|---|---|
| agency.txt | 1 |
| calendar.txt | 179 |
| calendar_dates.txt | 70 |
| feed_info.txt | 1 |
| routes.txt | 50 |
| shapes.txt | 28 006 |
| stop_times.txt | 508 134 |
| stops.txt | 1 117 |
| trips.txt | 20 598 |

Otros datos del feed:
- `routes.txt` tiene 50 `route_id` y 44 `route_short_name`. Solo **42 líneas tienen viajes**.
  Hay tres `route_id` sin viajes: `1033` (línea 23), `982` (línea 30) y `1068` (línea 24,
  "Només dissabtes i festius"). Las líneas 23 y 30 no tienen ningún viaje (`03_checks.py`).
- Líneas con varios `route_id`: 24 (`1040`: 124 viajes, `1068`: 0), 62 (`967`/`1077`),
  73 (`963`/`962`), 98 (`1055`/`1054`), C2 (`651`/`996`) y C3 (`1074`/`1075`).
- `stop_id == stop_code` en las 1 117 paradas. Todas las paradas tienen al menos un viaje.
- Todos los `service_id` de los viajes están en `calendar.txt`. Ninguno aparece solo en
  `calendar_dates.txt`.
- `stop_sequence` es `1..n` y contiguo en todos los viajes. `stop_headsign` está vacío en las
  508 134 filas.
- Cada `shape_id` tiene **una sola secuencia de paradas** en todos sus viajes. Lo comprobé con un
  `python3 -I -` ad hoc, cuya salida fue `shapes con >1 secuencia de paradas: {}`. En este feed,
  por tanto, patrón = `shape_id` sin pérdida. Ninguna forma se comparte entre líneas.
- Cada forma empieza y acaba a menos de 100 m de la primera y la última parada de su patrón.

### 2. `shape_id` y `trip_headsign`

- Viajes sin `shape_id`: **0**. Viajes sin `trip_headsign`: **0** (de 20 598). Además,
  `trip_short_name == trip_id` en todos.
- En todos los patrones, el `trip_headsign` es único y coincide literalmente con el
  `stop_name` de la última parada. No hay ninguna excepción. Lo comprobé con un `python3 -I -`
  ad hoc sobre el JSON de `02`, que no imprimió ningún caso `HS!=last`.
- **Espacios sobrantes** (`03_checks.py`):
  - 38 `stop_name` con espacios al final o dobles, como `'La Malva-rosa - Mendizábal '` o
    `'Doctor J.J. Dòmine  - Edifici del Rellotge'`.
  - El headsign `'Terramelar '` (441 viajes de la 62) lleva un espacio al final.
  - Dos `route_long_name` tienen doble espacio.

### 3. Horas ≥ 24:00:00

- **Sí.** El `arrival_time` máximo es **`28:00:01`**, en el viaje `24_1040_602_2253_2172_3_031`
  de la línea 24, que sale a `27:19:00`.
- 16 600 filas, de 725 viajes de 24 líneas, tienen `arrival_time ≥ 24:00:00`. De esos viajes,
  **621 empiezan después de las 24:00**; por ejemplo, `4_1017_562_1585_2403_3_094` sale a
  `24:30:00`.
- Las últimas llegadas de las líneas 99 (`27:52:56`) y 24 (`28:00:01`) superan las 27 h.
- Ninguna fila tiene `arrival_time` vacío.

### 4. Paradas 508 y 2070

| Parada | Nombre | Líneas |
|---|---|---|
| 508 | Parc de l'Oest - Enguera | **70, 93** |
| 2070 | Ciutat Administrativa 9 d'Octubre - Cieza | **73, 95, 98, 99** |

Viajes del feed completo que pasan por 2070: 73 → 435, 99 → 383, 98 → 141, 95 → 100.

**Ninguna de las líneas de `gtfs_mini` (70, 93, C2) sirve la 2070.** Design §8 ya contempla añadir
una línea en ese caso. Tamaño estimado de la fixture con los días 2026-11-03 y 2026-11-04
(`06_fixture_size.py`):
- 70 + 93 + C2 + 73: ≈ 1,39 MB.
- 70 + 93 + C2 + 98: ≈ 1,40 MB.
- 70 + 93 + C2 + 95: ≈ 1,64 MB.
- 70 + 93 + C2 + 99: ≈ 1,80 MB.
- A cualquiera de ellas hay que sumar < 0,1 MB del resto de ficheros.

### 5 y 8. Patrones por línea y sentidos derivados con §4.3

Resultado global (`02_derive_directions.py`):
- **Las 42 líneas con viajes salen con exactamente dos sentidos (0 y 1).** No hay ninguna con
  uno ni con más de dos.
- **Ninguna línea es circular** según la regla de §4.3. La distancia mínima entre los extremos
  del patrón de referencia es de 1 382 m (C1). La rama circular (paso 3) **no se activa nunca**
  con este feed.
- En las líneas lineales, todas las asignaciones tienen un margen holgado. El margen mínimo,
  `|c_igual − c_inverso|`, es de 2 386 m, en los patrones `996_*` de C2. En el resto de
  variantes supera los 6 700 m.
- Cada patrón tiene un solo par (primera, última parada), un solo número de paradas y un solo
  headsign.

Tabla completa, generada con `05_directions_table.py`. "Tipo" es la clasificación de §4.3, con la
distancia entre O y D del patrón de referencia. "Patrón principal" es el de más viajes del
sentido.

| Línea | Tipo (§4.3) | Sentido | Patrones (viajes) | Headsigns (viajes) | Primera → última (patrón principal) | Viajes | Anomalías |
|---|---|---|---|---|---|---|---|
| 4 | lineal (4600 m) | 0 | 1017_1585_2403 (340) | Plaça de l'Ajuntament - Ateneu (340) | 1585 Natzaret → 2403 Plaça de l'Ajuntament - Ateneu | 340 | — |
| 4 | lineal (4600 m) | 1 | 1017_2403_1585 (333) | Natzaret (333) | 2403 Plaça de l'Ajuntament - Ateneu → 1585 Natzaret | 333 | — |
| 6 | lineal (5910 m) | 0 | 1057_2085_2158 (208) | Bulevard Sud (via de servici) - Hospital La Fe (208) | 2085 Torrefiel → 2158 Bulevard Sud (via de servici) - Hospital La Fe | 208 | — |
| 6 | lineal (5910 m) | 1 | 1057_2158_2085 (206) | Torrefiel (206) | 2158 Bulevard Sud (via de servici) - Hospital La Fe → 2085 Torrefiel | 206 | — |
| 7 | lineal (3562 m) | 0 | 1061_1940_2288 (269) | Mercat Central - Beata (269) | 1940 Fonteta de Sant Lluís → 2288 Mercat Central - Beata | 269 | — |
| 7 | lineal (3562 m) | 1 | 1061_2288_1940 (268) | Fonteta de Sant Lluís (268) | 2288 Mercat Central - Beata → 1940 Fonteta de Sant Lluís | 268 | — |
| 8 | lineal (3789 m) | 0 | 1066_2410_2255 (350) | Porta de la Mar - Glorieta (350) | 2410 Gonzalo Tejero Langarita - Vicente Chuliá Campos → 2255 Porta de la Mar - Glorieta | 350 | — |
| 8 | lineal (3789 m) | 1 | 1066_2255_2410 (347) | Gonzalo Tejero Langarita - Vicente Chuliá Campos (347) | 2255 Porta de la Mar - Glorieta → 2410 Gonzalo Tejero Langarita - Vicente Chuliá Campos | 347 | — |
| 9 | lineal (4049 m) | 0 | 922_585_2312 (326) | Sant Pau - Estació del Nord (326) | 585 Forn d'Alcedo → 2312 Sant Pau - Estació del Nord | 326 | — |
| 9 | lineal (4049 m) | 1 | 922_2312_585 (322) | Forn d'Alcedo (322) | 2312 Sant Pau - Estació del Nord → 585 Forn d'Alcedo | 322 | — |
| 10 | lineal (5292 m) | 0 | 923_1440_1240 (290) | Benimaclet - Lliri Blau (290) | 1440 Sant Marcel·lí → 1240 Benimaclet - Lliri Blau | 290 | — |
| 10 | lineal (5292 m) | 1 | 923_1240_1440 (274) | Sant Marcel·lí (274) | 1240 Benimaclet - Lliri Blau → 1440 Sant Marcel·lí | 274 | — |
| 11 | lineal (5324 m) | 0 | 1056_1229_2380 (277) | Patraix (277) | 1229 Els Orriols - Metro Sant Miquel dels Reis → 2380 Patraix | 277 | — |
| 11 | lineal (5324 m) | 1 | 1056_2380_1229 (270) | Els Orriols - Metro Sant Miquel dels Reis (270) | 2380 Patraix → 1229 Els Orriols - Metro Sant Miquel dels Reis | 270 | — |
| 12 | lineal (4270 m) | 0 | 827_1326_764 (119) | Plaça d'Amèrica - Pont d'Aragó (119) | 1326 Ciutat de l'Artista Faller → 764 Plaça d'Amèrica - Pont d'Aragó | 119 | — |
| 12 | lineal (4270 m) | 1 | 827_764_1326 (114) | Ciutat de l'Artista Faller (114) | 764 Plaça d'Amèrica - Pont d'Aragó → 1326 Ciutat de l'Artista Faller | 114 | — |
| 13 | lineal (3326 m) | 0 | 1021_1940_2250 (95) | Porta de la Mar - Navarro Reverter (parell) (95) | 1940 Fonteta de Sant Lluís → 2250 Porta de la Mar - Navarro Reverter (parell) | 95 | — |
| 13 | lineal (3326 m) | 1 | 1021_2250_1940 (93) | Fonteta de Sant Lluís (93) | 2250 Porta de la Mar - Navarro Reverter (parell) → 1940 Fonteta de Sant Lluís | 93 | — |
| 14 | lineal (5119 m) | 0 | 983_2376_2279 (297) | Marqués de Sotelo - Plaça de l'Ajuntament (297) | 2376 Castellar - l'Oliveral - Doctor Ruiz i Comes → 2279 Marqués de Sotelo - Plaça de l'Ajuntament | 297 | — |
| 14 | lineal (5119 m) | 1 | 983_2279_2376 (292) | Castellar - l'Oliveral - Doctor Ruiz i Comes (292) | 2279 Marqués de Sotelo - Plaça de l'Ajuntament → 2376 Castellar - l'Oliveral - Doctor Ruiz i Comes | 292 | — |
| 16 | lineal (7232 m) | 0 | 1022_2391_2014 (293) | Poeta Querol - Teatre Principal (293) | 2391 Vinalesa - Plaça d'Ausiàs March → 2014 Poeta Querol - Teatre Principal | 293 | — |
| 16 | lineal (7232 m) | 1 | 1022_2014_2391 (290) | Vinalesa - Plaça d'Ausiàs March (290) | 2014 Poeta Querol - Teatre Principal → 2391 Vinalesa - Plaça d'Ausiàs March | 290 | — |
| 18 | lineal (5273 m) | 0 | 1045_2320_1949 (113) | Universitats - Facultat de Magisteri (113) | 2320 Hospital Doctor Peset - Primer de Maig → 1949 Universitats - Facultat de Magisteri | 113 | — |
| 18 | lineal (5273 m) | 1 | 1045_1949_2320 (111) | Hospital Doctor Peset - Primer de Maig (111) | 1949 Universitats - Facultat de Magisteri → 2320 Hospital Doctor Peset - Primer de Maig | 111 | — |
| 19 | lineal (4638 m) | 0 | 930_18_2314 (352) | Periodista Azzati - Plaça de l'Ajuntament (352) | 18 La Malva-rosa - Cavite → 2314 Periodista Azzati - Plaça de l'Ajuntament | 352 | — |
| 19 | lineal (4638 m) | 1 | 930_2314_18 (343) | La Malva-rosa - Cavite (343) | 2314 Periodista Azzati - Plaça de l'Ajuntament → 18 La Malva-rosa - Cavite | 343 | — |
| 24 | lineal (18395 m) | 0 | 1040_2172_2253 (62) | Porta de la Mar - General Palanca (62) | 2172 El Palmar → 2253 Porta de la Mar - General Palanca | 62 | route 1068 sin viajes |
| 24 | lineal (18395 m) | 1 | 1040_2253_2172 (62) | El Palmar (62) | 2253 Porta de la Mar - General Palanca → 2172 El Palmar | 62 | route 1068 sin viajes |
| 25 | lineal (23399 m) | 0 | 1026_2186_2253 (158) | Porta de la Mar - General Palanca (158) | 2186 El Perelló → 2253 Porta de la Mar - General Palanca | 158 | — |
| 25 | lineal (23399 m) | 1 | 1026_2253_2186 (158) | El Perelló (158) | 2253 Porta de la Mar - General Palanca → 2186 El Perelló | 158 | — |
| 26 | lineal (8082 m) | 0 | 1027_2105_2014 (49) | Poeta Querol - Teatre Principal (49) | 2105 Moncada - Alfara → 2014 Poeta Querol - Teatre Principal | 49 | — |
| 26 | lineal (8082 m) | 1 | 1027_2014_2105 (46) | Moncada - Alfara (46) | 2014 Poeta Querol - Teatre Principal → 2105 Moncada - Alfara | 46 | — |
| 27 | lineal (5042 m) | 0 | 1060_586_2290 (147) | Avinguda de l'Oest - Hospital (147) | 586 La Torre → 2290 Avinguda de l'Oest - Hospital | 147 | — |
| 27 | lineal (5042 m) | 1 | 1060_2290_586 (144) | La Torre (144) | 2290 Avinguda de l'Oest - Hospital → 586 La Torre | 144 | — |
| 28 | lineal (3839 m) | 0 | 1034_1326_2277 (382) | Xàtiva - Institut Lluís Vives (382) | 1326 Ciutat de l'Artista Faller → 2277 Xàtiva - Institut Lluís Vives | 382 | — |
| 28 | lineal (3839 m) | 1 | 1034_2277_1326 (380) | Ciutat de l'Artista Faller (380) | 2277 Xàtiva - Institut Lluís Vives → 1326 Ciutat de l'Artista Faller | 380 | — |
| 31 | lineal (5912 m) | 0 | 1053_2248_2284 (208) | Estació Joaquín Sorolla (208) | 2248 La Patacona - Institut → 2284 Estació Joaquín Sorolla | 208 | — |
| 31 | lineal (5912 m) | 1 | 1053_2284_2248 (202) | La Patacona - Institut (202) | 2284 Estació Joaquín Sorolla → 2248 La Patacona - Institut | 202 | — |
| 32 | lineal (4615 m) | 0 | 1029_1162_2403 (288) | Plaça de l'Ajuntament - Ateneu (288) | 1162 Passeig Marítim - Mendizábal → 2403 Plaça de l'Ajuntament - Ateneu | 288 | — |
| 32 | lineal (4615 m) | 1 | 1029_2403_1162 (278) | Passeig Marítim - Mendizábal (278) | 2403 Plaça de l'Ajuntament - Ateneu → 1162 Passeig Marítim - Mendizábal | 278 | — |
| 35 | lineal (2483 m) | 0 | 935_1950_2279 (318) | Marqués de Sotelo - Plaça de l'Ajuntament (318) | 1950 Pere II el Cerimoniós - Luis Merelo y Mas → 2279 Marqués de Sotelo - Plaça de l'Ajuntament | 318 | — |
| 35 | lineal (2483 m) | 1 | 935_2279_1950 (312) | Pere II el Cerimoniós - Luis Merelo y Mas (312) | 2279 Marqués de Sotelo - Plaça de l'Ajuntament → 1950 Pere II el Cerimoniós - Luis Merelo y Mas | 312 | — |
| 40 | lineal (2921 m) | 0 | 1030_1282_2278 (112) | Estació del Nord - Marqués de Sotelo (112) | 1282 Universitats - Facultat de Ciències Socials → 2278 Estació del Nord - Marqués de Sotelo | 112 | — |
| 40 | lineal (2921 m) | 1 | 1030_2278_1282 (111) | Universitats - Facultat de Ciències Socials (111) | 2278 Estació del Nord - Marqués de Sotelo → 1282 Universitats - Facultat de Ciències Socials | 111 | — |
| 59 | lineal (4461 m) | 0 | 1070_2285_2437 (135) | Ignacio Hernández Hervas - Ruíz (135) | 2285 Estació del Nord - Sant Agustí → 2437 Ignacio Hernández Hervas - Ruíz | 135 | empate de viajes (135/135): ref por `shape_id` menor |
| 59 | lineal (4461 m) | 1 | 1070_2437_2285 (135) | Estació del Nord - Sant Agustí (135) | 2437 Ignacio Hernández Hervas - Ruíz → 2285 Estació del Nord - Sant Agustí | 135 | ídem |
| 60 | lineal (3358 m) | 0 | 966_2085_1520 (327) | Sant Agustí (327) | 2085 Torrefiel → 1520 Sant Agustí | 327 | — |
| 60 | lineal (3358 m) | 1 | 966_1520_2085 (319) | Torrefiel (319) | 1520 Sant Agustí → 2085 Torrefiel | 319 | — |
| 62 | lineal (5755 m) | 0 | 967_390_2289 (283)<br>1077_390_2289 (165) | Avinguda de l'Oest - Roger de Flor (448) | 390 Terramelar → 2289 Avinguda de l'Oest - Roger de Flor | 448 | MULTI-ROUTE 967+1077 (mismos extremos; 1077 = días lectivos, recorrido distinto en un 19 % de puntos) |
| 62 | lineal (5755 m) | 1 | 967_2289_390 (279)<br>1077_2289_390 (162) | Terramelar␠ (441) | 2289 Avinguda de l'Oest - Roger de Flor → 390 Terramelar | 441 | MULTI-ROUTE; headsign con espacio final |
| 63 | lineal (6089 m) | 0 | 968_2359_1145 (47) | Campus de Burjassot (47) | 2359 Bailén - Ermita → 1145 Campus de Burjassot | 47 | — |
| 63 | lineal (6089 m) | 1 | 968_1145_2359 (45) | Bailén - Ermita (45) | 1145 Campus de Burjassot → 2359 Bailén - Ermita | 45 | — |
| 64 | lineal (5830 m) | 0 | 1076_1824_1946 (332) | Bulevard Sud (imparell) - Hospital La Fe (332) | 1824 Benicalap - Joan XXIII → 1946 Bulevard Sud (imparell) - Hospital La Fe | 332 | — |
| 64 | lineal (5830 m) | 1 | 1076_1946_1824 (325) | Benicalap - Joan XXIII (325) | 1946 Bulevard Sud (imparell) - Hospital La Fe → 1824 Benicalap - Joan XXIII | 325 | — |
| 67 | lineal (3416 m) | 0 | 995_1657_2309 (215) | Bailén - Estació del Nord (215) | 1657 Nou Campanar - Hospital Arnau de Vilanova → 2309 Bailén - Estació del Nord | 215 | — |
| 67 | lineal (3416 m) | 1 | 995_2309_1657 (213) | Nou Campanar - Hospital Arnau de Vilanova (213) | 2309 Bailén - Estació del Nord → 1657 Nou Campanar - Hospital Arnau de Vilanova | 213 | — |
| 70 | lineal (5797 m) | 0 | 1058_2030_500 (303) | La Fontsanta (303) | 2030 Alboraia → 500 La Fontsanta | 303 | — |
| 70 | lineal (5797 m) | 1 | 1058_500_2030 (302) | Alboraia (302) | 500 La Fontsanta → 2030 Alboraia | 302 | — |
| 71 | lineal (6228 m) | 0 | 1059_1366_1282 (206) | Universitats - Facultat de Ciències Socials (206) | 1366 La Llum → 1282 Universitats - Facultat de Ciències Socials | 206 | — |
| 71 | lineal (6228 m) | 1 | 1059_1282_1366 (201) | La Llum (201) | 1282 Universitats - Facultat de Ciències Socials → 1366 La Llum | 201 | — |
| 72 | lineal (2802 m) | 0 | 970_1936_2277 (169) | Xàtiva - Institut Lluís Vives (169) | 1936 Sant Isidre → 2277 Xàtiva - Institut Lluís Vives | 169 | — |
| 72 | lineal (2802 m) | 1 | 970_2277_1936 (165) | Sant Isidre (165) | 2277 Xàtiva - Institut Lluís Vives → 1936 Sant Isidre | 165 | — |
| 73 | lineal (2852 m) | 0 | 963_1936_2312 (278)<br>962_1936_2312 (165) | Sant Pau - Estació del Nord (443) | 1936 Sant Isidre → 2312 Sant Pau - Estació del Nord | 443 | MULTI-ROUTE 962+963 (mismos extremos) |
| 73 | lineal (2852 m) | 1 | 963_2312_1936 (273)<br>962_2312_1936 (162) | Sant Isidre (435) | 2312 Sant Pau - Estació del Nord → 1936 Sant Isidre | 435 | MULTI-ROUTE 962+963 |
| 81 | lineal (3554 m) | 0 | 1041_1210_2278 (107) | Estació del Nord - Marqués de Sotelo (107) | 1210 Blasco Ibáñez - Serradora → 2278 Estació del Nord - Marqués de Sotelo | 107 | — |
| 81 | lineal (3554 m) | 1 | 1041_2278_1210 (105) | Blasco Ibáñez - Serradora (105) | 2278 Estació del Nord - Marqués de Sotelo → 1210 Blasco Ibáñez - Serradora | 105 | — |
| 92 | lineal (5771 m) | 0 | 1046_1272_1546 (192) | La Malva-rosa - Gran Canària (192) | 1272 Campanar - Monestir de Poblet → 1546 La Malva-rosa - Gran Canària | 192 | — |
| 92 | lineal (5771 m) | 1 | 1046_1546_1272 (190) | Campanar - Monestir de Poblet (190) | 1546 La Malva-rosa - Gran Canària → 1272 Campanar - Monestir de Poblet | 190 | — |
| 93 | lineal (7860 m) | 0 | 994_488_2271 (418) | Passeig Marítim - Hospital Malva-rosa (418) | 488 Avinguda del Cid → 2271 Passeig Marítim - Hospital Malva-rosa | 418 | — |
| 93 | lineal (7860 m) | 1 | 994_2271_488 (403) | Avinguda del Cid (403) | 2271 Passeig Marítim - Hospital Malva-rosa → 488 Avinguda del Cid | 403 | — |
| 94 | lineal (5581 m) | 0 | 873_2324_2307 (168) | Campanar - General Avilés (illeta) (168) | 2324 França - Camí Fondo del Grao → 2307 Campanar - General Avilés (illeta) | 168 | — |
| 94 | lineal (5581 m) | 1 | 873_2307_2324 (167) | França - Camí Fondo del Grao (167) | 2307 Campanar - General Avilés (illeta) → 2324 França - Camí Fondo del Grao | 167 | — |
| 95 | lineal (6873 m) | 0 | 1047_504_2263 (103) | La Marina - Metro Neptú (103) | 504 Tres Creus (imparell) - Hospital General → 2263 La Marina - Metro Neptú | 103 | — |
| 95 | lineal (6873 m) | 1 | 1047_2263_504 (100) | Tres Creus (imparell) - Hospital General (100) | 2263 La Marina - Metro Neptú → 504 Tres Creus (imparell) - Hospital General | 100 | — |
| 98 | lineal (7693 m) | 0 | 1055_487_2271 (74)<br>1054_487_2229 (71) | Passeig Marítim - Hospital Malva-rosa (74)<br>Estació del Cabanyal (71) | 487 Cid - Pere Maria Orts → 2271 Passeig Marítim - Hospital Malva-rosa | 145 | VARIANTE 1054 (laborables) acaba en 2229, no en 2271 (c_igual 952 m frente a c_inverso 14 519 m: correcto)<br>MULTI-ROUTE 1054+1055 |
| 98 | lineal (7693 m) | 1 | 1055_2271_487 (72)<br>1054_2229_487 (69) | Cid - Pere Maria Orts (141) | 2271 Passeig Marítim - Hospital Malva-rosa → 487 Cid - Pere Maria Orts | 141 | VARIANTE 1054 empieza en 2229<br>MULTI-ROUTE |
| 99 | lineal (6279 m) | 0 | 1052_2230_1751 (383) | Mendizábal - Doctor Álvaro López (383) | 2230 Palau de Congressos → 1751 Mendizábal - Doctor Álvaro López | 383 | — |
| 99 | lineal (6279 m) | 1 | 1052_1751_2230 (379) | Palau de Congressos (379) | 1751 Mendizábal - Doctor Álvaro López → 2230 Palau de Congressos | 379 | — |
| C1 | lineal (1382 m) | 0 | 1018_1959_2277 (165) | Xàtiva - Institut Lluís Vives (165) | 1959 Blanqueria - Pare d'Òrfens → 2277 Xàtiva - Institut Lluís Vives | 165 | **BUCLE de un solo giro (horario) partido en dos medios viajes** → §4.3 da 2 sentidos |
| C1 | lineal (1382 m) | 1 | 1018_2277_1959 (163) | Blanqueria - Pare d'Òrfens (163) | 2277 Xàtiva - Institut Lluís Vives → 1959 Blanqueria - Pare d'Òrfens | 163 | ídem |
| C2 | lineal (2185 m) | 0 | 651_166_691 (56)<br>996_1057_346 (52) | Plaça d'Espanya - Ermita (56)<br>Estació d'autobusos (52) | 166 Blasco Ibáñez - Facultat de Geografia → 691 Plaça d'Espanya - Ermita | 108 | **Dos bucles de giro opuesto (651 horario, 996 antihorario), cada uno partido en dos medios viajes.** El sentido 0 mezcla medio bucle de cada giro (ambos van de este a oeste). Margen 2 386 m (el menor del feed)<br>VARIANTE, MULTI-ROUTE |
| C2 | lineal (2185 m) | 1 | 651_691_166 (54)<br>996_346_1057 (53) | Blasco Ibáñez - Facultat de Geografia (54)<br>Estadi de Mestalla (front) (53) | 691 Plaça d'Espanya - Ermita → 166 Blasco Ibáñez - Facultat de Geografia | 107 | ídem (de oeste a este) |
| C3 | lineal (3641 m) | 0 | 1074_231_1265 (471)<br>1075_229_1266 (448) | Conselleria d'Educació (471)<br>Avinguda Campanar - Centre de Salut (448) | 231 Eduard Boscà - Balears → 1265 Conselleria d'Educació | 919 | **Dos bucles de giro opuesto (1074 antihorario, 1075 horario)** con giros de cabecera a unos 200–400 m. El sentido 0 equivale a "hacia Campanar" por cualquiera de los dos lados del bucle<br>VARIANTE, MULTI-ROUTE |
| C3 | lineal (3641 m) | 1 | 1074_1265_231 (470)<br>1075_1266_229 (450) | Eduard Boscà - Balears (470)<br>Cardenal Benlloch (imparell) - Port (450) | 1265 Conselleria d'Educació → 231 Eduard Boscà - Balears | 920 | ídem ("hacia el Port") |

#### Evidencia de que C1, C2 y C3 son bucles partidos en medios viajes (`03_checks.py`, `04_loops_and_coverage.py`)

Dentro de cada `route_id` hay dos patrones, P y Q, con `P.última = Q.primera` y
`Q.última = P.primera`. Solo comparten 2 paradas, los extremos. Eso también ocurre en las líneas
lineales, porque cada acera tiene su `stop_id`; lo que las distingue es la **distancia mediana**
entre P y Q. En las líneas lineales, ida y vuelta van por las mismas calles; en los bucles, cada
medio viaje recorre un lado distinto:

| route_id (línea) | área P (m²) | área Q (m²) | área P+Q (m²) | mediana d(P,Q) |
|---|---|---|---|---|
| 1018 (C1) | −814 628 | −661 464 | −1 476 091 (horario) | **722 m** |
| 651 (C2) | −1 267 233 | −2 304 259 | −3 571 492 (horario) | **688 m** |
| 996 (C2) | 740 072 | 3 180 929 | 3 921 001 (antihorario) | **841 m** |
| 1074 (C3) | 4 741 930 | 5 010 330 | 9 752 260 (antihorario) | **1 309 m** |
| 1075 (C3) | −5 157 523 | −4 119 078 | −9 276 600 (horario) | **1 453 m** |
| resto (37 route_id lineales) | — | — | — | **9–169 m** (máx. línea 6) |

- Hay una separación clara entre 169 m y 688 m.
- El cociente de áreas `|área(P+Q)| / (|área P| + |área Q|)` **no** sirve para distinguir bucles.
  Las líneas 10, 26, 27 y 28 también dan 1,00, porque ida y vuelta casi se superponen con área
  pequeña del mismo signo.
- Entre `route_id` de la misma línea circular no hay paradas comunes: 0 paradas compartidas
  entre 651 y 996, y entre 1074 y 1075.

#### Cobertura de la forma representativa por sentido (`04_loops_and_coverage.py`)

`line_direction.shape_id` (design §5, paso 4) es el `shape_id` con más viajes del sentido. Para
los demás patrones del mismo sentido, este es el porcentaje de sus puntos que queda a más de
150 m de esa forma (umbral de CU-08 4b):

| Línea/sentido | Forma representativa | Otro patrón | % de puntos a > 150 m |
|---|---|---|---|
| 62 / 0 | 967_390_2289 | 1077_390_2289 | 19 % |
| 62 / 1 | 967_2289_390 | 1077_2289_390 | 12 % |
| 73 / 0 | 963_1936_2312 | 962_1936_2312 | 6 % |
| 73 / 1 | 963_2312_1936 | 962_2312_1936 | 8 % |
| 98 / 0 | 1055_487_2271 | 1054_487_2229 | 11 % |
| 98 / 1 | 1055_2271_487 | 1054_2229_487 | 3 % |
| **C2 / 0** | 651_166_691 | 996_1057_346 | **72 %** |
| **C2 / 1** | 651_691_166 | 996_346_1057 | **57 %** |
| **C3 / 0** | 1074_231_1265 | 1075_229_1266 | **85 %** |
| **C3 / 1** | 1074_1265_231 | 1075_1266_229 | **99 %** |

#### Respuesta a la pregunta 8

- Con el criterio literal de E-01, **ninguna** línea da un número de sentidos distinto de dos.
- La única que incumple "uno, si es circular de un solo giro" es **C1**. Geométricamente es un
  bucle horario de un solo giro, pero §4.3 no la detecta como circular y le asigna 2 sentidos.
- Hay incoherencias de significado en **3 líneas: C1, C2 y C3**. §4.3 las trata como lineales,
  pero son circulares: sus sentidos son "medio bucle de A a B" y "medio bucle de B a A", no
  giros. En C2 y C3, cada sentido mezcla medios bucles de los dos giros.
- El resto de anomalías (62, 73, 98: varios `route_id` o variante corta en el mismo sentido) son
  **coherentes**: los extremos están a < 1 km de los de la referencia y el margen es > 6 km.

### 6. Líneas circulares (extremos < 500 m)

Con la regla de §4.3 **no hay ninguna**: la distancia mínima entre O y D es de 1 382 m (C1). Las
líneas que son circulares de verdad (C1, C2 "Circular Grans Vies" y C3 "Circular Ronda
Trànsits") vienen en el feed como **medios viajes**, con un headsign de destino en cada mitad.

### 7. Significado aparente de los identificadores (solo informativo)

Lo comprobé con `03_checks.py` y con dos `python3 -I -` ad hoc.

- **`shape_id` = `<route_id>_<stop_id primera parada>_<stop_id última parada>`.** Se cumple en
  los 20 598 viajes; por ejemplo, `1017_1585_2403` va de Natzaret a Ateneu.
- **`service_id` = `<código interno de línea>_<route_id>_<tipo de día>[_EXC]`.** Ejemplos de
  tipo de día en la línea 4: `601` de lunes a jueves, `562` viernes, `603` sábado, `609`
  domingo, según `calendar.txt`. El sufijo `_EXC` aparece en los servicios de
  `calendar_dates.txt` con `exception_type = 1`.
- **`trip_id` = `<service_id>_<origen>_<destino>_<n>_<secuencia de 3 dígitos>`.**
  - El primer campo es un **código interno de línea**, que coincide con `route_short_name` en
    17 168 de 20 598 viajes. Las excepciones son C1 → `5`, 98 → `38`, 99 → `39`,
    C2 → `79`/`80` y C3 → `89`/`90`.
  - `<n>` (valores 2–6) parece un código interno de itinerario o variante. En la línea 4,
    `3` = ida y `4` = vuelta. En la línea 70, la forma `1058_2030_500` tiene viajes con `2` y
    con `4`, con la misma secuencia de paradas.
  - `(línea, route, servicio, n, secuencia)` no es único (32 duplicados), así que el formato no
    garantiza nada.
- Conclusión: **el sistema no debe depender de estos formatos**, como ya dice la spec. Ningún
  hallazgo de este informe se basa en ellos; todos se calculan con columnas GTFS.

### Otros hallazgos relevantes para la implementación

- **2026-11-03 (martes) y 2026-11-04 (miércoles)** tienen los mismos servicios para 70, 93 y C2:
  167, 267 y 215 viajes (`03_checks.py`). La fixture tendrá viajes que empiezan después de las
  24:00, porque 70 y 93 tienen 40 y 44 viajes así en el feed completo. Eso sirve para AC-27 y el
  caso de madrugada de T-09.
- La línea 59 empata en viajes (135/135) y se resuelve con el criterio "`shape_id` menor". Este
  orden es lexicográfico sobre cadenas (`1070_2285_2437` < `1070_2437_2285`); conviene que el
  test lo fije.

## Impacto en la spec

1. **AC-25 (verificación de integración "C2") no se puede cumplir con el feed real.** Según la
   regla de 500 m, C2 no es circular: la distancia entre O y D del patrón de referencia
   `651_166_691` es de 2 185 m, así que en `gtfs_mini` pasa por la rama lineal. Además,
   `docs/architecture.md` (`derive_directions`: "…o de su orientación (circulares)") da por hecho
   que hay líneas circulares detectables, y en este feed no las hay. **Contradicción entre spec y
   datos: hace falta decidirlo en CP-3.** Propuesta:
   - **Opción A (recomendada, mínima):** mantener §4.3 tal cual y cambiar:
     - En AC-25, la verificación pasa a ser solo *unit* (formas sintéticas horaria, antihoraria y
       degenerada).
     - En AC-24, la integración añade: "C2 en `gtfs_mini` da exactamente dos sentidos, cada uno
       con dos patrones de `route_id` distintos".
     - En design §4.3, una nota: "En el feed de EMT (23-10-2026) las líneas circulares C1, C2 y
       C3 vienen partidas en medios viajes con headsign de destino. §4.3 las trata como lineales
       y sus sentidos significan 'hacia el extremo X del medio bucle'. La rama circular queda
       para feeds que modelen el bucle completo en un viaje."

     Así, el sentido es coherente con los headsigns (cada sentido de C1, C2 y C3 tiene sus
     propios destinos) y con cómo opera EMT (el conductor cambia de viaje en cada cabecera, igual
     que en una línea lineal).
   - **Opción B (sentido = giro):** añadir a §4.3 un paso previo de **detección de bucles
     partidos**. Dos patrones P y Q del mismo `route_id` forman un bucle si cumplen las tres
     condiciones:
     - `P.última = Q.primera`;
     - `Q.última = P.primera`;
     - distancia mediana de P a Q > 300 m (en el feed: lineales ≤ 169 m, bucles ≥ 688 m).

     El giro del bucle es el signo del área de P+Q, y a cada bucle se le asigna sentido por giro
     respecto al bucle de referencia. Resultado:
     - C1: un solo sentido.
     - C2: sentido 0 para `651_*` (horario) y sentido 1 para `996_*` (antihorario).
     - C3: sentido 0 para `1074_*` y sentido 1 para `1075_*`.

     Desventajas:
     - Cada sentido tendría dos headsigns que cambian a mitad de recorrido.
     - El `headsign` de `line_direction` deja de describir el sentido.
     - La forma representativa tendría que ser la concatenación de P y Q.
     - Hay más superficie de test.
2. **`line_direction.shape_id` como única forma del sentido (design §5, paso 4; AC-10 y AC-17).**
   - En C2 y C3, entre el 57 % y el 99 % de los puntos de los otros patrones del sentido quedan a
     más de 150 m de la forma representativa. En la 62 queda hasta un 19 %.
   - Si las features posteriores (CU-08 4b, el trazado de CU de pasajero) usan solo esa forma,
     darán falsos "no estás en el recorrido".
   - Propuesta: añadir al puerto `shapes_for_direction(line, direction_id) -> list[str]` (o una
     tabla `line_direction_shape(fv, short_name, direction_id, shape_id, trip_count)`), o dejar
     constancia en la spec de que AC-17 devuelve solo la forma principal y que las features
     consumidoras deben tenerlo en cuenta.
   - No bloquea esta feature, pero conviene decidirlo ahora porque afecta al esquema.
3. **Líneas sin viajes (23 y 30) y `route_id` sin viajes (1068).**
   - Design §5, paso 1 ("`line`: por `short_name`, atributos del `route_id` con más viajes") no
     dice si una línea con 0 viajes se incluye.
   - Propuesta: "solo se crean líneas con al menos un viaje; los `route_id` sin viajes se
     ignoran (se cuentan en el resumen de importación)".
   - Con el feed real habría **42 líneas** (la cifra ilustrativa de design §3 es 46).
4. **AC-07 y headsigns.** AC-07 elimina los espacios al principio y al final de los nombres de
   paradas y líneas, pero no dice nada de `trip_headsign`. El headsign `'Terramelar '` (441
   viajes) no coincidiría con el nombre de parada ya recortado `'Terramelar'`. Propuesta: aplicar
   el mismo recorte a `trip_headsign` (y a la alternativa "nombre de la última parada").
5. **Design §8, parada 2070.** Ninguna de las líneas 70, 93 y C2 la sirve. Propuesta: añadir la
   **98** (≈ +0,31 MB, total ≈ 1,40 MB).
   - Además de servir la 2070, aporta una **variante corta en el mismo sentido** (`1054_487_2229`)
     y dos `route_id`. Así, AC-24 tiene un caso de integración real de "variante corta" y no
     solo sintético.
   - La alternativa más pequeña es la 73 (≈ 1,39 MB), pero solo aporta dos `route_id` con los
     mismos extremos.
   - El README de la fixture debe documentarlo, como ya pide design §8.

## Riesgos

- **Semántica del sentido en las líneas circulares (C1, C2, C3).** Con §4.3 tal cual, "sentido"
  significa "hacia el extremo X del medio bucle". Si el SAE informa de un destino que no casa con
  esos headsigns (por ejemplo "Circular"), `DirectionResolver` fallará en esas líneas. No se
  puede comprobar sin grabaciones del SAE: conviene incluirlo en la exploración de
  `stop_arrivals_api`.
- **Forma por sentido** (Impacto 2): falsos "fuera de recorrido" para conductores de C2, C3 y,
  en menor medida, 62 y 98.
- **Horas hasta 28:00:01.** La consulta D / D−1 de design §3 lo cubre (< 48 h). Hay 621 viajes
  que empiezan después de las 24:00 y pertenecen al día de servicio anterior; si se calcula mal,
  esos viajes de madrugada desaparecen.
- **Feeds futuros.** Si EMT modela algún bucle completo en un solo viaje (extremos < 500 m), se
  activará la rama circular, que hoy solo está probada con datos sintéticos. El margen mínimo
  actual de la rama lineal (2 386 m, C2) es holgado.
- **Fragilidad del criterio de bucle** (si se elige la opción B): el umbral de 300 m sale de un
  único feed. El hueco entre 169 m y 688 m es amplio, pero habría que revalidarlo en cada feed
  con `gtfs info --directions`.

## Recomendación

- La derivación §4.3 se puede implementar tal cual para 39 de las 42 líneas, que dan dos
  sentidos limpios con márgenes amplios.
- Las incoherencias de significado afectan a **3 líneas (C1, C2, C3)**. No supera el umbral de
  "más de 3" de tasks.md, pero **la verificación de integración de AC-25 ("C2") contradice los
  datos**, así que hace falta un **CP-3 breve** antes de implementar.
- Recomiendo:
  - adoptar la **opción A** (aceptar medios bucles y ajustar las verificaciones de AC-24 y AC-25,
    más la nota en §4.3);
  - decidir ya el punto 2 (formas por sentido);
  - incorporar las aclaraciones 3–5 (líneas sin viajes, recorte de headsigns, línea 98 en
    `gtfs_mini`).
- No hace falta reexplorar: los scripts de `progress/explore_gtfs_feed_samples/` reproducen todo.

**Resumen para el orquestador:**
- E-01 está completo. Las 42 líneas con viajes dan exactamente 2 sentidos con §4.3.
- Ninguna línea es circular según la regla de 500 m: C1, C2 y C3 vienen como medios bucles.
- Por eso la verificación de integración de AC-25 sobre C2 es irrealizable, y C1 (bucle de un
  solo giro) recibe 2 sentidos.
- Otros datos: hay horas hasta 28:00:01; las líneas 23 y 30 no tienen viajes; la 2070 la sirven
  73, 95, 98 y 99, ninguna de `gtfs_mini`.
- **La spec no puede implementarse tal cual: requiere CP-3** (cambios pequeños en
  AC-24/AC-25/§4.3/§8 y decidir formas por sentido). Propuesta concreta: opción A y añadir la 98
  a `gtfs_mini`.
