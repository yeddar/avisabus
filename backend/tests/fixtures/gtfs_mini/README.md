# Fixture `gtfs_mini`

## Propósito

GTFS reducido (2–3 líneas, ~20 paradas) para los tests de importación de red y de horarios
programados. Permite probar sin depender del feed real de `data/gtfs/emt/`, que no se versiona.

## Origen de los datos

Subconjunto del GTFS público de EMT València (ficheros `agency.txt`, `stops.txt`, `routes.txt`,
`trips.txt`, `stop_times.txt`, `calendar.txt`, `calendar_dates.txt`, `shapes.txt`,
`feed_info.txt`). Los nombres de paradas y líneas se conservan tal como vienen en el feed.

## Regeneración

El comando de regeneración lo añade la feature `gtfs_import`. Hasta entonces esta carpeta solo
contiene este README.
