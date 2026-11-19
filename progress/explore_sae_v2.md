# Exploración: sae_v2 (retirada de `QR.php` y fuentes alternativas de tiempo real)
Feature(s): sae_arrivals_source (done, v1.4) · Fecha: 2026-11-16 · Agente: explorer

## Pregunta(s)

Desde el 2026-11-12, `https://www.emtvalencia.es/QR.php?sec=est&p=<parada>` responde 404 con 16 B, así que la
app cae siempre al horario del GTFS. Preguntas:

1. ¿En qué estado está hoy `QR.php` (http y https; paradas 508, 708, 10, 1026 y la inexistente 99999) comparado
   con las muestras de noviembre? ¿Se ha movido (redirección, otra ruta, otro parámetro) o ha desaparecido?
2. ¿A dónde llevan ahora los QR de las paradas físicas? ¿Qué consultan la web pública de EMT y su app para
   mostrar los tiempos de llegada (endpoint, parámetros, formato, cabeceras)?
3. ¿Sigue funcionando el `getSAE` del geoportal u otra fuente ya vista? ¿Hay API abierta, GTFS-RT o datos
   abiertos de tiempo real de EMT València, y con qué condiciones de uso?
4. Para las candidatas viables: respuesta real de ejemplo, campos, latencia, límites o bloqueos, y qué habría
   que cambiar en el adaptador y en la spec.

**Peticiones a EMT:** unas 26 en total, entre las 15:30:55 y las 15:37:44 UTC del lunes 2026-11-16 (16:30–16:37
en Madrid). Desglose: 14 a `www.emtvalencia.es`, 9 a `geoportal.emtvalencia.es` y 3 a otros hosts de EMT.
Fueron peticiones únicas, separadas 2–4 s, sin bucles largos; como mucho 2 a `QR.php` por parada. Las cabeceras
fueron `User-Agent: AvisaBus/0.1 (TFM; exploracion sae_v2)`, sin `Referer`, sin cookies y sin datos personales.
Además hubo 1 petición al geoportal del Ajuntament, 5 a su CKAN y consultas a GitHub y PyPI. Las muestras están
en `progress/explore_sae_v2_samples/`: cada petición tiene `.body`, `.headers.txt` y `.meta.txt`.

## Hallazgos

### H-1. `QR.php` ya no existe en el servidor: no hay bloqueo ni traslado

| Petición (2026-11-16) | Código | Cuerpo | Muestra |
|---|---|---|---|
| `https://www.emtvalencia.es/QR.php?sec=est&p=508` | 404 | `File not found.` (16 B) | `qrphp_508_https_20261116T153055Z.*` |
| `http://…/QR.php?sec=est&p=508` | 404 | ídem | `qrphp_508_http_20261116T153058Z.*` |
| `p=708`, `p=10`, `p=1026` (https) | 404 | ídem | `qrphp_{708,10,1026}_https_*` |
| `p=99999` (inexistente) | 404 | ídem | `qrphp_99999_https_20261116T153120Z.*` |
| **Control:** `https://www.emtvalencia.es/noexiste_avisabus_test.php` | 404 | **idéntico**: `File not found.` (16 B) | `ctrl_nonexistent_20261116T153124Z.body` |
| Control: `…/noexiste_avisabus_test.html` | 404 | página 404 estándar de Apache, `iso-8859-1`, 196 B | `ctrl_nonexistent_html_*.body` |
| `https://www.emtvalencia.es/ciudadano/index.php?lang=es` (la "Home" que cita el error de `getSAE`) | 404 | `File not found.` | (salida de curl, no guardada) |
| `https://www.emtvalencia.es/` | 200 | `<meta HTTP-EQUIV="REFRESH" content="0; url=/wp/">` | — |

Cabeceras de hoy (`qrphp_508_https_….headers.txt`): `HTTP/1.1 404 Not Found`, `Server: Apache`,
`Content-Type: text/html; charset=UTF-8`, `Cache-Control: private`. No hay `Location` ni `Vary`, y curl informa
`redirect_url` vacío. Las cabeceras del 2026-11-02 (`progress/explore_sae_samples/stop508_qrphp_https_20261102T110011Z.headers.txt`)
eran `200 OK`, `text/html; charset=utf-8` y 3548 B, con las mismas cabeceras de seguridad. El servidor y el
front-end son los mismos.

**Conclusión.** La respuesta para `QR.php` es la misma, byte a byte, que para un `.php` inventado. Es el mensaje
de PHP-FPM cuando el script no existe. Además da igual la parada (también la 99999), el esquema (http o https) y
el User-Agent (la persona lo comprobó desde el Mac y la Raspberry). Por tanto **el fichero se ha retirado del
servidor**: no es un bloqueo por cliente ni un cambio de parámetro. Con él ha desaparecido todo el sitio antiguo
`/ciudadano/` de `www`, y la web pública es ahora un WordPress en `/wp/`.

Comprobé dos posibles traslados al host `geoportal.emtvalencia.es`, que conserva parte de `/ciudadano/servicios/`:
- `https://geoportal.emtvalencia.es/QR.php?sec=est&p=508` → 200, pero el cuerpo es **el `index.html` del visor
  Angular** (13 723 B, idéntico según `diff` a `/visor`). Es la ruta comodín de la SPA, no una página de parada
  (`geoportal_QR.php_508_*`).
- `https://geoportal.emtvalencia.es/ciudadano/QR.php?sec=est&p=508` → 404 `File not found.` (`geoportal_ciudadano_QR.php_508_*`).

### H-2. Destino de los QR físicos y qué usa la web de EMT

- **Dataset del Ajuntament.** Sigue apuntando a la URL retirada. En la capa 226 del geoportal municipal, consultada
  hoy (`geoportal_226_stops_20261116T153342Z.json`), las paradas 10, 508, 708 y 1026 siguen con
  `"proximas_llegadas": "http://www.emtvalencia.es/QR.php?sec=est&p=<id>"`. En CKAN, el dataset `emt` tiene
  `metadata_modified` del 2026-10-14, anterior a la retirada. **El enlace publicado con CC BY 4.0 está roto.**
- **QR de las marquesinas.** Según la nota de 2012 (esmartcity) y el propio campo del dataset, los QR codifican una
  URL fija `…/QR.php?sec=est&p=<id>`. Mientras EMT no los sustituya o no añada una redirección, **llevan a un 404**.
  No he podido leer un QR físico. *Comprobación manual sugerida a la persona:* escanear uno, por ejemplo el de la
  508, y anotar la URL exacta.
  - Las ~760–900 marquesinas renovadas llevan además códigos **NaviLens**, que solo se leen con la app NaviLens GO
    (cerrada). Esa app lee en voz alta líneas, destinos y esperas; la fuente de los datos no está documentada.
- **Web pública (WordPress `/wp/`).** No tiene consulta de llegadas. La portada y el mapa del sitio (125 enlaces)
  solo enlazan, para eso, al visor `https://geoportal.emtvalencia.es/visor?lang=es`, a las apps y a WhatsApp.
  La API REST `wp-json/emt/v1` solo expone `/invoice/download`.
- **Visor del geoportal (Angular).** Pide las llegadas a `getSAE`. Extractos guardados en
  `visor_getStopEstimations_excerpt.js` y `visor_config_excerpt.js`:
  ```
  GET /EMT/mapfunctions/MapUtilsPetitions.php?sec=getSAE&parada=${id}&adaptados=false&idioma=${lang}&nocache=${Math.random()}
  ```
  - La ruta es relativa al propio `geoportal.emtvalencia.es` (`bus_stop.baseUrl: ""`).
  - El visor interpreta la respuesta como XML y lee **`estimacion.solo_parada.bus[]`**, con los campos `linea`,
    `minutos`, `destino`, `horaLlegada` y `error`.
  - Marca como "cerca" un `minutos` no numérico o entre 1 y 5, y como nocturna la línea que contiene `N`.
- **App oficial** (`es.emtvalencia.emt`). Según dos clientes comunitarios recientes, usa otra API:
  - `Humanoidear/EMT-RealTime`, `app.py`, último push el 2026-09-30.
  - `Humanoidear/OpenTransport-Valencia`, `EmtRepository.kt`, último push el 2026-11-08.
  - Endpoint: `https://servicios.emtvalencia.es/estimaciones/estimacion.php?parada=<id>&idioma=<es|en>&adaptados=false`,
    que devuelve XML `<bus><linea/><destino/><minutos/><horaLlegada/></bus>`. También existe `/buses/linea.php`
    (posiciones).
  - **Exige autenticación WS-Security** (`X-WSSE: UsernameToken …, PasswordDigest=…`). El comentario de `app.py`
    lo dice: *"PasswordDigest = b64(sha1(nonce + created + password)) — needs the app's secret password (extract
    from the EMT APK)"*. También avisa de que, con tokens reutilizados, `estimaciones` devuelve un `<bus/>` vacío.
  - **Comprobado sin credenciales** (`servicios_estimacion_noauth_508_20261116T153533Z.*`): **401 Unauthorized**,
    `Content-Type: text/xml`, cuerpo vacío, 111 ms.
  - El bundle del visor incluye un bloque `emt_services` con usuario y contraseña. **No lo he usado ni lo copio en
    las muestras**: el extracto lo omite expresamente.
- **Otros hosts.** `api.emtvalencia.es` responde 404 `No listener for endpoint: /` (una pasarela sin ruta pública
  en `/`). `sae.emtvalencia.es` resuelve, pero no responde en 8 s.

### H-3. Estado de `getSAE` y búsqueda de datos abiertos de tiempo real

- **`getSAE` del geoportal sigue cerrado a clientes que no son el visor.** Petición:
  `https://geoportal.emtvalencia.es/EMT/mapfunctions/MapUtilsPetitions.php?sec=getSAE&parada=508&adaptados=false&idioma=es`
  (`getsae_geoportal_508_20261116T153310Z.*`).
  - Respuesta 200, `text/html; charset=UTF-8`, 525 B, 81 ms, `Access-Control-Allow-Origin: *`.
  - El cuerpo es el mismo que el 2026-11-02:
    `<estimacion><parada_linea><bus>…<error><![CDATA[<center>Temporalmente no disponible desde el plano.…]]></error></bus></parada_linea><solo_parada /><info /></estimacion>`.
  - **Indicio de que es un filtro deliberado y no una caída:** el visor solo lee `solo_parada.bus`, que en esta
    respuesta está vacío; el error va en `parada_linea`, que el visor ignora. Es decir, el propio visor nunca
    mostraría ese mensaje.
  - Además, el texto enlaza a `/ciudadano/index.php`, que ya da 404: es un mensaje antiguo.
  - Los clientes comunitarios activos (`pyemtvlc` 1.0.0, PR #14 del 2026-06-17 "migrate to geoportal";
    `valencia-transport`, push del 2026-11-13; `ZeppOS-EMT`) siguen usando este endpoint. `pyemtvlc` lo hace con
    `User-Agent` de Chrome y `Referer: https://geoportal.emtvalencia.es/visor?lang=es` (`utils/emtinfo.py`).
  - **No he probado a imitar al visor** (UA de navegador ni `Referer`): sería eludir el control de acceso (ADR-015).
- **No hay API abierta ni GTFS-RT de EMT València:**
  - En el CKAN del Ajuntament (`opendata.vlci.valencia.es`), `package_search` con `q=emt` da 4 datasets: `emt`,
    `emt-travelers-2020-2022`, `google-transit-lines-stops-bus-schedules` y `vulnerabilidad-por-barrios`. Con
    `tiempo real` y `temps real` solo aparecen tráfico, parkings, Valenbisi y contaminación (más `emt`, por el
    enlace `QR.php`). Ninguno trae llegadas en tiempo real. Licencia de todos: `cc-by`.
  - Mobility Database (`mdb-795`): EMT Valencia solo tiene *GTFS Schedule*, sin feed GTFS-RT asociado. El
    `mdb-2215` que aparece al buscar es de EMT **Málaga**.
  - La búsqueda web no da ninguna noticia de una API, un GTFS-RT o una nueva web de llegadas en noviembre de 2026.
- **Condiciones de uso.** El aviso legal de EMT, ya resumido en `explore_sae.md` H-7, sigue vigente
  (`/wp/aviso-legal/` aparece en el mapa del sitio). No hay términos que autoricen usar `getSAE` ni
  `servicios.emtvalencia.es`.

### H-4. Candidatas: ninguna viable hoy

| Candidata | Técnicamente | Acceso legítimo para AvisaBus | Veredicto |
|---|---|---|---|
| `QR.php` (actual) | 404, fichero retirado | Era la URL publicada por el Ajuntament (CC BY) | **Muerta** |
| `getSAE` geoportal / `www` | Responde 200 con datos solo al visor (indicio, no verificado imitándolo) | Solo imitando al visor (UA y `Referer` de navegador) = eludir un control (ADR-015) | **No viable** sin permiso escrito de EMT |
| `servicios.emtvalencia.es/estimaciones` (app) | 401 sin credenciales | Exige WSSE con el secreto de la app o las credenciales embebidas en el visor = acceso no autorizado | **Descartada** (solo con credenciales propias acordadas con EMT) |
| Datos abiertos / GTFS-RT | No existen | — | **No hay** |
| Paneles SAE de las marquesinas, NaviLens, WhatsApp | Canales cerrados para personas | — | **No aplicable** |

**Latencias observadas hoy** (`time_total`): `QR.php` 404, 52–88 ms; `getSAE`, 81 ms; `servicios` 401, 111 ms.
No aparecen cabeceras de límite de uso (`RateLimit`, `Retry-After`) en ninguna respuesta.

**Formato `getSAE` (solo como referencia, por si EMT lo autoriza).** No tengo muestra real con datos, solo la de
error. Fuentes: el código del visor (H-2), los tests de `pyemtvlc` y `explore_sae.md` H-2. El formato esperado es:

```
<estimacion><solo_parada><bus><linea>93</linea><destino>…</destino><minutos>N min.|Próximo</minutos><horaLlegada>HH:MM[:SS]</horaLlegada><error/></bus>…</solo_parada></estimacion>
```

- Cuando se filtra por `linea=<n>`, los `<bus>` vienen en `parada_linea`.
- Con `idioma=en`, el texto de `minutos` cambia (`Next`, según `EMT-RealTime`).
- "Sin estimaciones" llega como `<error>SIN ESTIMACIONES</error>`.

### H-5. Efecto en AvisaBus hoy (código actual, sin cambios)

- `SaeHttpArrivalsSource` convierte el 404 en `ArrivalsUnavailableError(stop_id, "http_404")` (design §6) y
  registra `sae.error`. `GetStopArrivals` cae al horario (RF-09). **El sistema se comporta según la spec:** no
  hay fallo, solo se pierde el tiempo real.
- Hay un coste innecesario: con `AVISABUS_SAE_ERROR_TTL_S=5` (por defecto), cada parada consultada o vigilada
  (`alert_tasks` / `PASSAGE_WATCHER`) vuelve a pedir a EMT una URL muerta cada 5 s como mínimo. Además, en
  `http`, `config.py:155` sigue exigiendo `AVISABUS_SAE_CONTACT` para una fuente que ya no existe.
- Las fixtures de `backend/tests/fixtures/sae_recordings/` (`stop_508_peak`, `samples/*`) no dependen de la red,
  así que tests y replay siguen siendo válidos.

## Impacto en la spec

La spec `sae_arrivals_source` v1.4 **no queda contradicha**: ya prevé este caso (R-01, respaldo GTFS, error
explícito). Pero **no hay ninguna fuente sustituta que se pueda especificar sin una decisión humana**, así que no
cabe "cambiar URL y parser" sin más. Propuestas, de menor a mayor alcance:

1. **Sin cambio de spec, solo configuración (inmediato, decide la persona).** En el `.env` de producción, subir
   `AVISABUS_SAE_ERROR_TTL_S` (p. ej. a `300`) para no pedir cada 5 s una URL muerta. Es una variable que ya
   existe (design §7, AC-11). Para la demo del TFM, `AVISABUS_ARRIVALS_SOURCE=replay` con `stop_508_peak` ya está
   permitido por AC-20. Limitaciones:
   - solo hay tiempo real "grabado" en las paradas grabadas (508 y 2070); el resto cae a `no_recording` y de ahí
     al GTFS;
   - pasado el final de la grabación se repite la última respuesta (AC-15).
   Conviene decirlo en la memoria.

2. **Spec v1.5, cambios menores (requiere CP-3 ligero):**
   - **requirements.md, «Contexto»:** añadir que el 2026-11-12 EMT retiró `QR.php` (404 `File not found.`,
     idéntico al de un `.php` inexistente; ver esta exploración, H-1) y que el enlace del dataset del Ajuntament
     está roto. La fuente queda "sin proveedor activo" hasta que EMT responda (ADR-015).
   - **Nuevo valor `AVISABUS_ARRIVALS_SOURCE=none`** (o `disabled`), con su AC (p. ej. AC-24): la composición
     devuelve una fuente que lanza `ArrivalsUnavailableError(stop_id, "disabled")` **sin red** y no exige
     `AVISABUS_SAE_CONTACT`. Cambios:
     - design §6: motivo `disabled`;
     - design §7: valores `http | replay | none`;
     - AC-20: ampliarlo;
     - `config.py`: `Literal` y validación del contacto.
     Así producción no golpea a EMT y los logs no se llenan de `sae.error`. La UI ya muestra "Sin datos en tiempo
     real". `stop_arrivals_api` (RF-09) no cambia, porque el motivo es transparente para el respaldo; habría que
     comprobar que ningún test o métrica de esa feature enumera los motivos.
   - **Default de `AVISABUS_SAE_URL_TEMPLATE`:** se puede dejar como está (documenta la fuente histórica y las
     grabaciones `qrphp_html` siguen siendo válidas) o vaciarlo y hacerlo obligatorio en `http`. Lo decide la
     persona. Recomiendo dejarlo y anotarlo como "retirada".
   - **docs/architecture.md** (cambio que hace la persona): ADR-015 y R-01 → "materializado el 2026-11-12;
     `QR.php` retirado". En la tabla de ADR, que `getSAE` sigue cerrado a terceros a 2026-11-16 y que la API de la
     app (`servicios.emtvalencia.es`) exige WSSE (401 sin credenciales).

3. **Si EMT autoriza `getSAE` o da credenciales propias** (feature nueva o spec v2.0, con CP-3 completo y
   exploración con muestras reales). Ya está prevista en design §4 ("Otras fuentes"). Habría que especificar:
   - **URL:** `https://geoportal.emtvalencia.es/EMT/mapfunctions/MapUtilsPetitions.php?sec=getSAE&parada={stop_id}&adaptados=false&idioma=es`
     (plantilla `AVISABUS_SAE_URL_TEMPLATE`). Las cabeceras serán las que EMT indique por escrito, nunca un
     `Referer` imitado.
   - **Parser `getsae_xml`** registrado en `PARSERS`, con `source_format: "getsae_xml"` en las grabaciones
     (AC-22). Reglas:
     - leer `solo_parada/bus` (y `parada_linea/bus`);
     - `linea` → `line`, `destino` → `destination`;
     - `minutos` `N min.` → MINUTES; `Próximo`/`Next` → 0;
     - `horaLlegada` `HH:MM[:SS]` → CLOCK_TIME;
     - `<error>` no vacío y sin ningún `<bus>` con `linea` → `unparseable` (o `SIN ESTIMACIONES` → lista vacía,
       AC-07, si se confirma con una muestra real);
     - decodificación de bytes con el XML parser (lo que corrigió `pyemtvlc` en su PR #14).
   - **AC-21 (cabecera de parada):** no tiene equivalente en `getSAE`, porque el XML no trae el nombre de la parada.
     Habría que redefinir cómo se detecta una "parada inexistente" con una muestra real.
   - **Fixtures:** `getsae_geoportal_508_20261116T153310Z.body` (de esta exploración) sirve como caso de error real
     ("no disponible desde el plano" → `unparseable`). Los casos con datos requieren grabaciones autorizadas
     (AC-19).
   - **Tests:** un parser nuevo con sus AC; tests de `http_source` con `MockTransport` y la URL nueva; tests de
     replay con `source_format` `getsae_xml`.
   - **La API de la app (`servicios.emtvalencia.es`)** solo sería admisible con credenciales emitidas por EMT para
     AvisaBus. Necesitaría su propio adaptador (firma WSSE con secreto en `.env`, nunca en logs).

**No propongo** usar `getSAE` imitando al visor ni las credenciales de la app o el visor: contradice ADR-015 y
sería eludir un control de acceso.

## Riesgos

- **R-01 materializado.** Sin una fuente legítima, AvisaBus pierde RF-07 (tiempo real) y en parte RF-20/RF-21
  (paso del autobús detectado por el SAE): el aviso depende del horario GTFS y de la posición del conductor, si la
  hay. Puede afectar a la demo y a la evaluación del TFM. Es una decisión de alcance de la persona.
- **El enlace roto del Ajuntament** puede repararse con otra URL sin aviso. Conviene revisar de vez en cuando la
  capa 226 o el CKAN: una consulta al día como mucho, que la persona puede hacer a mano.
- **`getSAE`:** es una conclusión por indicios. Sin imitar al visor no puedo confirmar si el visor recibe datos
  hoy. *Comprobación manual que la persona puede hacer como usuaria normal:* abrir
  `https://geoportal.emtvalencia.es/visor?lang=es` en un navegador, pulsar la parada 508 y ver si salen
  estimaciones. Opcionalmente, mirar en las herramientas de desarrollo la respuesta de `getSAE`. Si el visor
  tampoco muestra nada, EMT podría haber apagado también el SAE web, y entonces solo quedarían la app y los paneles.
- **Legal:** los clientes comunitarios que siguen funcionando lo hacen imitando al navegador o a la app (WSSE
  extraído del APK). Que existan no implica autorización.
- **Peticiones residuales a EMT** desde la Raspberry mientras siga en `http` con un TTL de error de 5 s
  (propuesta 1).

## Recomendación

1. **Ya (sin código):** dar `QR.php` por retirado (no hay que esperar a que vuelva). En la Pi, la persona decide
   entre seguir en `http` subiendo `AVISABUS_SAE_ERROR_TTL_S` o pasar a `replay` para la demo.
2. **Escribir a EMT de nuevo** (seguimiento del correo del 2026-11-02, ADR-015) y **al portal de datos abiertos
   del Ajuntament** (enlace `proximas_llegadas` roto en el dataset `emt` CC BY). En ambos, preguntar si hay una
   URL sustituta o si pueden autorizar `getSAE` o dar credenciales de API. Lo hace la persona; los agentes no
   envían correos.
3. **CP-3 ligero:** decidir si se abre `sae_arrivals_source` v1.5 con el modo `none` y la nota de retirada
   (propuesta 2). Es pequeño, sin red y sin tocar el parser.
4. **La nueva fuente (propuesta 3) no se especifica hasta tener la autorización de EMT y muestras reales
   obtenidas legítimamente.** Entonces hará falta una exploración corta con grabación.

### Índice de muestras (`progress/explore_sae_v2_samples/`)

- `qrphp_508_https_20261116T153055Z.*`, `qrphp_508_http_20261116T153058Z.*`: 404 `File not found.`
- `qrphp_{708,10,1026}_https_*`, `qrphp_99999_https_*`: 404, idénticas.
- `ctrl_nonexistent_20261116T153124Z.body`: control `.php` inventado, cuerpo idéntico.
- `ctrl_nonexistent_html_20261116T153124Z.body`: control `.html` inventado, 404 de Apache.
- `geoportal_QR.php_508_*`: 200, pero es el `index.html` del visor (ruta comodín).
- `geoportal_ciudadano_QR.php_508_*`: 404 `File not found.`
- `getsae_geoportal_508_20261116T153310Z.*`: `getSAE` con UA honesto y sin `Referer`, "Temporalmente no disponible
  desde el plano".
- `servicios_estimacion_noauth_508_20261116T153533Z.*`: API de la app sin credenciales, 401.
- `geoportal_226_stops_20261116T153342Z.json`: el dataset del Ajuntament sigue enlazando `QR.php`.
- `visor_getStopEstimations_excerpt.js`, `visor_config_excerpt.js`: cómo pide y lee el visor las estimaciones
  (sin el bloque de credenciales).

---
**Resumen para el orquestador:** `QR.php` no está bloqueado, **está retirado**: da 404 `File not found.`, idéntico
al de un `.php` inexistente, con cualquier parada y esquema y sin redirecciones; también ha desaparecido
`/ciudadano/` de `www`. El dataset del Ajuntament y los QR físicos siguen apuntando a esa URL muerta. La web de
EMT solo ofrece llegadas a través del visor del geoportal (`getSAE`), que sigue cerrado a terceros. La app usa
`servicios.emtvalencia.es` con autenticación WSSE (401 sin credenciales). No hay API abierta ni GTFS-RT.
**No hay candidata viable que implementar**: el sistema ya cae al GTFS según la spec. **Requiere CP-3** para que
la persona decida entre seguir solo con el GTFS (subiendo `AVISABUS_SAE_ERROR_TTL_S`), usar el modo `replay`
para la demo y/o una v1.5 pequeña con `AVISABUS_ARRIVALS_SOURCE=none`, y para retomar el contacto con EMT y el
Ajuntament. Un adaptador `getsae_xml` solo con autorización escrita de EMT.
