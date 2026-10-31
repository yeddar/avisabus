# Implementación: gtfs_import
Spec: specs/gtfs_import/ (v1.1, APPROVED) · Ciclo de revisión: 0 · Agente: implementer · Fecha: 2026-10-31

> **Estado: DETENIDA en T-04 por CP-3** (contradicción entre la spec y los datos del feed; ver
> "Bloqueos"). T-01 a T-03b están hechas y en verde.

## Tareas
- [x] T-01 Modelos de red, `parse_gtfs_time` y normalización de nombres (AC-07, AC-08) (commit 6257969)
- [x] T-02 Servicios activos por fecha (AC-14) (commit e7f6419)
- [x] T-03 Estado de vigencia y vigencia sin `feed_info` (AC-19, AC-20) (commit d7959f9)
- [x] T-03b `derive_directions` con patrones sintéticos (AC-24, AC-25) (commit 8939de8)
- [ ] T-04 Script `make_gtfs_mini.py` y fixture `gtfs_mini` — **bloqueada (CP-3)**. El script
      está escrito y sin commit en `backend/scripts/make_gtfs_mini.py`. Implementa design §8 tal
      cual. La fixture generada se ha borrado: se regenera en segundos.
- [ ] T-05 Lector `CsvGtfsFeedReader`
- [ ] T-06 Base de datos (motor, PRAGMAs, tablas)
- [ ] T-07 `SqliteGtfsFeedWriter`
- [ ] T-08 Caso de uso `ImportGtfsFeed`
- [ ] T-09 `SqliteNetworkRepository`
- [ ] T-10 CLI `gtfs import` / `gtfs info [--directions]`
- [ ] T-11 Importación del feed real (tiempo, memoria, salida de `--directions`)
- [ ] T-12 `.env.example` y verificación completa

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

## Bloqueos

### B-01 (CP-3) — La fixture definida en design §8 no contiene los datos que piden AC-24 y AC-29

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

### Observación no bloqueante (para resolverla junto con B-01): `gtfs import --yes`
Design §3 define `avisabus gtfs import PATH [--yes]`, pero la spec no describe ninguna
confirmación interactiva ni qué hace `--yes`. Propuesta: aclararlo en design §3. Por ejemplo:
- "sin `--yes`, si ya hay una versión activa, se pide confirmación; si se rechaza, exit 1"; o
- "`--yes` se acepta por compatibilidad y no tiene efecto".

Si no se aclara, la implementación aceptará el flag sin efecto y lo anotará aquí.

## Verificación

Estado al detenerse (2026-10-31), `./init.sh verify`:

```
OK   backend: format
OK   backend: lint
OK   backend: types
OK   backend: architecture
OK   backend: tests          (101 passed; cobertura domain+application 99 %)
OK   frontend: format / lint / types / tests / build
OK   harness: feature_list.json
FAIL harness: trazabilidad AC→test   (esperado: AC-01…06, 09…13, 15…18, 23, 26…29 aún sin
                                      test, porque las tareas T-04…T-12 no se han hecho)
```
