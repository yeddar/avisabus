# Despliegue de AvisaBus en la Raspberry Pi

Guía de operación (feature `deployment_rpi`). Las imágenes se construyen en el **Mac (Apple
Silicon)** para `linux/arm64` y se llevan a la **Raspberry Pi** por SSH: la Raspberry no necesita
el código ni compilar nada. Delante está el **Nginx Proxy Manager (NPM)** que ya existe en la
Raspberry, con el dominio y el certificado de Let's Encrypt.

```
Mac: deploy/ship.sh ──ssh──▶ Raspberry Pi: NPM (TLS) ─▶ web (nginx + PWA) ─▶ backend (uvicorn) ─▶ data/ (SQLite)
```

| Fichero | Para qué |
|---|---|
| `compose.yaml` | Servicios `web` y `backend`, red interna y red de NPM |
| `nginx/` | Configuración de nginx del contenedor `web` (va dentro de la imagen; en la Raspberry, copia de referencia) |
| `.env.prod.example` | Plantilla de la configuración de producción (`.env.prod`, solo en la Raspberry) |
| `ship.env.example` | Plantilla de `ship.env` (destino del despliegue, solo en el Mac) |
| `ship.sh` | Construir, enviar, arrancar y comprobar; `--rollback <versión>` |
| `gtfs-update.sh` | Renovar el feed GTFS |
| `smoke.sh` | Comprobaciones tras el despliegue |

Ni `.env.prod` ni `ship.env` se versionan (`.gitignore`). `ship.sh` nunca copia `.env.prod`.

## 1. Requisitos

**En el Mac:** Docker con Compose v2 y `buildx` (p. ej. Colima), `git`, `ssh`, `rsync`, `curl` y
`python3`. Acceso SSH a la Raspberry **con clave** (sin contraseña).

**En la Raspberry Pi** (SO de 64 bits, `arm64`):

- Docker y Docker Compose **v2.24 o posterior** (`docker compose version`). El usuario de SSH debe
  poder usar `docker` sin `sudo` (grupo `docker`).
- NPM funcionando en Docker. Anota el **nombre de su red**:

  ```bash
  docker network ls                       # p. ej. npm_default
  docker inspect <contenedor-de-npm> --format '{{json .NetworkSettings.Networks}}'
  ```

- El dominio apuntando a la Raspberry y los puertos 80/443 llegando a NPM (ya existe).

Comprueba que todo construye en el Mac antes de empezar:

```bash
./init.sh verify-deploy
```

## 2. Configuración en el Mac (`deploy/ship.env`)

```bash
cp deploy/ship.env.example deploy/ship.env
```

Rellena `RPI_HOST` (p. ej. `pi@raspberrypi.local` o un alias de `~/.ssh/config`), `RPI_DIR`
(ruta absoluta sin espacios, p. ej. `/home/pi/avisabus`), `PUBLIC_URL` (`https://<tu-dominio>`) y
`NPM_NETWORK` (la red de NPM del paso anterior).

## 3. Primer despliegue

### 3.1. Configuración de producción (en la Raspberry)

```bash
ssh <RPI_HOST> 'mkdir -p <RPI_DIR>'
scp deploy/.env.prod.example <RPI_HOST>:<RPI_DIR>/.env.prod
ssh <RPI_HOST>
cd <RPI_DIR>
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # el secreto: guárdalo aparte
nano .env.prod
```

En `.env.prod` rellena como mínimo:

- `AVISABUS_PUBLIC_BASE_URL=https://<tu-dominio>` (sin barra final). Es la base de los enlaces de
  los QR: si cambia, hay que regenerar e imprimir los QR.
- `AVISABUS_STOP_TOKEN_SECRET=<el secreto generado>`. Cambiarlo invalida todos los QR impresos.
- `AVISABUS_SAE_CONTACT=<un correo de contacto>`: EMT lo verá en el User-Agent.

Con `AVISABUS_ENV=prod`, el backend **no arranca** si falta el secreto, si la fuente es `http` y
falta el contacto, o si la URL pública no empieza por `https://`; el error nombra la variable.

```bash
chmod 600 .env.prod
```

### 3.2. *Proxy Host* en NPM (antes del primer envío)

Créalo **antes** de `deploy/ship.sh`, que termina comprobando la URL pública con
`deploy/smoke.sh`. NPM acepta el destino `web` aunque el contenedor todavía no exista: hasta el
primer envío, el dominio responde `502 Bad Gateway`.

En la interfaz de NPM, **Hosts → Proxy Hosts → Add Proxy Host**:

- *Domain Names*: `<tu-dominio>`.
- *Scheme* `http`, *Forward Hostname / IP* **`web`**, *Forward Port* **`80`** (NPM y `web`
  comparten la red `NPM_NETWORK`; `web` no publica puertos en la Raspberry).
- Activa **Websockets Support** (necesario para `/ws/`) y *Block Common Exploits*.
- Pestaña **SSL**: el certificado de Let's Encrypt del dominio, **Force SSL** y **HTTP/2**.
- No añadas cabeceras propias: `web` ya pone las de seguridad y caché.

NPM añade la IP real del cliente al final de `X-Forwarded-For`; `web` toma esa última dirección
(solo confía en redes privadas) y se la pasa al backend como única entrada, así que los límites
por IP no se pueden falsear con esa cabecera. Por eso `web` nunca debe publicar puertos.

### 3.3. Enviar y arrancar (en el Mac)

```bash
deploy/ship.sh
```

Construye `avisabus-backend` y `avisabus-web` con la versión `git describe --tags --always
--dirty`, las copia (`docker save | ssh docker load`), sincroniza `compose.yaml` y `nginx/`, fija
la versión en `<RPI_DIR>/.env` (lo leen todos los `docker compose` de esa carpeta), prepara
`data/` para el usuario del contenedor (uid 10001), arranca y ejecuta `deploy/smoke.sh`. Mientras
no haya feed GTFS, `/api/v1/health` responde `degraded` (aviso, no error).

Si `ship.sh` termina con `FALLO` en las comprobaciones (por ejemplo, porque el *Proxy Host*, el
DNS o el certificado aún no están listos), el servicio ya está arrancado en la Raspberry: corrige
lo que indique el motivo y repite solo la comprobación, sin volver a enviar:

```bash
deploy/smoke.sh https://<tu-dominio>
deploy/smoke.sh https://<tu-dominio> --ip-limit   # opcional (AC-05): bloquea tu IP para el
                                                  # acceso de conductores durante 15 min
```

### 3.4. Importar el GTFS

Descarga el zip del GTFS de EMT València y, en el Mac:

```bash
deploy/gtfs-update.sh ~/Descargas/google_transit.zip
```

### 3.5. Códigos de conductor y QR de las paradas (en la Raspberry)

```bash
cd <RPI_DIR>
# Un código por tablet o conductor; se muestra solo esta vez.
docker compose run --rm backend avisabus driver-codes create --label "Tablet 1"
docker compose run --rm backend avisabus driver-codes list              # sin los códigos
docker compose run --rm backend avisabus driver-codes revoke <code_id>    # p. ej. dc-k3m9qa

# QR de las paradas (con AVISABUS_PUBLIC_BASE_URL y el secreto de .env.prod).
docker compose run --rm backend avisabus qr generate --all --format svg --out /data/qr
```

Los QR quedan en `<RPI_DIR>/data/qr/`; cópialos al Mac para imprimirlos:

```bash
scp -r <RPI_HOST>:<RPI_DIR>/data/qr ./qr-impresion
```

## 4. Actualizaciones

En el Mac, con los cambios en `git` (si hay cambios sin *commit*, la versión acaba en `-dirty`):

```bash
deploy/ship.sh
```

Al terminar muestra la versión anterior y el comando para volver a ella. Las imágenes anteriores
se quedan en la Raspberry con su etiqueta.

## 5. Renovar el GTFS

El GTFS caduca (`feed_end_date`). El sistema avisa:

- `GET /api/v1/health` incluye `gtfs.days_left`; con el feed caducado (o sin feed) `status` es
  `degraded` (sigue respondiendo `200`). `deploy/smoke.sh` lo muestra.
- El backend registra `gtfs.feed_expiring` al arrancar y una vez al día cuando faltan
  `AVISABUS_GTFS_EXPIRY_WARNING_DAYS` días (7) o menos, y `gtfs.feed_expired` cuando ha caducado:

  ```bash
  ssh <RPI_HOST> 'cd <RPI_DIR> && docker compose logs backend | grep gtfs.feed_'
  ```

Para renovarlo, descarga el zip nuevo y, en el Mac:

```bash
deploy/gtfs-update.sh <zip>
```

Copia el zip a `data/gtfs/incoming.zip`, lo importa con la CLI dentro del contenedor, compacta la
base de datos (`VACUUM`) y reinicia el backend. Si la importación falla, termina con error **sin
reiniciar**: la versión activa no cambia.

## 6. Pasar a la grabación (`replay`) y volver

Para dejar de consultar el SAE de EMT sin reconstruir (por ejemplo, si EMT lo pide), en la
Raspberry:

```bash
cd <RPI_DIR>
nano .env.prod                  # AVISABUS_ARRIVALS_SOURCE=replay
docker compose up -d backend    # recrea el backend con la nueva configuración
```

La grabación `stop_508_peak` va dentro de la imagen (`AVISABUS_SAE_REPLAY_DIR`). Para volver al
SAE real, pon `AVISABUS_ARRIVALS_SOURCE=http` y repite `docker compose up -d backend`.

## 7. Volver a una versión anterior

```bash
ssh <RPI_HOST> 'docker image ls avisabus-backend'    # versiones disponibles
deploy/ship.sh --rollback <versión>                  # en el Mac
```

Cambia la versión fijada en `<RPI_DIR>/.env`, arranca esas imágenes y ejecuta `smoke.sh`. La base
de datos no se toca: si la versión nueva hubiera cambiado su estructura, restaura también la
copia (sección 9, «Restaurar una copia»).

Para liberar espacio, borra las versiones que ya no quieras (nunca la que está en uso):

```bash
ssh <RPI_HOST> 'docker image rm avisabus-backend:<versión> avisabus-web:<versión>'
```

## 8. Logs

```bash
ssh <RPI_HOST>
cd <RPI_DIR>
docker compose ps
docker compose logs -f backend          # JSON; sin IP ni cadena de consulta en los accesos
docker compose logs --since 1h web
```

Los logs rotan solos (10 MB × 3 por contenedor). `web` no escribe log de acceso: el útil es el
del backend.

## 9. Copia de la base de datos

Con el servicio parado, para que la copia sea consistente:

```bash
ssh <RPI_HOST>
cd <RPI_DIR>
docker compose stop web backend
cp data/avisabus.sqlite "avisabus-$(date +%Y%m%d-%H%M).sqlite"
docker compose start backend web
```

Guarda también `.env.prod` en un lugar seguro: sin el mismo secreto, los QR impresos dejan de
valer.

### Restaurar una copia

`data/` y la base de datos son del usuario del contenedor (uid 10001), así que el usuario de SSH
no puede sobrescribirlas: un `cp` o un `rm` directos dan *Permission denied*. Restaura con un
contenedor como root, que además deja los ficheros otra vez con el propietario 10001:

```bash
ssh <RPI_HOST>
cd <RPI_DIR>
COPIA=avisabus-AAAAMMDD-HHMM.sqlite    # la copia que quieres restaurar, en <RPI_DIR>
docker compose stop web backend
docker compose run --rm --no-deps -T --user 0 -v "$PWD/$COPIA:/restore.sqlite:ro" \
  --entrypoint sh backend -c '
    cp /restore.sqlite /data/avisabus.sqlite &&
    rm -f /data/avisabus.sqlite-wal /data/avisabus.sqlite-shm &&
    chown 10001:10001 /data /data/avisabus.sqlite &&
    chmod 644 /data/avisabus.sqlite'
docker compose start backend web
docker compose ps                      # backend debe quedar «healthy»
```

Si prefieres `sudo` en la Raspberry, los pasos son los mismos con el servicio parado:

```bash
sudo cp "$COPIA" data/avisabus.sqlite
sudo rm -f data/avisabus.sqlite-wal data/avisabus.sqlite-shm
sudo chown 10001:10001 data data/avisabus.sqlite
sudo chmod 644 data/avisabus.sqlite
```
