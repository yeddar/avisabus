# Fixture `sae_recordings`

## Propósito

Respuestas del SAE de EMT València (página `QR.php`, HTML) guardadas en el formato de grabación de
`specs/sae_arrivals_source/design.md` §5, para reproducirlas en los tests con
`SaeReplayArrivalsSource` y con el parser `parse_qrphp_html`. Los tests nunca acceden a la red
(sockets bloqueados).

## Formato

Cada sesión es una carpeta:

```
<sesión>/
├── session.json        started_at, stops, interval_s, source_url_template, source_format
└── <stop_id>/
    └── <offset_s con 6 cifras>.json   stop_id, captured_at, offset_s, status, content_type,
                                       body (texto), error
```

- `source_format` es `"qrphp_html"` en todas (AC-22).
- `offset_s` son los segundos desde `started_at`; el replay elige, por parada, la grabación con
  mayor `offset_s` que no supere el tiempo transcurrido (AC-15).
- Las fixtures **derivadas** (no reales) llevan `derived_from` (fichero de origen) y `note` (qué
  se cambió), tanto en `session.json` como en la respuesta.
- Campos adicionales (`note`, `source_sample`, `source_url`) son informativos; el replay los
  ignora.

## Sesiones

### `samples/e01_2026-11-02/` — real

- **Fecha:** lunes 2026-11-02, de 10:59:09 a 11:02:43 UTC (11:59–12:03 en Madrid).
- **Cómo se obtuvo:** son las respuestas brutas de la exploración E-01 (`progress/explore_sae.md`),
  peticiones `curl` manuales con User-Agent `AvisaBus/0.1 (TFM; exploracion E-01)` y como
  máximo 1 petición cada 20 s por parada. Se convirtieron sin modificar el cuerpo desde
  `progress/explore_sae_samples/*.body` (+ `.meta.txt` para `captured_at`, estado y
  `content_type`); cada respuesta indica su muestra de origen en `source_sample` y la URL pedida
  en `source_url` (algunas por `http://`, que según E-01 devuelve lo mismo que `https://`).
- **Intervalo:** irregular (peticiones manuales), por eso `interval_s` es `null`.
- **Contenido:**

| Parada | `offset_s` | Caso |
|---|---|---|
| 508 | 0, 62, 147, 180, 212 | Minutos (líneas 93 y 70); la ETA de la 93 baja de 7 a 2 min |
| 2070 | 50 | Minutos + **`Próximo`** (línea 95, primera entrada) |
| 2070 | 149, 182, 214 | Minutos; la 95 ya ha pasado: su primera llegada salta a `10 min.` (paso de un autobús) |
| 99999 | 54 | **Parada inexistente**: HTTP 200 con la cabecera vacía y sin entradas → `unparseable` (AC-21). Es el caso de error grabado de AC-19 (d) |

### `samples/derived_no_arrivals/` — derivada (AC-19 b)

- **Origen:** `progress/explore_sae_samples/stop508_qrphp_https_20261102T110011Z.body` (real,
  2026-11-02 11:00:11 UTC).
- **Cambio:** se quitaron los cuatro bloques de llegada (`<div style="padding-left: 5px;…">…</div>`);
  la cabecera `508 - Parc de l'Oest - Enguera` y el resto de la página no cambian. Así queda como
  la página real de la parada inexistente, pero con cabecera válida.
- **Por qué derivada:** en E-01 no se observó ninguna parada existente sin llegadas.

### `samples/derived_clock_time/` — derivada (AC-19 c)

- **Origen:** el mismo fichero que la anterior.
- **Cambio:** el texto de la última llegada (línea 70) `Alboraia - 20 min.` pasa a
  `Alboraia - 22:41`; nada más.
- **Por qué derivada:** en E-01 no apareció ninguna hora `HH:MM`; el formato
  `"{destino} - HH:MM"` es un **supuesto** de design §4. La grabación nocturna opcional (T-08b)
  debe confirmarlo o desmentirlo.

### `stop_508_peak/` — real (AC-19 a)

- **Fecha:** lunes 2026-11-02 (laborable), de 20:42:23 a 21:07:04 en Madrid (19:42:23–20:07:04
  UTC). **Fuera de hora punta:** se grabó a última hora de la tarde, a petición de la persona,
  en lugar de en la hora punta de la mañana prevista en T-08. El nombre de la carpeta se mantiene
  porque es el valor por defecto de `AVISABUS_SAE_REPLAY_DIR`.
- **Paradas:** 508 y 2070 (en cada ciclo, primero la 508 y luego la 2070).
- **Intervalo y duración:** 20 s durante 25 min: 75 ciclos (`offset_s` de 0 a 1480), es decir,
  150 consultas (75 por parada).
- **Cómo se obtuvo:** con la CLI de la feature contra `QR.php`, con `AVISABUS_SAE_CONTACT`
  definido (User-Agent `AvisaBus/0.1.0 (TFM; <contacto>)`); paradas, intervalo y carpeta según
  `session.json`, y `--duration 1500` según sus 75 ciclos:

  ```
  cd backend
  AVISABUS_ENV=dev AVISABUS_SAE_CONTACT='<contacto>' \
    uv run avisabus sae record --stop 508 --stop 2070 --interval 20 --duration 1500 \
    --out tests/fixtures/sae_recordings/stop_508_peak
  ```

- **Consultas fallidas:** 0 (las 150 respuestas son HTTP 200 y el parser las interpreta todas
  sin descartar ninguna entrada).
  No hay fixtures derivadas: todas las respuestas son reales.
- **Pasos de autobús observados en la 508** (detector de `tests/unit/test_sae_fixtures.py`: la
  primera ETA de la línea llega a 0–2 min y en la respuesta siguiente salta al autobús siguiente):

| `offset_s` | Línea | Destino |
|---|---|---|
| 520 | 70 | Alboraia |
| 1040 | 93 | Pass. Marítim |
| 1180 | 70 | Alboraia |

  En la 2070 el mismo detector encuentra 8 pasos (líneas 73, 95 y 99).

## Regeneración

Las sesiones reales nuevas se graban con la CLI (requiere red; nunca en los tests ni en CI).
`sae record` se niega a escribir en una carpeta que ya tenga `session.json` (sale con código 2),
así que cada grabación va a una carpeta `--out` **nueva**; las sesiones existentes no se
sobrescriben. Por ejemplo, para repetir una sesión como `stop_508_peak` (paradas 508 y 2070,
intervalo 20 s, 25 min):

```
cd backend
AVISABUS_SAE_CONTACT=<contacto> uv run avisabus sae record --stop 508 --stop 2070 --interval 20 \
    --duration 1500 --out tests/fixtures/sae_recordings/stop_508_<AAAA-MM-DD>
```

Para usarla como sesión de replay, apunta `AVISABUS_SAE_REPLAY_DIR` a la carpeta nueva. Sustituir
`stop_508_peak` (el valor por defecto de esa variable, del que dependen los tests de
`test_sae_fixtures.py`) es una decisión aparte: hay que borrar o renombrar antes la carpeta
existente y revisar esos tests y su documentación arriba.

Las muestras de `samples/` no se regeneran: proceden de la exploración E-01 y se convirtieron una
sola vez con un script desechable que aplicaba exactamente las reglas descritas arriba.
