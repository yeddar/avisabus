# Importación del GTFS — requirements

> Feature: `gtfs_import` · Versión: 1.2 · Estado: APPROVED
> Requisitos: RF-01, RF-02, RF-03, RF-04, RF-32 · Casos de uso: CU-11 · Depende de: project_scaffold

## Contexto

Toda la información de red (paradas, líneas, sentidos, horarios y trazados) procede del feed
GTFS estático de EMT València, que se renueva aproximadamente cada mes (el feed del 23-10-2026
es válido del 16-10-2026 al 22-11-2026). El administrador lo importa con la CLI. Otras features
consultan la red a través del puerto `NetworkRepository` que define esta feature.

Hechos conocidos del feed (ver `docs/vision.md` §5): `stop_id = stop_code` numérico (1117
paradas); una línea comercial puede tener varios `route_id` (24, 62, 73, 98, C2, C3); nombres en
valenciano; `wheelchair_boarding = 0` en todas las paradas; no incluye líneas nocturnas;
**`trips.txt` no incluye `direction_id`** (columnas: `route_id, service_id, trip_id,
trip_headsign, trip_short_name, shape_id`), por lo que el sentido se deriva al importar;
`shape_dist_traveled` viene en `stop_times` y `shapes`, en metros.

La exploración E-01 (`progress/explore_gtfs_feed.md`) confirmó además:
- 42 líneas con viajes (las 23 y 30 no tienen ninguno, y el `route_id` 1068 tampoco);
- horas de hasta `28:00:01` y 621 viajes que empiezan después de las 24:00;
- **las circulares C1, C2 y C3 vienen partidas en medios viajes**, cada uno con su destino, por
  lo que se tratan como líneas lineales: cada sentido significa "hacia el destino de ese medio
  bucle" (decisión de la persona en CP-3, opción A);
- en algunas líneas un mismo sentido tiene variantes de recorrido muy distintas (C2, C3, 62, 98).

## Alcance

- Comando `avisabus gtfs import <ruta>` (directorio o ZIP) y `avisabus gtfs info`.
- Validación de ficheros y columnas obligatorias.
- Almacenamiento versionado con activación atómica y borrado de la versión anterior.
- Datos derivados: líneas comerciales, **sentidos derivados** (el feed no los trae), sentidos y
  headsigns por parada.
- Cálculo de servicios activos por fecha.
- Aviso de caducidad del feed.
- Puerto `NetworkRepository` y su adaptador SQLite con las consultas de §Criterios.
- Fixture `gtfs_mini` y script para regenerarla.

## Fuera de alcance

- Descarga automática del feed desde internet.
- Frecuencias (`frequencies.txt`), transbordos, tarifas.
- Interpretación del ETA del SAE (feature `stop_arrivals_api`).

## Historias de usuario

- Como **administrador**, quiero importar el feed nuevo de EMT con un comando, sin parar el
  servicio, para que los horarios y paradas estén al día.
- Como **administrador**, quiero saber cuándo caduca el feed activo para renovarlo a tiempo.

## Criterios de aceptación

### Importación

- **gtfs_import.AC-01** — CUANDO el administrador ejecuta `avisabus gtfs import <dir>` con un
  feed válido, LA CLI DEBERÁ importar agency, routes, stops, trips, stop_times, shapes, calendar,
  calendar_dates y feed_info, activar la nueva versión, mostrar el número de líneas comerciales,
  paradas, viajes y horarios de parada importados, y terminar con código 0.
  *Verificación:* integration (gtfs_mini)
- **gtfs_import.AC-02** — CUANDO la ruta indicada es un fichero `.zip` con los mismos ficheros
  en su raíz, LA CLI DEBERÁ importarlo igual que un directorio.
  *Verificación:* integration
- **gtfs_import.AC-03** — SI falta un fichero obligatorio (agency, routes, stops, trips,
  stop_times, shapes, y al menos uno de calendar o calendar_dates), ENTONCES LA CLI DEBERÁ
  terminar con código 2, indicar el fichero que falta y mantener activa la versión anterior.
  *Verificación:* integration
- **gtfs_import.AC-04** — SI falta una columna obligatoria (design §4.1), ENTONCES LA CLI DEBERÁ
  terminar con código 2 indicando fichero y columna, y mantener activa la versión anterior.
  *Verificación:* integration
- **gtfs_import.AC-05** — SI la importación falla a mitad (error de datos o de E/S), ENTONCES
  EL SISTEMA DEBERÁ eliminar los datos parciales de la versión fallida y mantener activa y
  completa la versión anterior.
  *Verificación:* integration (inyección de fallo en el lector de `stop_times`)
- **gtfs_import.AC-06** — CUANDO una importación termina con éxito, EL SISTEMA DEBERÁ activar
  la nueva versión en una única transacción y borrar después los datos de la versión anterior.
  *Verificación:* integration (dos importaciones seguidas; solo queda una versión)
- **gtfs_import.AC-07** — EL SISTEMA DEBERÁ leer los ficheros como UTF-8 aceptando BOM y
  conservar los nombres de paradas y líneas y los `trip_headsign` (y el nombre de la última parada
  cuando se use como headsign) tal como vienen en el GTFS, eliminando solo espacios al principio y
  al final (p. ej. `'Terramelar '` → `'Terramelar'`).
  *Verificación:* unit
- **gtfs_import.AC-08** — EL SISTEMA DEBERÁ almacenar las horas de `stop_times` como segundos
  desde el inicio del día de servicio, admitiendo valores ≥ 24:00:00 (p. ej. `25:10:00` →
  `90600`).
  *Verificación:* unit

### Datos derivados

- **gtfs_import.AC-09** — EL SISTEMA DEBERÁ agrupar los `route_id` en una línea comercial por
  `route_short_name`, con nombre largo, color y color de texto del `route_id` con más viajes.
  *Verificación:* integration (C2 agrupa dos `route_id` en gtfs_mini)
- **gtfs_import.AC-10** — EL SISTEMA DEBERÁ calcular, para cada línea y `direction_id`, el
  `headsign` más frecuente entre sus viajes y el `shape_id` más frecuente (forma representativa).
  *Verificación:* unit/integration
- **gtfs_import.AC-11** — EL SISTEMA DEBERÁ precalcular qué pares (línea, sentido) sirven cada
  parada.
  *Verificación:* integration

### Sentido de los viajes

- **gtfs_import.AC-23** — DONDE `trips.txt` incluya `direction_id`, EL SISTEMA DEBERÁ usarlo y
  marcar los viajes con `direction_source = "feed"`.
  *Verificación:* integration (copia de `gtfs_mini` con columna añadida)
- **gtfs_import.AC-24** — SI `trips.txt` no incluye `direction_id`, ENTONCES EL SISTEMA DEBERÁ
  derivarlo por línea comercial según design §4.3: el patrón (`shape_id`) con más viajes define el
  sentido `0`; en líneas lineales cada patrón toma el sentido cuyos extremos (primera y última
  parada) están más cerca de los del patrón de referencia en el mismo orden; los viajes quedan
  marcados con `direction_source = "derived"`.
  *Verificación:* unit (patrones sintéticos: ida y vuelta, variante corta en el mismo sentido;
  empate de viajes resuelto por `shape_id` menor en orden lexicográfico) + integration (gtfs_mini:
  70, 93, 98 y C2 tienen exactamente dos sentidos; la variante corta `1054_487_2229` de la 98 queda
  en el mismo sentido que `1055_487_2271`; cada sentido de C2 tiene patrones de dos `route_id`)
- **gtfs_import.AC-25** — SI una línea es circular (extremos del patrón de referencia a menos de
  500 m), ENTONCES EL SISTEMA DEBERÁ asignar el sentido según la orientación de la forma (mismo giro
  que el patrón de referencia → `0`, giro contrario → `1`); SI la orientación no es determinable,
  ENTONCES DEBERÁ asignar `0` y registrar `gtfs.direction_ambiguous`.
  *Verificación:* unit (formas sintéticas horaria, antihoraria y degenerada). *Nota:* el feed de
  EMT no contiene líneas circulares en un único viaje (ver Contexto); esta rama queda para feeds
  futuros y no tiene caso de integración.
- **gtfs_import.AC-26** — CUANDO se ejecuta `avisabus gtfs info --directions`, LA CLI DEBERÁ
  listar por línea y sentido: origen del sentido, primera y última parada del patrón principal,
  headsigns con su número de viajes y número de patrones.
  *Verificación:* integration
- **gtfs_import.AC-27** — CUANDO se piden los headsigns de una línea en una parada, EL
  REPOSITORIO DEBERÁ devolver cada combinación (sentido, headsign) de los viajes de esa línea que
  paran en ella, con su número de viajes.
  *Verificación:* integration

- **gtfs_import.AC-28** — EL SISTEMA DEBERÁ crear solo las líneas comerciales con al menos un
  viaje e ignorar los `route_id` sin viajes; el resumen de `gtfs import` DEBERÁ indicar cuántos
  `route_id` se han ignorado por no tener viajes.
  *Verificación:* integration (copia de `gtfs_mini` con un `route_id` añadido sin viajes)
- **gtfs_import.AC-29** — EL SISTEMA DEBERÁ guardar, para cada línea y sentido, **todas** sus
  formas con su número de viajes, y EL REPOSITORIO DEBERÁ devolverlas con
  `shapes_for_direction(line, direction_id)` ordenadas por número de viajes descendente (empate:
  `shape_id` menor).
  *Verificación:* integration (98 y C2 en gtfs_mini devuelven dos formas por sentido)

### Consultas (`NetworkRepository`)

- **gtfs_import.AC-12** — CUANDO se pide una parada existente, EL REPOSITORIO DEBERÁ devolver
  su `stop_id`, nombre, latitud y longitud; SI no existe, ENTONCES DEBERÁ devolver `None`.
  *Verificación:* integration
- **gtfs_import.AC-13** — CUANDO se piden las líneas de una parada, EL REPOSITORIO DEBERÁ
  devolver los pares (línea, sentido, headsign, color, color de texto) ordenados por línea en
  orden natural (numéricas ascendentes, después alfanuméricas).
  *Verificación:* integration
- **gtfs_import.AC-14** — CUANDO se piden los servicios activos de una fecha, EL REPOSITORIO
  DEBERÁ incluir los servicios de `calendar` cuyo día de la semana esté activo y cuyo rango
  contenga la fecha, añadir los de `calendar_dates` con `exception_type = 1` y quitar los de
  `exception_type = 2`.
  *Verificación:* unit (tabla de casos) + integration
- **gtfs_import.AC-15** — CUANDO se piden los horarios programados de una parada para un
  instante, EL REPOSITORIO DEBERÁ devolver las pasadas de servicios activos en la ventana pedida,
  incluidas las de viajes del día de servicio anterior con horas ≥ 24:00:00 que caen en esa
  ventana, ordenadas por hora.
  *Verificación:* integration (caso de madrugada)
- **gtfs_import.AC-16** — CUANDO se piden los horarios de un viaje, EL REPOSITORIO DEBERÁ
  devolverlos ordenados por `stop_sequence`, con `shape_dist_traveled` si existe.
  *Verificación:* integration
- **gtfs_import.AC-17** — CUANDO se pide la forma de una línea y sentido, EL REPOSITORIO DEBERÁ
  devolver los puntos de su forma representativa ordenados por `shape_pt_sequence`.
  *Verificación:* integration

### Vigencia del feed

- **gtfs_import.AC-18** — CUANDO se ejecuta `avisabus gtfs info`, LA CLI DEBERÁ mostrar la
  versión activa, la fecha de importación, el rango de vigencia (`feed_start_date`–`feed_end_date`)
  y los recuentos; SI no hay ningún feed importado, ENTONCES DEBERÁ indicarlo y terminar con
  código 1.
  *Verificación:* integration
- **gtfs_import.AC-19** — SI faltan 7 días o menos para `feed_end_date`, ENTONCES `gtfs import`
  y `gtfs info` DEBERÁN mostrar una advertencia y EL SISTEMA DEBERÁ registrar el evento de log
  `gtfs.feed_expiring` con los días restantes; SI la fecha ya ha pasado, ENTONCES DEBERÁN mostrar
  y registrar `gtfs.feed_expired`.
  *Verificación:* unit (FakeClock) + integration
- **gtfs_import.AC-20** — SI no existe `feed_info.txt`, ENTONCES EL SISTEMA DEBERÁ usar como
  vigencia la mínima fecha de inicio y la máxima de fin de `calendar` / `calendar_dates`.
  *Verificación:* unit

### Fixture y rendimiento

- **gtfs_import.AC-21** — EL SISTEMA DEBERÁ incluir `backend/tests/fixtures/gtfs_mini/` generada
  desde el feed real con las líneas 70, 93, 98 y C2 (la 98 sirve la parada 2070 y aporta una
  variante corta en el mismo sentido) mediante `backend/scripts/make_gtfs_mini.py`, y
  su `README.md` DEBERÁ indicar el feed de origen, la fecha de referencia y el comando usado.
  *Verificación:* revisión + los tests de integración la usan
- **gtfs_import.AC-22** — CUANDO se importa el feed real completo en el equipo de desarrollo,
  LA IMPORTACIÓN DEBERÁ completarse en menos de 2 minutos con un uso de memoria inferior a 500 MB.
  *Verificación:* manual (test marcado `slow`, tiempo y memoria anotados en `progress/impl_gtfs_import.md`)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-01 Importar el feed | AC-01, AC-02, AC-03, AC-04, AC-07, AC-08, AC-12, AC-15, AC-16, AC-17, AC-22 |
| RF-02 Reimportar sin interrupción y avisar de caducidad | AC-05, AC-06, AC-18, AC-19, AC-20 |
| RF-03 Líneas comerciales | AC-09, AC-10, AC-11, AC-13 |
| RF-03 / R-02 Sentidos (derivados) y headsigns | AC-23, AC-24, AC-25, AC-26, AC-27, AC-29 |
| RF-03 Solo líneas con viajes | AC-28 |
| RF-04 Servicios activos por fecha | AC-14, AC-15 |
| RF-32 Nombres tal como vienen en el GTFS | AC-07 |
| RNF-10 Testabilidad | AC-21 |

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-10-31 | Versión inicial aprobada (PR #2) | — |
| 1.1 | 2026-10-31 | Circulares de EMT tratadas como lineales (medios bucles); AC-24 y AC-25 con verificaciones ajustadas; AC-07 incluye `trip_headsign`; AC-28 (solo líneas con viajes); AC-29 (todas las formas por sentido); línea 98 en `gtfs_mini`. | CP-3 tras la exploración E-01 (`progress/explore_gtfs_feed.md`). Aprobada por la persona. |
| 1.2 | 2026-10-31 | Design §8 y T-04: `gtfs_mini` con `--date 2026-11-09` (lunes + domingo) y límite < 2,5 MB. Design §3: `gtfs import` sin la opción `--yes` (no tenía comportamiento definido). | Bloqueo B-01 del implementer (T-04): con 2026-11-04 faltaba el `route_id` 1055 de la 98, necesario para AC-24 y AC-29. Aprobada por la persona. |
