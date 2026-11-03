# Fixture `gtfs_mini`

## Propósito

GTFS reducido para los tests de importación de red y de horarios programados
(`specs/gtfs_import/`, AC-21). Permite probar sin depender del feed real de `data/gtfs/emt/`,
que no se versiona.

## Origen de los datos

- **Feed de origen:** GTFS estático público de EMT València, `feed_version` `23-10-2026`
  (vigencia 2026-10-16 → 2026-11-22), copiado en `data/gtfs/emt/`.
- **Líneas:** 70, 93, 98 y C2.
- **Fecha de referencia:** `2026-11-09` (lunes). Se conservan los viajes cuyos servicios están
  activos ese día o el anterior (domingo 2026-11-08). Así entran los servicios de lunes a jueves
  / viernes y los del domingo.

Las filas se copian **literalmente** del feed (mismos bytes, finales de línea `CRLF`, espacios
sobrantes en algunos nombres), para que la fixture conserve las particularidades del feed real.

## Contenido

| Fichero | Filas |
|---|---|
| agency.txt | 1 |
| feed_info.txt | 1 |
| routes.txt | 6 (`route_id` 1054, 1055, 1058, 996, 651, 994) |
| trips.txt | 1 109 |
| stop_times.txt | 29 040 |
| stops.txt | 178 |
| shapes.txt | 2 882 |
| calendar.txt | 8 |
| calendar_dates.txt | 0 (solo cabecera) |

Casos que cubre:
- Parada **508** (servida por 70 y 93) y parada **2070** (servida por la 98).
- **98:** dos `route_id` (1054 laborables, 1055 domingos) y una variante corta en el mismo
  sentido (`1054_487_2229`, que acaba en 2229, frente a `1055_487_2271`). Dos formas por sentido.
- **C2:** dos `route_id` (651 y 996) con medios bucles de giro opuesto. Dos formas por sentido.
- Viajes con horas ≥ 24:00:00 (máximo `26:12:02`), para el caso de madrugada.
- Sin `direction_id` en `trips.txt` (como el feed real): los sentidos se derivan al importar.

Tamaño total: ≈ 2,15 MB (< 2,5 MB, design §8).

## Regeneración

Desde `backend/`, con el feed real en `data/gtfs/emt/`:

```
uv run python scripts/make_gtfs_mini.py --src ../data/gtfs/emt --lines 70,93,98,C2 \
    --date 2026-11-09 --out tests/fixtures/gtfs_mini
```

El script falla si las líneas elegidas no sirven las paradas 508 y 2070. No sobrescribe este
README.
