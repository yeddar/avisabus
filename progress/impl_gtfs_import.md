# Implementación: gtfs_import
Spec: specs/gtfs_import/ (v1.2, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-10-31

> Reanudada en T-04 tras resolverse B-01 (spec v1.2, PR #9). T-01…T-03b se hicieron antes del
> bloqueo y no se repiten (sus commits cambiaron de hash al rebasar la rama sobre `develop`).

## Tareas
- [x] T-01 Modelos de red, `parse_gtfs_time` y normalización de nombres (AC-07, AC-08) (commit e91ae4b)
- [x] T-02 Servicios activos por fecha (AC-14) (commit 726db8d)
- [x] T-03 Estado de vigencia y vigencia sin `feed_info` (AC-19, AC-20) (commit e871426)
- [x] T-03b `derive_directions` con patrones sintéticos (AC-24, AC-25) (commit 1b6c950)
- [x] T-04 Script `make_gtfs_mini.py` y fixture `gtfs_mini` (AC-21) (commit 6dc19f9)
- [x] T-05 Lector `CsvGtfsFeedReader` (AC-02, AC-03, AC-04, AC-07) (commit c48700c)
- [x] T-06 Base de datos: motor, PRAGMAs, tablas y `create_all` (commit 243d640)
- [x] T-07 `SqliteGtfsFeedWriter` (AC-05, AC-06, AC-09, AC-10, AC-11, AC-23, AC-24, AC-28, AC-29)
      (commit a624a4b)
- [x] T-08 Caso de uso `ImportGtfsFeed` (AC-01, AC-05) (commit a7529f1)
- [x] T-09 `SqliteNetworkRepository` (AC-12–AC-17, AC-27, AC-29) (commit 608f478)
- [x] T-10 CLI `gtfs import` / `gtfs info [--directions]` (AC-01–AC-04, AC-18, AC-19, AC-26, AC-28)
      (commit e22227c)
- [x] T-11 Importación del feed real: tiempo, memoria y salida de `--directions` (AC-22, AC-26)
      (commit 9c6802c; resultados abajo)
- [x] T-12 `.env.example` y verificación completa (commit de este fichero; ver "Verificación")

## Decisiones locales
- **Normalización de nombres (AC-07).** Está en `domain/services/gtfs_text.py` (`clean_name`) y su
  test en `tests/unit/test_gtfs_text.py`. tasks.md T-01 solo lista `gtfs_time.py`; separarlo no
  cambia ninguna interfaz del design.
- **`feed_validity_status(feed, today, warning_days=7)`.** `warning_days` es un parámetro para
  poder pasar `AVISABUS_GTFS_EXPIRY_WARNING_DAYS` (design §7). `feed_end_date` se considera el
  último día válido (inclusive): ese día se devuelve `Expiring(0)` y al día siguiente
  `Expired(1)`.
- **`feed_validity_range`.** Si `feed_info` trae solo una de las dos fechas, la que falta se
  completa con `calendar` / `calendar_dates`. Si no hay ninguna fecha, se lanza
  `MissingValidityRangeError`.
- **`derive_directions(patterns, on_ambiguous=None)`.** La firma del design se mantiene y se añade
  un callback opcional. Así el dominio sigue siendo puro y el adaptador puede registrar
  `gtfs.direction_ambiguous` (AC-25). En una línea circular, si el área del patrón de referencia
  es despreciable, la orientación de ningún patrón es determinable: todos reciben `0` y se
  informan como ambiguos.

- **Errores de aplicación** (`GtfsValidationError`, `GtfsDataError`, base `GtfsImportError`) en
  `application/errors.py`, como indica design §6 ("Excepción (application)").
  `GtfsValidationError` lleva además un `reason` opcional para "ruta inexistente" y "ZIP corrupto".
- **Contrato de los puertos del importador** (`domain/ports/gtfs_import.py`). El design solo fija
  sus nombres y el flujo de §5. El lector devuelve filas crudas (`GtfsRow`: nº de línea + valores
  de texto). La aplicación (`application/gtfs_rows.py`) las convierte en registros tipados
  (`RouteRecord`, `StopRecord`, `TripRecord`, `StopTimeRecord`, `ShapePointRecord`, más
  `ServiceCalendar` y `CalendarException`, que ya existían), con el recorte de AC-07 y los
  segundos de AC-08. El escritor tiene `begin_version`, `insert_batch`, `build_derived`,
  `activate(feed, timezone)`, `purge_inactive` y `discard`.
- **`FeedInfoSource`** (puerto local en `domain/ports/gtfs_import.py`, implementado por
  `SqliteNetworkRepository`): `direction_report()` y `active_timezone()`. Sirve los datos de
  `gtfs info --directions` (AC-26: origen del sentido, extremos del patrón principal, headsigns y
  patrones), que no expone `NetworkRepository`, y la zona horaria del feed para calcular "hoy"
  igual que en la importación. **`NetworkRepository` queda exactamente como en design §3.**
- **Casos de uso `async`** (`ImportGtfsFeed.execute`, `GetFeedInfo.execute`), según
  `docs/conventions.md` §3. La CLI los ejecuta con `asyncio.run`.
- **"Hoy" para la vigencia:** `clock.now()` convertido a la `agency_timezone` del feed.
  `feed_end_date` incluido (ver arriba).
- **Validación de valores** (design §6, "Valor inválido"): `GtfsDataError` con fichero y línea
  si hay horas no válidas o vacías, números o fechas `YYYYMMDD` no válidos, días de `calendar`
  distintos de 0/1, `exception_type` distinto de 1/2, `shape_id`/IDs vacíos, `agency_timezone`
  desconocida, `route_id` de un viaje que no está en `routes.txt`, o `direction_id` distinto de
  0/1 cuando la columna existe (también vacío). Otros errores (p. ej. IDs duplicados →
  `IntegrityError`) también descartan la versión. La CLI muestra solo su **tipo**, nunca el
  mensaje (`docs/conventions.md` §3), y termina con código 2.
- **Desempates sin especificar:** atributos de la línea (AC-09) del `route_id` con más viajes y,
  si empatan, el `route_id` menor. Headsign y forma de `line_direction` (AC-10): orden
  alfabético, como dice design §5.4.
- **Viaje sin `stop_times` en la derivación:** se usan los extremos de su forma. Si tampoco hay
  forma, los extremos son (0, 0) (no ocurre en el feed de EMT). Los route_id sin viajes no entran
  en `line_route` (`Line.route_ids` solo incluye los que tienen viajes, AC-28).
- **Orden natural de líneas (AC-13):** `domain/services/line_order.py`. Las alfanuméricas
  comparan sus partes numéricas como números (`C2` < `C10`).
- **`scheduled_stop_times`:** los segundos de cada día de servicio se cuentan desde su inicio
  (mediodía − 12 h local, en UTC), como define design §3. Fuera de los días de cambio de hora
  coincide con `[s + 86400, s + 86400 + window]` para `D − 1`. En los días de cambio de hora, la
  definición GTFS es la correcta. Ventana cerrada `[at, at + window]`, orden por instante
  absoluto. `at` sin zona → `ValueError`.
- **`list_stop_ids`:** orden por `stop_id` (cadena). El design no fija ningún orden.
- **Esquema:** `feed_version.imported_at` se guarda como texto ISO 8601 en UTC.
  `feed_version.id` es `AUTOINCREMENT`, para que las versiones no se reutilicen tras la purga.
  `gtfs_trip.direction_id` y `headsign` admiten NULL hasta que `build_derived` los rellena.
  Fechas como `Date`. Sin claves foráneas (el design no las define). No hay índices adicionales.
- **Logs:** `gtfs.feed_expiring` / `gtfs.feed_expired` se registran en la CLI (adaptador de
  entrada), junto al aviso en pantalla, en `import` e `info`. `gtfs.direction_ambiguous` se
  registra en el escritor con `line` y `shape_id`. `gtfs.import_failed` registra solo el tipo de
  la excepción.
- **CLI:** `_container()` construye `Settings()` (H-09), configura los logs y llama a
  `build_cli_container(settings, clock)`, que los tests sustituyen (design §8). Los errores van
  a stderr. Mensajes según design §3 y §6. Se añade la línea `route_id sin viajes ignorados: N`
  también en `info`.
- **Settings nuevas** (`AVISABUS_GTFS_EXPIRY_WARNING_DAYS` ≥ 0 y `AVISABUS_GTFS_BATCH_SIZE` > 0)
  añadidas en T-10, junto con su documentación en `.env.example`. Se documentaron en T-10 y no
  en T-12 porque el test de `project_scaffold` exige que cada setting esté documentada; así
  ningún commit queda en rojo.
- **Dependencia nueva:** `sqlalchemy>=2` (2.1.6), en T-06.
- **Fixture:** `tests/support/gtfs.py` copia y modifica `gtfs_mini` en `tmp_path` para los casos
  de AC-03, AC-04, AC-23 y AC-28. `tests/integration/test_gtfs_mini_fixture.py` comprueba
  automáticamente la composición, el tamaño y el README de la fixture (AC-21).

## Bloqueos

### B-01 (CP-3) — RESUELTO en spec v1.2 (PR #9): `--date 2026-11-09` y < 2,5 MB

Resuelto con la propuesta 1. La fixture generada en T-04 (2,15 MB) tiene en la 98 las formas
`1054_487_2229` (71), `1055_487_2271` (35), `1054_2229_487` (69) y `1055_2271_487` (32).

<details><summary>Descripción original del bloqueo</summary>

#### La fixture definida en design §8 (v1.1) no contenía los datos que piden AC-24 y AC-29

**Qué dice la spec**
- design §8: `make_gtfs_mini.py ... --lines 70,93,98,C2 --date 2026-11-04`, que conserva los
  viajes cuyos servicios están activos en `--date` o en `--date - 1 día` (miércoles 04-11 y
  martes 03-11). Objetivo de tamaño: < 2 MB (T-04 lo verifica con `du -sh`).
- AC-24 (integración): "la variante corta `1054_487_2229` de la 98 queda en el mismo sentido que
  `1055_487_2271`".
- AC-29 (integración): "98 y C2 en gtfs_mini devuelven dos formas por sentido".

**Qué dicen los datos.** En la línea 98, el `route_id` 1054 es "Només dies laborables" (servicio
`38_1054_561`, de lunes a viernes) y el 1055 es "Només dissabtes i festius" (`38_1055_603` los
sábados y `38_1055_604` los domingos). Generando la fixture exactamente como dice §8, la 98
queda así:

```
71 1054_487_2229   69 1054_2229_487       (ningún viaje de 1055)
```

Por tanto:
- `1055_487_2271` no existe en la fixture, así que AC-24 no se puede verificar como está escrito.
- La 98 tiene una sola forma por sentido, así que AC-29 no se puede verificar para la 98. C2 sí
  da dos formas por sentido.
- Además, la "variante corta" `1054_487_2229` pasa a ser el patrón de referencia de la 98. Ya
  no hay ninguna variante en el mismo sentido que comprobar.

La exploración E-01 estimó el tamaño con esas fechas (≈ 1,40 MB) sin advertir que el 1055 no
circula de lunes a viernes.

**Mediciones con otras fechas** (mismo script; salida en el scratchpad, no versionada):

| `--date` (y día anterior) | Tamaño | Formas de la 98 (viajes) | C2 con 651 y 996 |
|---|---|---|---|
| 2026-11-04 mié (+ mar), **design actual** | 1,5 MB | 1054_487_2229 (71), 1054_2229_487 (69) | sí |
| 2026-11-09 lun (+ dom 08-11) | **2,15 MB** | 1054_487_2229 (71), 1055_487_2271 (35), 1054_2229_487 (69), 1055_2271_487 (32) | sí |
| 2026-11-02 lun (+ dom 01-11) | 2,15 MB | igual que 09-11 | sí |
| 2026-11-07 sáb (+ vie) | 2,27 MB | 1054 (71/69) + 1055 (39/40) | sí |
| 2026-11-08 dom (+ sáb) | 1,47 MB | solo 1055 (74/72) | **no** (C2 no circula) |

**Propuestas (elige la persona):**
1. **(Recomendada, la más simple) `--date 2026-11-09`** (lunes; el día anterior es domingo) y
   objetivo de tamaño **< 2,5 MB** en design §8 y en la verificación de T-04. Con eso:
   - La 98 queda con dos formas por sentido: sentido 0 = `1054_487_2229` (referencia, 71 viajes)
     y `1055_487_2271` (35); sentido 1 = `1054_2229_487` y `1055_2271_487`. AC-24 y AC-29 se
     cumplen tal como están escritos.
   - El caso de madrugada (AC-15) sigue cubierto: los viajes del domingo con horas ≥ 24:00 caen
     en la madrugada del lunes.
   - Matiz: en esa fixture la "variante corta" es el patrón de referencia y la "larga"
     (`1055_487_2271`) es la variante. La aserción de AC-24 ("mismo sentido") no cambia.
2. Mantener `--date 2026-11-04` y < 2 MB, pero añadir al generador una opción para conservar
   también los viajes de otra fecha en una línea concreta (p. ej. `--extra 98:2026-11-08`).
   Estimación: ≈ 1,6 MB. Requiere describir esa opción en design §8.
3. Mantener la fixture del design y cambiar las verificaciones de AC-24 y AC-29: la 98 deja de
   aportar varias formas por sentido. Pierde el caso real de "variante corta en el mismo sentido"
   que motivó añadir la 98 en la v1.1.

</details>

### Observación `gtfs import --yes` — RESUELTA en spec v1.2 (la opción se elimina)

<details><summary>Descripción original</summary>

#### `gtfs import --yes`
Design §3 define `avisabus gtfs import PATH [--yes]`, pero la spec no describe ninguna
confirmación interactiva ni qué hace `--yes`. Propuesta: aclararlo en design §3. Por ejemplo:
- "sin `--yes`, si ya hay una versión activa, se pide confirmación; si se rechaza, exit 1"; o
- "`--yes` se acepta por compatibilidad y no tiene efecto".

Si no se aclara, la implementación aceptará el flag sin efecto y lo anotará aquí.

</details>

### Bloqueos nuevos
Ninguno.

### Observaciones para la persona y el reviewer (no bloqueantes)
- **Ventana de `scheduled_stop_times` que cruza la medianoche.** Design §3 consulta solo los
  días `D` y `D − 1`. Una ventana que empiece poco antes de las 24:00 no incluye las primeras
  salidas del día de servicio `D + 1` (horas 00:xx). Se implementa tal como está escrito. Si
  `stop_arrivals_api` usa ventanas largas cerca de la medianoche, quizá convenga añadir `D + 1`
  en esa spec.
- **Tamaño de la BD tras reimportar:** 68 MB con una versión y 139 MB tras la segunda
  importación. SQLite reutiliza las páginas libres, pero no las devuelve sin `VACUUM`.
  No afecta a ningún AC.

## Verificación

### T-11 — Importación del feed real (AC-22)

Feed `data/gtfs/emt/` (feed_version `23-10-2026`). MacBook de desarrollo (darwin, Python 3.12.16,
SQLite 3.53.1), BD en un directorio temporal.

| Medición | Tiempo | Memoria | Límite AC-22 |
|---|---|---|---|
| CLI real, BD vacía: `/usr/bin/time -l .venv/bin/avisabus gtfs import ../data/gtfs/emt` | **4,6 s** | **75 MB** (RSS máx.) | < 120 s, < 500 MB |
| CLI real vía `uv run`, 1.ª importación | 4,7 s | 75 MB | |
| CLI real vía `uv run`, 2.ª importación (purga de la anterior) | 5,1 s | 87 MB | |
| Test `slow` en proceso (`test_gtfs_real_feed.py`, RSS de todo pytest) | 4,4 s | 96 MB | |

`cd backend && uv run pytest -m slow tests/integration/test_gtfs_real_feed.py` → `2 passed`.

Salida de la importación:
```
Feed importado (versión 1, feed_version 23-10-2026)
Vigencia: 2026-10-16 → 2026-11-22
Líneas: 42 · Paradas: 1 117 · Viajes: 20 598 · Horarios de parada: 508 134
route_id sin viajes ignorados: 3
```

### T-11 — `avisabus gtfs info --directions` con el feed real (AC-26) — **para validar (CP-6)**

Resumen:
- 42 líneas × 2 sentidos = 84 sentidos, todos con `origen: derived`. Ninguna línea tiene 1 o 3
  sentidos. No se ha registrado ningún `gtfs.direction_ambiguous`, porque ninguna línea es
  circular según la regla de 500 m.
- Coincide **línea por línea** con la tabla de la exploración E-01
  (`progress/explore_gtfs_feed.md` §5): patrones, viajes, extremos y headsigns.
- Sentidos con varios patrones:
  - 62 y 73: dos `route_id` con los mismos extremos.
  - 98: la variante corta `1054_487_2229` (71) va en el mismo sentido que `1055_487_2271` (74).
    En el sentido 1, los dos patrones tienen el mismo headsign.
  - C2 y C3: cada sentido mezcla medios bucles de los dos `route_id`, con dos headsigns. Es la
    opción A aprobada en CP-3.
- C1 tiene 2 sentidos (medios bucles). La línea 59 empata (135/135) y se resuelve por
  `shape_id` menor: el sentido 0 es `1070_2285_2437`. El headsign `Terramelar` (62/1) aparece
  ya recortado.
- `route_id` ignorados por no tener viajes: 3 (`1033` de la 23, `982` de la 30 y `1068` de la 24).

Salida completa:
```
Versión activa: 2 (feed_version 23-10-2026)
Importado: 2026-10-31 20:37 UTC
Vigencia: 2026-10-16 → 2026-11-22
Líneas: 42 · Paradas: 1 117 · Viajes: 20 598 · Horarios de parada: 508 134
route_id sin viajes ignorados: 3

Línea 4 · sentido 0 · origen: derived · viajes: 340 · patrones: 1
  Patrón principal 1017_1585_2403: 1585 Natzaret → 2403 Plaça de l'Ajuntament - Ateneu
  Headsigns: Plaça de l'Ajuntament - Ateneu (340)
  Patrones: 1017_1585_2403 (340)
Línea 4 · sentido 1 · origen: derived · viajes: 333 · patrones: 1
  Patrón principal 1017_2403_1585: 2403 Plaça de l'Ajuntament - Ateneu → 1585 Natzaret
  Headsigns: Natzaret (333)
  Patrones: 1017_2403_1585 (333)
Línea 6 · sentido 0 · origen: derived · viajes: 208 · patrones: 1
  Patrón principal 1057_2085_2158: 2085 Torrefiel → 2158 Bulevard Sud (via de servici) - Hospital La Fe
  Headsigns: Bulevard Sud (via de servici) - Hospital La Fe (208)
  Patrones: 1057_2085_2158 (208)
Línea 6 · sentido 1 · origen: derived · viajes: 206 · patrones: 1
  Patrón principal 1057_2158_2085: 2158 Bulevard Sud (via de servici) - Hospital La Fe → 2085 Torrefiel
  Headsigns: Torrefiel (206)
  Patrones: 1057_2158_2085 (206)
Línea 7 · sentido 0 · origen: derived · viajes: 269 · patrones: 1
  Patrón principal 1061_1940_2288: 1940 Fonteta de Sant Lluís → 2288 Mercat Central - Beata
  Headsigns: Mercat Central - Beata (269)
  Patrones: 1061_1940_2288 (269)
Línea 7 · sentido 1 · origen: derived · viajes: 268 · patrones: 1
  Patrón principal 1061_2288_1940: 2288 Mercat Central - Beata → 1940 Fonteta de Sant Lluís
  Headsigns: Fonteta de Sant Lluís (268)
  Patrones: 1061_2288_1940 (268)
Línea 8 · sentido 0 · origen: derived · viajes: 350 · patrones: 1
  Patrón principal 1066_2410_2255: 2410 Gonzalo Tejero Langarita - Vicente Chuliá Campos → 2255 Porta de la Mar - Glorieta
  Headsigns: Porta de la Mar - Glorieta (350)
  Patrones: 1066_2410_2255 (350)
Línea 8 · sentido 1 · origen: derived · viajes: 347 · patrones: 1
  Patrón principal 1066_2255_2410: 2255 Porta de la Mar - Glorieta → 2410 Gonzalo Tejero Langarita - Vicente Chuliá Campos
  Headsigns: Gonzalo Tejero Langarita - Vicente Chuliá Campos (347)
  Patrones: 1066_2255_2410 (347)
Línea 9 · sentido 0 · origen: derived · viajes: 326 · patrones: 1
  Patrón principal 922_585_2312: 585 Forn d'Alcedo → 2312 Sant Pau - Estació del Nord
  Headsigns: Sant Pau - Estació del Nord (326)
  Patrones: 922_585_2312 (326)
Línea 9 · sentido 1 · origen: derived · viajes: 322 · patrones: 1
  Patrón principal 922_2312_585: 2312 Sant Pau - Estació del Nord → 585 Forn d'Alcedo
  Headsigns: Forn d'Alcedo (322)
  Patrones: 922_2312_585 (322)
Línea 10 · sentido 0 · origen: derived · viajes: 290 · patrones: 1
  Patrón principal 923_1440_1240: 1440 Sant Marcel·lí → 1240 Benimaclet - Lliri Blau
  Headsigns: Benimaclet - Lliri Blau (290)
  Patrones: 923_1440_1240 (290)
Línea 10 · sentido 1 · origen: derived · viajes: 274 · patrones: 1
  Patrón principal 923_1240_1440: 1240 Benimaclet - Lliri Blau → 1440 Sant Marcel·lí
  Headsigns: Sant Marcel·lí (274)
  Patrones: 923_1240_1440 (274)
Línea 11 · sentido 0 · origen: derived · viajes: 277 · patrones: 1
  Patrón principal 1056_1229_2380: 1229 Els Orriols - Metro Sant Miquel dels Reis → 2380 Patraix
  Headsigns: Patraix (277)
  Patrones: 1056_1229_2380 (277)
Línea 11 · sentido 1 · origen: derived · viajes: 270 · patrones: 1
  Patrón principal 1056_2380_1229: 2380 Patraix → 1229 Els Orriols - Metro Sant Miquel dels Reis
  Headsigns: Els Orriols - Metro Sant Miquel dels Reis (270)
  Patrones: 1056_2380_1229 (270)
Línea 12 · sentido 0 · origen: derived · viajes: 119 · patrones: 1
  Patrón principal 827_1326_764: 1326 Ciutat de l'Artista Faller → 764 Plaça d'Amèrica - Pont d'Aragó
  Headsigns: Plaça d'Amèrica - Pont d'Aragó (119)
  Patrones: 827_1326_764 (119)
Línea 12 · sentido 1 · origen: derived · viajes: 114 · patrones: 1
  Patrón principal 827_764_1326: 764 Plaça d'Amèrica - Pont d'Aragó → 1326 Ciutat de l'Artista Faller
  Headsigns: Ciutat de l'Artista Faller (114)
  Patrones: 827_764_1326 (114)
Línea 13 · sentido 0 · origen: derived · viajes: 95 · patrones: 1
  Patrón principal 1021_1940_2250: 1940 Fonteta de Sant Lluís → 2250 Porta de la Mar - Navarro Reverter (parell)
  Headsigns: Porta de la Mar - Navarro Reverter (parell) (95)
  Patrones: 1021_1940_2250 (95)
Línea 13 · sentido 1 · origen: derived · viajes: 93 · patrones: 1
  Patrón principal 1021_2250_1940: 2250 Porta de la Mar - Navarro Reverter (parell) → 1940 Fonteta de Sant Lluís
  Headsigns: Fonteta de Sant Lluís (93)
  Patrones: 1021_2250_1940 (93)
Línea 14 · sentido 0 · origen: derived · viajes: 297 · patrones: 1
  Patrón principal 983_2376_2279: 2376 Castellar - l'Oliveral - Doctor Ruiz i Comes → 2279 Marqués de Sotelo - Plaça de l'Ajuntament
  Headsigns: Marqués de Sotelo - Plaça de l'Ajuntament (297)
  Patrones: 983_2376_2279 (297)
Línea 14 · sentido 1 · origen: derived · viajes: 292 · patrones: 1
  Patrón principal 983_2279_2376: 2279 Marqués de Sotelo - Plaça de l'Ajuntament → 2376 Castellar - l'Oliveral - Doctor Ruiz i Comes
  Headsigns: Castellar - l'Oliveral - Doctor Ruiz i Comes (292)
  Patrones: 983_2279_2376 (292)
Línea 16 · sentido 0 · origen: derived · viajes: 293 · patrones: 1
  Patrón principal 1022_2391_2014: 2391 Vinalesa - Plaça d'Ausiàs March → 2014 Poeta Querol - Teatre Principal
  Headsigns: Poeta Querol - Teatre Principal (293)
  Patrones: 1022_2391_2014 (293)
Línea 16 · sentido 1 · origen: derived · viajes: 290 · patrones: 1
  Patrón principal 1022_2014_2391: 2014 Poeta Querol - Teatre Principal → 2391 Vinalesa - Plaça d'Ausiàs March
  Headsigns: Vinalesa - Plaça d'Ausiàs March (290)
  Patrones: 1022_2014_2391 (290)
Línea 18 · sentido 0 · origen: derived · viajes: 113 · patrones: 1
  Patrón principal 1045_2320_1949: 2320 Hospital Doctor Peset - Primer de Maig → 1949 Universitats - Facultat de Magisteri
  Headsigns: Universitats - Facultat de Magisteri (113)
  Patrones: 1045_2320_1949 (113)
Línea 18 · sentido 1 · origen: derived · viajes: 111 · patrones: 1
  Patrón principal 1045_1949_2320: 1949 Universitats - Facultat de Magisteri → 2320 Hospital Doctor Peset - Primer de Maig
  Headsigns: Hospital Doctor Peset - Primer de Maig (111)
  Patrones: 1045_1949_2320 (111)
Línea 19 · sentido 0 · origen: derived · viajes: 352 · patrones: 1
  Patrón principal 930_18_2314: 18 La Malva-rosa - Cavite → 2314 Periodista Azzati - Plaça de l'Ajuntament
  Headsigns: Periodista Azzati - Plaça de l'Ajuntament (352)
  Patrones: 930_18_2314 (352)
Línea 19 · sentido 1 · origen: derived · viajes: 343 · patrones: 1
  Patrón principal 930_2314_18: 2314 Periodista Azzati - Plaça de l'Ajuntament → 18 La Malva-rosa - Cavite
  Headsigns: La Malva-rosa - Cavite (343)
  Patrones: 930_2314_18 (343)
Línea 24 · sentido 0 · origen: derived · viajes: 62 · patrones: 1
  Patrón principal 1040_2172_2253: 2172 El Palmar → 2253 Porta de la Mar - General Palanca
  Headsigns: Porta de la Mar - General Palanca (62)
  Patrones: 1040_2172_2253 (62)
Línea 24 · sentido 1 · origen: derived · viajes: 62 · patrones: 1
  Patrón principal 1040_2253_2172: 2253 Porta de la Mar - General Palanca → 2172 El Palmar
  Headsigns: El Palmar (62)
  Patrones: 1040_2253_2172 (62)
Línea 25 · sentido 0 · origen: derived · viajes: 158 · patrones: 1
  Patrón principal 1026_2186_2253: 2186 El Perelló → 2253 Porta de la Mar - General Palanca
  Headsigns: Porta de la Mar - General Palanca (158)
  Patrones: 1026_2186_2253 (158)
Línea 25 · sentido 1 · origen: derived · viajes: 158 · patrones: 1
  Patrón principal 1026_2253_2186: 2253 Porta de la Mar - General Palanca → 2186 El Perelló
  Headsigns: El Perelló (158)
  Patrones: 1026_2253_2186 (158)
Línea 26 · sentido 0 · origen: derived · viajes: 49 · patrones: 1
  Patrón principal 1027_2105_2014: 2105 Moncada - Alfara → 2014 Poeta Querol - Teatre Principal
  Headsigns: Poeta Querol - Teatre Principal (49)
  Patrones: 1027_2105_2014 (49)
Línea 26 · sentido 1 · origen: derived · viajes: 46 · patrones: 1
  Patrón principal 1027_2014_2105: 2014 Poeta Querol - Teatre Principal → 2105 Moncada - Alfara
  Headsigns: Moncada - Alfara (46)
  Patrones: 1027_2014_2105 (46)
Línea 27 · sentido 0 · origen: derived · viajes: 147 · patrones: 1
  Patrón principal 1060_586_2290: 586 La Torre → 2290 Avinguda de l'Oest - Hospital
  Headsigns: Avinguda de l'Oest - Hospital (147)
  Patrones: 1060_586_2290 (147)
Línea 27 · sentido 1 · origen: derived · viajes: 144 · patrones: 1
  Patrón principal 1060_2290_586: 2290 Avinguda de l'Oest - Hospital → 586 La Torre
  Headsigns: La Torre (144)
  Patrones: 1060_2290_586 (144)
Línea 28 · sentido 0 · origen: derived · viajes: 382 · patrones: 1
  Patrón principal 1034_1326_2277: 1326 Ciutat de l'Artista Faller → 2277 Xàtiva - Institut Lluís Vives
  Headsigns: Xàtiva - Institut Lluís Vives (382)
  Patrones: 1034_1326_2277 (382)
Línea 28 · sentido 1 · origen: derived · viajes: 380 · patrones: 1
  Patrón principal 1034_2277_1326: 2277 Xàtiva - Institut Lluís Vives → 1326 Ciutat de l'Artista Faller
  Headsigns: Ciutat de l'Artista Faller (380)
  Patrones: 1034_2277_1326 (380)
Línea 31 · sentido 0 · origen: derived · viajes: 208 · patrones: 1
  Patrón principal 1053_2248_2284: 2248 La Patacona - Institut → 2284 Estació Joaquín Sorolla
  Headsigns: Estació Joaquín Sorolla (208)
  Patrones: 1053_2248_2284 (208)
Línea 31 · sentido 1 · origen: derived · viajes: 202 · patrones: 1
  Patrón principal 1053_2284_2248: 2284 Estació Joaquín Sorolla → 2248 La Patacona - Institut
  Headsigns: La Patacona - Institut (202)
  Patrones: 1053_2284_2248 (202)
Línea 32 · sentido 0 · origen: derived · viajes: 288 · patrones: 1
  Patrón principal 1029_1162_2403: 1162 Passeig Marítim - Mendizábal → 2403 Plaça de l'Ajuntament - Ateneu
  Headsigns: Plaça de l'Ajuntament - Ateneu (288)
  Patrones: 1029_1162_2403 (288)
Línea 32 · sentido 1 · origen: derived · viajes: 278 · patrones: 1
  Patrón principal 1029_2403_1162: 2403 Plaça de l'Ajuntament - Ateneu → 1162 Passeig Marítim - Mendizábal
  Headsigns: Passeig Marítim - Mendizábal (278)
  Patrones: 1029_2403_1162 (278)
Línea 35 · sentido 0 · origen: derived · viajes: 318 · patrones: 1
  Patrón principal 935_1950_2279: 1950 Pere II el Cerimoniós - Luis Merelo y Mas → 2279 Marqués de Sotelo - Plaça de l'Ajuntament
  Headsigns: Marqués de Sotelo - Plaça de l'Ajuntament (318)
  Patrones: 935_1950_2279 (318)
Línea 35 · sentido 1 · origen: derived · viajes: 312 · patrones: 1
  Patrón principal 935_2279_1950: 2279 Marqués de Sotelo - Plaça de l'Ajuntament → 1950 Pere II el Cerimoniós - Luis Merelo y Mas
  Headsigns: Pere II el Cerimoniós - Luis Merelo y Mas (312)
  Patrones: 935_2279_1950 (312)
Línea 40 · sentido 0 · origen: derived · viajes: 112 · patrones: 1
  Patrón principal 1030_1282_2278: 1282 Universitats - Facultat de Ciències Socials → 2278 Estació del Nord - Marqués de Sotelo
  Headsigns: Estació del Nord - Marqués de Sotelo (112)
  Patrones: 1030_1282_2278 (112)
Línea 40 · sentido 1 · origen: derived · viajes: 111 · patrones: 1
  Patrón principal 1030_2278_1282: 2278 Estació del Nord - Marqués de Sotelo → 1282 Universitats - Facultat de Ciències Socials
  Headsigns: Universitats - Facultat de Ciències Socials (111)
  Patrones: 1030_2278_1282 (111)
Línea 59 · sentido 0 · origen: derived · viajes: 135 · patrones: 1
  Patrón principal 1070_2285_2437: 2285 Estació del Nord - Sant Agustí → 2437 Ignacio Hernández Hervas - Ruíz
  Headsigns: Ignacio Hernández Hervas - Ruíz (135)
  Patrones: 1070_2285_2437 (135)
Línea 59 · sentido 1 · origen: derived · viajes: 135 · patrones: 1
  Patrón principal 1070_2437_2285: 2437 Ignacio Hernández Hervas - Ruíz → 2285 Estació del Nord - Sant Agustí
  Headsigns: Estació del Nord - Sant Agustí (135)
  Patrones: 1070_2437_2285 (135)
Línea 60 · sentido 0 · origen: derived · viajes: 327 · patrones: 1
  Patrón principal 966_2085_1520: 2085 Torrefiel → 1520 Sant Agustí
  Headsigns: Sant Agustí (327)
  Patrones: 966_2085_1520 (327)
Línea 60 · sentido 1 · origen: derived · viajes: 319 · patrones: 1
  Patrón principal 966_1520_2085: 1520 Sant Agustí → 2085 Torrefiel
  Headsigns: Torrefiel (319)
  Patrones: 966_1520_2085 (319)
Línea 62 · sentido 0 · origen: derived · viajes: 448 · patrones: 2
  Patrón principal 967_390_2289: 390 Terramelar → 2289 Avinguda de l'Oest - Roger de Flor
  Headsigns: Avinguda de l'Oest - Roger de Flor (448)
  Patrones: 967_390_2289 (283); 1077_390_2289 (165)
Línea 62 · sentido 1 · origen: derived · viajes: 441 · patrones: 2
  Patrón principal 967_2289_390: 2289 Avinguda de l'Oest - Roger de Flor → 390 Terramelar
  Headsigns: Terramelar (441)
  Patrones: 967_2289_390 (279); 1077_2289_390 (162)
Línea 63 · sentido 0 · origen: derived · viajes: 47 · patrones: 1
  Patrón principal 968_2359_1145: 2359 Bailén - Ermita → 1145 Campus de Burjassot
  Headsigns: Campus de Burjassot (47)
  Patrones: 968_2359_1145 (47)
Línea 63 · sentido 1 · origen: derived · viajes: 45 · patrones: 1
  Patrón principal 968_1145_2359: 1145 Campus de Burjassot → 2359 Bailén - Ermita
  Headsigns: Bailén - Ermita (45)
  Patrones: 968_1145_2359 (45)
Línea 64 · sentido 0 · origen: derived · viajes: 332 · patrones: 1
  Patrón principal 1076_1824_1946: 1824 Benicalap - Joan XXIII → 1946 Bulevard Sud (imparell) - Hospital La Fe
  Headsigns: Bulevard Sud (imparell) - Hospital La Fe (332)
  Patrones: 1076_1824_1946 (332)
Línea 64 · sentido 1 · origen: derived · viajes: 325 · patrones: 1
  Patrón principal 1076_1946_1824: 1946 Bulevard Sud (imparell) - Hospital La Fe → 1824 Benicalap - Joan XXIII
  Headsigns: Benicalap - Joan XXIII (325)
  Patrones: 1076_1946_1824 (325)
Línea 67 · sentido 0 · origen: derived · viajes: 215 · patrones: 1
  Patrón principal 995_1657_2309: 1657 Nou Campanar - Hospital Arnau de Vilanova → 2309 Bailén - Estació del Nord
  Headsigns: Bailén - Estació del Nord (215)
  Patrones: 995_1657_2309 (215)
Línea 67 · sentido 1 · origen: derived · viajes: 213 · patrones: 1
  Patrón principal 995_2309_1657: 2309 Bailén - Estació del Nord → 1657 Nou Campanar - Hospital Arnau de Vilanova
  Headsigns: Nou Campanar - Hospital Arnau de Vilanova (213)
  Patrones: 995_2309_1657 (213)
Línea 70 · sentido 0 · origen: derived · viajes: 303 · patrones: 1
  Patrón principal 1058_2030_500: 2030 Alboraia → 500 La Fontsanta
  Headsigns: La Fontsanta (303)
  Patrones: 1058_2030_500 (303)
Línea 70 · sentido 1 · origen: derived · viajes: 302 · patrones: 1
  Patrón principal 1058_500_2030: 500 La Fontsanta → 2030 Alboraia
  Headsigns: Alboraia (302)
  Patrones: 1058_500_2030 (302)
Línea 71 · sentido 0 · origen: derived · viajes: 206 · patrones: 1
  Patrón principal 1059_1366_1282: 1366 La Llum → 1282 Universitats - Facultat de Ciències Socials
  Headsigns: Universitats - Facultat de Ciències Socials (206)
  Patrones: 1059_1366_1282 (206)
Línea 71 · sentido 1 · origen: derived · viajes: 201 · patrones: 1
  Patrón principal 1059_1282_1366: 1282 Universitats - Facultat de Ciències Socials → 1366 La Llum
  Headsigns: La Llum (201)
  Patrones: 1059_1282_1366 (201)
Línea 72 · sentido 0 · origen: derived · viajes: 169 · patrones: 1
  Patrón principal 970_1936_2277: 1936 Sant Isidre → 2277 Xàtiva - Institut Lluís Vives
  Headsigns: Xàtiva - Institut Lluís Vives (169)
  Patrones: 970_1936_2277 (169)
Línea 72 · sentido 1 · origen: derived · viajes: 165 · patrones: 1
  Patrón principal 970_2277_1936: 2277 Xàtiva - Institut Lluís Vives → 1936 Sant Isidre
  Headsigns: Sant Isidre (165)
  Patrones: 970_2277_1936 (165)
Línea 73 · sentido 0 · origen: derived · viajes: 443 · patrones: 2
  Patrón principal 963_1936_2312: 1936 Sant Isidre → 2312 Sant Pau - Estació del Nord
  Headsigns: Sant Pau - Estació del Nord (443)
  Patrones: 963_1936_2312 (278); 962_1936_2312 (165)
Línea 73 · sentido 1 · origen: derived · viajes: 435 · patrones: 2
  Patrón principal 963_2312_1936: 2312 Sant Pau - Estació del Nord → 1936 Sant Isidre
  Headsigns: Sant Isidre (435)
  Patrones: 963_2312_1936 (273); 962_2312_1936 (162)
Línea 81 · sentido 0 · origen: derived · viajes: 107 · patrones: 1
  Patrón principal 1041_1210_2278: 1210 Blasco Ibáñez - Serradora → 2278 Estació del Nord - Marqués de Sotelo
  Headsigns: Estació del Nord - Marqués de Sotelo (107)
  Patrones: 1041_1210_2278 (107)
Línea 81 · sentido 1 · origen: derived · viajes: 105 · patrones: 1
  Patrón principal 1041_2278_1210: 2278 Estació del Nord - Marqués de Sotelo → 1210 Blasco Ibáñez - Serradora
  Headsigns: Blasco Ibáñez - Serradora (105)
  Patrones: 1041_2278_1210 (105)
Línea 92 · sentido 0 · origen: derived · viajes: 192 · patrones: 1
  Patrón principal 1046_1272_1546: 1272 Campanar - Monestir de Poblet → 1546 La Malva-rosa - Gran Canària
  Headsigns: La Malva-rosa - Gran Canària (192)
  Patrones: 1046_1272_1546 (192)
Línea 92 · sentido 1 · origen: derived · viajes: 190 · patrones: 1
  Patrón principal 1046_1546_1272: 1546 La Malva-rosa - Gran Canària → 1272 Campanar - Monestir de Poblet
  Headsigns: Campanar - Monestir de Poblet (190)
  Patrones: 1046_1546_1272 (190)
Línea 93 · sentido 0 · origen: derived · viajes: 418 · patrones: 1
  Patrón principal 994_488_2271: 488 Avinguda del Cid → 2271 Passeig Marítim - Hospital Malva-rosa
  Headsigns: Passeig Marítim - Hospital Malva-rosa (418)
  Patrones: 994_488_2271 (418)
Línea 93 · sentido 1 · origen: derived · viajes: 403 · patrones: 1
  Patrón principal 994_2271_488: 2271 Passeig Marítim - Hospital Malva-rosa → 488 Avinguda del Cid
  Headsigns: Avinguda del Cid (403)
  Patrones: 994_2271_488 (403)
Línea 94 · sentido 0 · origen: derived · viajes: 168 · patrones: 1
  Patrón principal 873_2324_2307: 2324 França - Camí Fondo del Grao → 2307 Campanar - General Avilés (illeta)
  Headsigns: Campanar - General Avilés (illeta) (168)
  Patrones: 873_2324_2307 (168)
Línea 94 · sentido 1 · origen: derived · viajes: 167 · patrones: 1
  Patrón principal 873_2307_2324: 2307 Campanar - General Avilés (illeta) → 2324 França - Camí Fondo del Grao
  Headsigns: França - Camí Fondo del Grao (167)
  Patrones: 873_2307_2324 (167)
Línea 95 · sentido 0 · origen: derived · viajes: 103 · patrones: 1
  Patrón principal 1047_504_2263: 504 Tres Creus (imparell) - Hospital General → 2263 La Marina - Metro Neptú
  Headsigns: La Marina - Metro Neptú (103)
  Patrones: 1047_504_2263 (103)
Línea 95 · sentido 1 · origen: derived · viajes: 100 · patrones: 1
  Patrón principal 1047_2263_504: 2263 La Marina - Metro Neptú → 504 Tres Creus (imparell) - Hospital General
  Headsigns: Tres Creus (imparell) - Hospital General (100)
  Patrones: 1047_2263_504 (100)
Línea 98 · sentido 0 · origen: derived · viajes: 145 · patrones: 2
  Patrón principal 1055_487_2271: 487 Cid - Pere Maria Orts → 2271 Passeig Marítim - Hospital Malva-rosa
  Headsigns: Passeig Marítim - Hospital Malva-rosa (74); Estació del Cabanyal (71)
  Patrones: 1055_487_2271 (74); 1054_487_2229 (71)
Línea 98 · sentido 1 · origen: derived · viajes: 141 · patrones: 2
  Patrón principal 1055_2271_487: 2271 Passeig Marítim - Hospital Malva-rosa → 487 Cid - Pere Maria Orts
  Headsigns: Cid - Pere Maria Orts (141)
  Patrones: 1055_2271_487 (72); 1054_2229_487 (69)
Línea 99 · sentido 0 · origen: derived · viajes: 383 · patrones: 1
  Patrón principal 1052_2230_1751: 2230 Palau de Congressos → 1751 Mendizábal - Doctor Álvaro López
  Headsigns: Mendizábal - Doctor Álvaro López (383)
  Patrones: 1052_2230_1751 (383)
Línea 99 · sentido 1 · origen: derived · viajes: 379 · patrones: 1
  Patrón principal 1052_1751_2230: 1751 Mendizábal - Doctor Álvaro López → 2230 Palau de Congressos
  Headsigns: Palau de Congressos (379)
  Patrones: 1052_1751_2230 (379)
Línea C1 · sentido 0 · origen: derived · viajes: 165 · patrones: 1
  Patrón principal 1018_1959_2277: 1959 Blanqueria - Pare d'Òrfens → 2277 Xàtiva - Institut Lluís Vives
  Headsigns: Xàtiva - Institut Lluís Vives (165)
  Patrones: 1018_1959_2277 (165)
Línea C1 · sentido 1 · origen: derived · viajes: 163 · patrones: 1
  Patrón principal 1018_2277_1959: 2277 Xàtiva - Institut Lluís Vives → 1959 Blanqueria - Pare d'Òrfens
  Headsigns: Blanqueria - Pare d'Òrfens (163)
  Patrones: 1018_2277_1959 (163)
Línea C2 · sentido 0 · origen: derived · viajes: 108 · patrones: 2
  Patrón principal 651_166_691: 166 Blasco Ibáñez - Facultat de Geografia → 691 Plaça d'Espanya - Ermita
  Headsigns: Plaça d'Espanya - Ermita (56); Estació d'autobusos (52)
  Patrones: 651_166_691 (56); 996_1057_346 (52)
Línea C2 · sentido 1 · origen: derived · viajes: 107 · patrones: 2
  Patrón principal 651_691_166: 691 Plaça d'Espanya - Ermita → 166 Blasco Ibáñez - Facultat de Geografia
  Headsigns: Blasco Ibáñez - Facultat de Geografia (54); Estadi de Mestalla (front) (53)
  Patrones: 651_691_166 (54); 996_346_1057 (53)
Línea C3 · sentido 0 · origen: derived · viajes: 919 · patrones: 2
  Patrón principal 1074_231_1265: 231 Eduard Boscà - Balears → 1265 Conselleria d'Educació
  Headsigns: Conselleria d'Educació (471); Avinguda Campanar - Centre de Salut (448)
  Patrones: 1074_231_1265 (471); 1075_229_1266 (448)
Línea C3 · sentido 1 · origen: derived · viajes: 920 · patrones: 2
  Patrón principal 1074_1265_231: 1265 Conselleria d'Educació → 231 Eduard Boscà - Balears
  Headsigns: Eduard Boscà - Balears (470); Cardenal Benlloch (imparell) - Port (450)
  Patrones: 1074_1265_231 (470); 1075_1266_229 (450)
```

### `./init.sh verify` (2026-10-31, tras T-12)

```
OK   backend: format
OK   backend: lint
OK   backend: types
OK   backend: architecture          (Contracts: 2 kept, 0 broken)
OK   backend: tests                 (215 passed, 2 deselected [slow]; cobertura domain+application 99,29 %)
OK   frontend: format / lint / types
OK   frontend: tests                (7 passed)
OK   frontend: build
OK   harness: feature_list.json
OK   harness: trazabilidad AC→test  (gtfs_import en `implementing`: todos los AC automáticos citados)
OK   verify: todo en verde
```
