# CLI de administración: `avisabus`

La CLI es la herramienta de la persona que administra AvisaBus. Sirve para cargar la red de
autobuses, generar los QR de las paradas, dar acceso a los conductores y preparar
demostraciones. Va en el mismo paquete que el backend y usa su misma configuración (variables
`AVISABUS_*`) y su misma base de datos.

## Cómo se ejecuta

| Dónde | Comando |
|---|---|
| **En desarrollo**, desde `backend/` | `uv run avisabus <comando>` (lee el `.env` de la raíz) |
| **En producción**, en la carpeta del despliegue | `docker compose run --rm -T backend avisabus <comando>` (lee `.env.prod`) |

En producción el comando se ejecuta en un contenedor temporal con la misma imagen, configuración
y volumen `data/` que el backend en marcha. Si el servicio tiene otro nombre en tu
`compose.yaml` (por ejemplo `avisabus-backend`), usa ese.

Todos los comandos aceptan `--help`. Los mensajes para la persona salen en castellano y los
registros en JSON. Los registros nunca incluyen códigos de conductor ni identificadores de
dispositivo.

```
avisabus
├── gtfs           import · info             Red de autobuses (feed GTFS)
├── qr             generate                  QR de las paradas
├── driver-codes   create · list · revoke    Códigos de acceso de los conductores
├── simulate                                 Simulador de recorrido de un conductor
├── sae            fetch · record            Tiempos de llegada del SAE: consultar y grabar
├── occupancy      override                  Forzar la ocupación de una línea (demostraciones)
└── openapi        export                    Contrato OpenAPI de la API
```

## `gtfs`: la red de autobuses

AvisaBus no inventa nada de la red: líneas, paradas, horarios y trazados salen del feed GTFS de
EMT València. Hay que importarlo la primera vez y renovarlo antes de que caduque.

### `gtfs import`

```bash
avisabus gtfs import <carpeta o .zip>
```

Valida el feed, lo importa como versión nueva y la deja activa. Si falla la validación o la
importación, sigue activa la versión anterior y el servicio no se interrumpe (RF-02). Al
terminar muestra un resumen (líneas, paradas, viajes) y avisa si el feed caduca en
`AVISABUS_GTFS_EXPIRY_WARNING_DAYS` días (7) o menos.

- Códigos de salida: `0` correcto, `2` error de validación o de importación.
- En producción, el backend en marcha carga la versión nueva al reiniciarse. El script
  `deploy/gtfs-update.sh` hace todo el proceso: copia, importación, `VACUUM` y reinicio.

### `gtfs info`

```bash
avisabus gtfs info                # versión activa, vigencia y recuentos
avisabus gtfs info --directions   # además, cada sentido de cada línea y su cabecera
```

`--directions` muestra el `direction_id` (0 o 1) de cada sentido, que es el que pide
`simulate --direction`. Si no hay ningún feed importado, termina con código `1`.

## `qr generate`: QR de las paradas

Cada parada tiene un QR con su URL pública firmada (`/p/<parada>?t=<token>`). El token se firma
con `AVISABUS_STOP_TOKEN_SECRET` e impide abrir paradas inventadas o recorrerlas a ciegas.

```bash
avisabus qr generate --stop 496 --stop 508           # paradas concretas (repetible)
avisabus qr generate --all --out qr-impresion        # todas las paradas del feed activo
avisabus qr generate --all --format png --out qr-png # PNG en lugar de SVG
```

| Opción | Valor por defecto | Descripción |
|---|---|---|
| `--stop ID` | — | Parada que se genera. Se puede repetir. |
| `--all` | — | Todas las paradas del feed activo. |
| `--format svg\|png` | `svg` | Formato de los ficheros. |
| `--out DIR` | `qr` | Carpeta de salida. |

- **Salida:** un fichero por parada, con el nombre y el número de la parada debajo del código, y
  un `index.csv` con `stop_id,name,url,file`.
- **Base de las URL:** sale de `AVISABUS_PUBLIC_BASE_URL`. Para generar los QR de producción hay
  que ejecutar el comando con la configuración de producción, es decir, en el servidor.
- **Códigos de salida:** `1` si no hay feed importado, `3` si alguna parada no existe.
- **Cambio de secreto:** si cambia `AVISABUS_STOP_TOKEN_SECRET`, todos los QR impresos dejan de
  valer y hay que generarlos de nuevo.

Hay ejemplos de QR de producción en [`docs/qr/`](qr/README.md).

## `driver-codes`: acceso de los conductores

Los conductores entran en `/driver` con un código de 8 dígitos, sin cuentas ni contraseñas. El
código se guarda cifrado (HMAC, ADR-018), así que **solo se muestra una vez, al crearlo**: si se
pierde, se revoca y se crea otro.

```bash
avisabus driver-codes create --label "Tablet 1"   # crea un código y lo muestra una sola vez
avisabus driver-codes list                        # etiquetas, identificadores y estado (sin los códigos)
avisabus driver-codes list --json                 # lo mismo, en JSON
avisabus driver-codes revoke dc-k3m9qa            # revoca un código por su identificador
```

Salida de `create`:

```
Código creado: dc-k3m9qa  ·  Tablet 1
  Código de acceso: 1234 5678
  Apúntalo ahora: no se volverá a mostrar.
```

- **`--label`:** obligatoria, de 1 a 40 caracteres imprimibles. Sirve para saber de quién es cada
  código.
- **Revocación:** si el código tenía un turno abierto, se cierra en menos de un minuto, en la
  siguiente pasada de la tarea de turnos. Revocar un código ya revocado solo muestra un aviso.
- **Códigos de salida:** `1` si el código no existe, `2` si la etiqueta no es válida.

## `simulate`: recorrido de un conductor sin tablet

Hace de tablet de conductor. Inicia un turno por la API, elige una salida y envía posiciones GPS
a lo largo del trazado real de la línea, deteniéndose en cada parada. Sirve para ver cómo llegan
las solicitudes de parada a la vista del conductor sin salir a la calle.

```bash
export AVISABUS_SIM_CODE=12345678                    # código de conductor (mejor que --code)
avisabus simulate --line 93 --direction 0            # primera salida libre, servidor local
avisabus simulate --line 93 --direction 0 --departure 08:40 --speed-kmh 30 --noise-m 10 --seed 1
avisabus simulate --line 93 --direction 0 --base-url https://avisabus.yeddarpi.com
```

| Opción | Valor por defecto | Descripción |
|---|---|---|
| `--line` | obligatoria | Línea comercial, por ejemplo `93`. |
| `--direction` | obligatoria | `direction_id` del sentido (ver `gtfs info --directions`). |
| `--code` | `AVISABUS_SIM_CODE` | Código de conductor. |
| `--departure HH:MM` | primera salida libre | Hora de salida desde cabecera. |
| `--trip TRIP_ID` | — | `trip_id` de la salida, en lugar de la hora. |
| `--speed-kmh` | `20` | Velocidad. |
| `--interval-s` | `5` | Segundos entre dos posiciones. |
| `--dwell-s` | `15` | Segundos detenido en cada parada. |
| `--noise-m` / `--seed` | `0` / — | Ruido GPS máximo en metros y su semilla (reproducible). |
| `--base-url` | `http://localhost:8000` | Servidor AvisaBus al que se conecta. |

El simulador termina al llegar a la última parada o con `Ctrl+C`, y en los dos casos cierra el
turno. Códigos de salida: `0` terminado o interrumpido, `1` la simulación no ha podido ejecutarse
o el turno no se ha podido cerrar, `2` opciones no válidas.

## `sae`: tiempos de llegada en tiempo real

```bash
avisabus sae fetch --stop 508                       # llegadas normalizadas de una parada, o por qué no hay
avisabus sae record --stop 508 --stop 2070 \
  --interval 20 --duration 3600 --out sesion_508    # graba respuestas reales para reproducirlas
```

- **`fetch`:** consulta la fuente configurada (`AVISABUS_ARRIVALS_SOURCE`) y muestra las llegadas
  normalizadas. Termina con código `1` si no están disponibles.
- **`record`:** consulta las paradas cada `--interval` segundos durante `--duration` segundos y
  guarda cada respuesta en una carpeta de sesión. Con `AVISABUS_ARRIVALS_SOURCE=replay` y
  `AVISABUS_SAE_REPLAY_DIR=<sesión>`, la aplicación reproduce esa sesión como si fuera el SAE
  (RF-35). Así se graba `stop_508_peak`, la sesión de demostración.

> Desde el 12/11/2026 EMT ya no publica la página de la que se leían los tiempos, así que `fetch`
> y `record` contra el SAE real responden "no disponible". Las sesiones grabadas siguen sirviendo.

## `occupancy override`: forzar la ocupación

La ocupación se simula (EMT no la publica). Para enseñar los tres niveles en una demostración se
puede forzar el de una línea durante un tiempo:

```bash
avisabus occupancy override --line 93 --level full --minutes 20   # forzar "lleno" 20 minutos
avisabus occupancy override --list                                # forzados activos
avisabus occupancy override --line 93 --clear                     # quitar el forzado
```

Niveles: `free` (poco ocupado), `medium` (ocupación media) y `full` (lleno). Sin `--minutes`,
dura 30 minutos. Si la línea no existe, termina con código `2`.

## `openapi export`: contrato de la API

```bash
avisabus openapi export --out openapi.json
```

Escribe el documento OpenAPI de la API HTTP. El frontend genera sus tipos TypeScript a partir de
él con `npm run gen:api`, de modo que un cambio en la API se refleja en los tipos del cliente.
