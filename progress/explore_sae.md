# Exploración: endpoint y formato del SAE de EMT València
Feature(s): sae_arrivals_source (E-01) · Fecha: 2026-11-02 · Agente: explorer

## Pregunta(s)

E-01 de `specs/sae_arrivals_source/tasks.md`. Hay que averiguar:

- el endpoint real de "próximas llegadas" por parada: URL, parámetros, método, `content_type`, codificación y estructura;
- ejemplos reales de las paradas 508 y 2070 para estos casos: minutos, hora `HH:MM`, "llegando/en parada", sin llegadas y parada inexistente;
- la latencia;
- las condiciones de uso;
- si el resultado contradice design §4 o requirements.

Fuentes de partida: el dataset `emt` de opendata.vlci.valencia.es, la capa 226 del geoportal y el cliente comunitario `emtvlcapi`.

Peticiones hechas al servicio de EMT: 14 en total, entre 10:59 y 11:03 UTC (11:59–12:03 hora de Madrid, lunes laborable). Nunca hubo más de 1 petición por parada cada 20 s. User-Agent honesto: `AvisaBus/0.1 (TFM; exploracion E-01)`. No se ha grabado `stop_508_peak` (eso es T-08).

## Hallazgos

### H-1. La URL publicada por el Ajuntament es `QR.php` (página HTML)

La capa 226 del geoportal tiene el campo `proximas_llegadas` (texto, longitud 60000).

```
curl 'https://geoportal.valencia.es/server/rest/services/OPENDATA/Trafico/MapServer/226/query?where=id_parada+IN+(508,2070)&outFields=id_parada,denominacion,lineas,proximas_llegadas&returnGeometry=false&f=json'
→ 508:  "lineas":"70,93",        "proximas_llegadas":"http://www.emtvalencia.es/QR.php?sec=est&p=508"
→ 2070: "lineas":"73,95,98,99",  "proximas_llegadas":"http://www.emtvalencia.es/QR.php?sec=est&p=2070"
```

Muestra: `explore_sae_samples/geoportal_226_stops_508_2070.json`.

El dataset CKAN `emt` (`opendata_emt_package_metadata.json`) tiene licencia CC BY 4.0. Define el campo así: *"Enlace web (URL) directo a la plataforma de la EMT para consultar la estimación en tiempo real de las próximas llegadas de autobuses a esa parada específica."*

### H-2. El endpoint de `emtvlcapi` (`getSAE`, XML) ya no da datos

En `emtvlcapi` 1.0.0 (sdist descargado en el scratchpad, sin instalar), `src/emtvlcapi/emtvlcapi.py:6` usa:

```
EMT_BUS_TIMES_URL = "https://www.emtvalencia.es/EMT/mapfunctions/MapUtilsPetitions.php?sec=getSAE"
params: parada=<id>, adaptados=true|false, [linea=<n>]
```

- Las cabeceras del cliente imitan un navegador: User-Agent de Firefox y `Referer: https://www.emtvalencia.es`.
- La respuesta es XML: `<estimacion><parada_linea|solo_parada><bus><linea/><destino/><minutos/><horaLlegada/><error/></bus>…`.
- `minutos` vale `"N min."` o empieza por `"Pr"` (Próximo).
- La biblioteca convierte `destino` de latin-1 a utf-8.

Otro cliente, `pyemtvlc` 1.0.0 (junio de 2026, `utils/emtinfo.py:3`), usa el mismo `sec=getSAE`, pero en el host `https://geoportal.emtvalencia.es/` con `Referer: https://geoportal.emtvalencia.es/visor?lang=es` y User-Agent de Chrome. Sus tests con datos simulados muestran `<horaLlegada>22:38</horaLlegada>` para la línea N7 y `<error>SIN ESTIMACIONES</error>`.

Lo observado con nuestro User-Agent honesto y sin `Referer`:

| Fichero | Resultado |
|---|---|
| `stop2070_getsae_20261102T105917Z.*` (www) | 200, `text/html; charset=UTF-8`, 524 B |
| `stop508_geoportal_getsae_20261102T110120Z.*` (geoportal.emtvalencia.es) | 200, 525 B, `Access-Control-Allow-Origin: *` |

Las dos devuelven solo una entrada de error:

```xml
<?xml version="1.0" encoding="utf-8"?><estimacion><parada_linea><bus><linea /><destino /><minutos /><horaLlegada />
<error><![CDATA[<center>Temporalmente no disponible desde el plano.<br/>Consulta las estimaciones de llegada desde la
<a href="/ciudadano/index.php?lang=es">Home</a> o desde <a href="...">nuestra APP</a>...]]></error></bus></parada_linea><solo_parada /><info /></estimacion>
```

EMT ha cerrado este endpoint a los clientes que no son su visor. Probablemente lo filtra por `Referer`. **No he probado a enviar un `Referer` o un User-Agent de navegador**: sería eludir un control de acceso, y el sistema de permisos lo denegó al intentarlo. Este endpoint **no es apto** para AvisaBus.

### H-3. Formato de `QR.php` (endpoint recomendado)

- **URL:** `https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}`. Método GET. Parámetros: `sec=est` (fijo) y `p` (id de parada).
  - HTTP y HTTPS devuelven el mismo contenido: comparar `stop508_qrphp_http_…105909Z` con `stop508_qrphp_https_…110011Z`.
  - No hay redirección. No se necesitan cookies (ninguna respuesta de `QR.php` trae `Set-Cookie`).
  - Responde 200 con nuestro User-Agent propio, sin `Referer`.
- **Cabeceras de respuesta:**
  - `Content-Type: text/html; charset=utf-8`
  - `Cache-Control: private`
  - `Transfer-Encoding: chunked`
  - `Server: Apache`
  - no hay cabeceras de límite de uso (`RateLimit`, `Retry-After`).
- **Codificación:** UTF-8 válido (`b'Mar\xc3\xadtim'`, `b'Pr\xc3\xb3ximo'`). El cuerpo también declara `<meta … charset=UTF-8>`. Contiene entidades HTML (`&nbsp;`). No hace falta el arreglo latin-1 que aplica `emtvlcapi`.
- **Estructura:** es una página jQuery Mobile, no un documento completo (no hay `<html>` ni `<body>`). Pesa unos 3,5 KB con 4 llegadas y unos 4,9 KB con 8. Partes relevantes:
  - Cabecera: `<div style=" background: grey; …">{stop_id} - {nombre parada}</div>`.
  - Una llegada por bloque:
    ```html
    <div style="padding-left: 5px;…border-bottom:1px solid black;" ><span class="imagenParada">
      <img src="http://www.emtvalencia.es/EmtEsquemas_graphics/line-icons/93bigW.gif" title="93" width="25px" height="25px"></span>
      <span style="position: relative; top: -5px;">&nbsp;&nbsp;Pass. Marítim - 7 min.</span></div>
    ```
  - **La línea** solo aparece en el atributo `title` del `<img>` (también en el nombre del gif).
  - **El destino y el tiempo** van juntos en un solo texto, `"{destino} - {tiempo}"`, precedido de `&nbsp;&nbsp;`.
- **Orden:** ascendente por tiempo, mezclando líneas. Hay como máximo 2 llegadas por línea: 508 da 4 entradas (2×70, 2×93) y 2070 da 8 (2×73, 2×95, 2×98, 2×99).

Para extraer los datos uso `explore_sae_samples/extract_qrphp.py`, solo con la biblioteca estándar:

```
python3 -I progress/explore_sae_samples/extract_qrphp.py progress/explore_sae_samples
```

### H-4. Casos observados (muestras reales)

| Caso | Muestra | Fragmento |
|---|---|---|
| **Minutos** (508) | `stop508_qrphp_https_20261102T110011Z.body` | `title="93"` → `Pass. Marítim - 5 min.`; `title="70"` → `Alboraia - 8 min.` |
| **Minutos** (2070) | `stop2070_qrphp_https_series_20261102T110243Z.body` | `73` → `Sant Isidre - 2 min.`, `99` → `La Malva-rosa - 4 min.`, … |
| **Llegando** (2070) | `stop2070_qrphp_20261102T105959Z.body` | `title="95"` → `Tres Creus - Próximo` (primera entrada). |
| **Paso de autobús** (2070) | mismo fichero y series posteriores | La entrada `95 Tres Creus - Próximo` (10:59:59 Z) ya no está a las 11:01:38 Z. La primera llegada de la 95 pasa a ser `Tres Creus - 10 min.`. |
| **Parada inexistente** (99999) | `stop99999_qrphp_nonexistent_20261102T110003Z.body` | HTTP **200**, mismo `content_type`, 2144 B. La cabecera está **vacía** (`<div style=" background: grey; …"></div>`) y no hay entradas. |

Serie corta de 508, para ver cómo baja la ETA:

| Hora (Z) | 1.ª 93 | 1.ª 70 |
|---|---|---|
| 10:59:09 | 7 min | 9 min |
| 11:00:11 | 5 min | 8 min |
| 11:01:36 | 3 min | 7 min |
| 11:02:09 | 2 min | 6 min |
| 11:02:41 | 2 min | 6 min |

### H-5. Casos no observados

- **Hora `HH:MM`:** no ha aparecido en 508 ni en 2070 hacia las 12:00, hora local.
  - Indicios indirectos: el README de `emtvlcapi` muestra `N4 (Est.del Nord) horaLlegada 22:41` en la parada 508 y también `93 (Pass. Marítim): 12:34`. Los tests de `pyemtvlc` muestran `N7 … 22:38`. Es decir, aparece en líneas nocturnas y probablemente cuando no hay estimación en tiempo real y se muestra el horario.
  - **No sabemos cómo lo pinta `QR.php`.** Lo más probable, por coherencia con `pyemtvlc` (`destino + ' - ' + hora`), es `"{destino} - HH:MM"`, pero es una suposición.
  - El campo `lineas` del geoportal para 508 es `"70,93"`: no incluye la N4.
- **Sin llegadas en una parada existente:** no observado. No sabemos si la página muestra un texto (por ejemplo, "SIN ESTIMACIONES", que es el `<error>` de `getSAE` según `pyemtvlc`, o "Temporalmente no disponible. Actualiza la estimación en unos segundos.", que es la clave de `pyemtvlc/utils/parser.py:44`) o solo la cabecera sin entradas.
- **"En parada":** solo he visto `Próximo`. No sé si existe otro marcador, por ejemplo "En parada" o "Llegando", ni si cambia con el idioma (`QR.php` no lleva parámetro de idioma y sale en castellano).
- **Errores HTTP o de servicio:** no observados. Todas las respuestas de `QR.php` fueron 200.

### H-6. Latencia

12 peticiones a `emtvalencia.es` (`time_total` de curl, desde España):

- `QR.php`: entre 81 y 212 ms (mediana aproximada, 160 ms).
- `getSAE`: 86 y 251 ms.

El timeout de 3 s de design §7 deja margen de sobra.

### H-7. Condiciones de uso

- No hay `robots.txt`: `https://www.emtvalencia.es/robots.txt` da 404.
- El dataset del Ajuntament (CC BY 4.0) publica el enlace `QR.php` como recurso de consulta en tiempo real por parada. Es la vía "oficial" de acceso que más se le parece.
- El aviso legal de EMT (`https://www.emtvalencia.es/wp/aviso-legal/`, resumido con WebFetch) prohíbe "la reproducción, transformación, distribución, comunicación pública" de sus contenidos y enlazar al sitio sin consentimiento escrito. No menciona el scraping, las API ni límites de frecuencia. Tampoco hay un documento de condiciones específico para `QR.php`.
- No necesita autenticación, cookies ni cabeceras especiales. El User-Agent identificativo que exige AC-01 se acepta.

## Impacto en la spec

**Candidato a CP-3.** design §4 dice: *"Si no los contiene o requiere otra estrategia (autenticación, scraping de HTML complejo, **bloqueo**) → CP-3"*. El formato de referencia de requirements.md («Contexto», el XML `getSAE` de `emtvlcapi`, con `minutos` y `horaLlegada`) está **bloqueado** (H-2). La alternativa (H-3) es scraping de HTML. Es un HTML simple, pero eso supone cambiar de estrategia respecto a lo que asume la spec. Por eso propongo que la persona lo confirme. Los AC y las interfaces **no cambian**.

Propuestas concretas:

1. **requirements.md, «Contexto»:** sustituir la referencia a `emtvlcapi` por:
   > "Fuente: página `QR.php?sec=est&p={stop_id}` enlazada en el campo `proximas_llegadas` del dataset `emt` del Ajuntament (HTML, UTF-8). Por cada llegada: línea (atributo `title` del icono), y texto `"{destino} - {N} min."`, `"{destino} - Próximo"` o (no confirmado) `"{destino} - HH:MM"`. El endpoint XML `getSAE` usado por `emtvlcapi` no está disponible para terceros."

2. **design §4 y §7:** default de `AVISABUS_SAE_URL_TEMPLATE` = `https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}`. Escribir en §4 las reglas mínimas del parser, para que no sean solo decisiones locales:
   - cada entrada es un bloque con `img[title]` y un `span` de texto;
   - `line` = `title`; el texto se desescapa y se le quitan los espacios de los extremos, incluido `\xa0`;
   - el texto se separa en el **último** `" - "` → `destination` y tiempo;
   - `^\d+ min\.$` → MINUTES;
   - `Próximo` (sin distinguir mayúsculas ni acentos) → MINUTES 0, que es AC-04;
   - `^\d{1,2}:\d{2}$` → CLOCK_TIME;
   - cualquier otra cosa → entrada descartada (AC-06).

   design §9 ya permite usar `selectolax` o `html.parser`; recomiendo `html.parser` de la biblioteca estándar, que no añade dependencias.

3. **Parada inexistente frente a sin llegadas (hueco en los AC).** La página de parada inexistente es un 200 sin entradas. Sin una regla, un parser ingenuo la convertiría en "sin llegadas" (AC-07). Propuesta:
   - la respuesta solo es válida si la cabecera contiene `^{stop_id} - .+`;
   - si la cabecera está vacía o no existe, `SaeUnparseableError` → `ArrivalsUnavailableError(stop_id, "unparseable")`;
   - así se conserva la lista de motivos de design §6 y el respaldo GTFS (RF-09) sigue funcionando si EMT devuelve la página sin datos.

   Si se prefiere un motivo propio (`unknown_stop`), habría que añadirlo a design §6 y AC-08.

4. **AC-04 ("marcadores identificados en E-01"):** el único marcador identificado es `Próximo`. Propongo citarlo literalmente. Cualquier texto distinto de `N min.` u `HH:MM` cae en AC-06 (descartar y registrar `sae.unparsed_entry`). Así un marcador nuevo aparece en los logs en lugar de romper el parser.

5. **AC-19 (b) y (c):** no he conseguido muestras reales de "sin llegadas" ni de `HH:MM`. Las vías previstas en el AC ("derivada documentada") siguen valiendo. Propuesta:
   - T-02 crea las derivadas a partir de `stop508_qrphp_https_20261102T110011Z.body`: quitar los bloques de llegada para "sin llegadas" y cambiar un texto a `"… - 22:41"` para `HH:MM`, con `derived_from` y `note`;
   - T-08, o una grabación nocturna con `avisabus sae record` (p. ej. 508 hacia las 23:30, cuando circula la N4), sustituye o complementa las derivadas con muestras reales.
   - La persona debe decidir si eso es aceptable o si quiere una grabación nocturna real antes de dar la feature por cerrada.

6. **AC-19 (d) "caso de error grabado":** como no he visto un error HTTP, puede valer la grabación de la parada inexistente (200 sin cabecera → `unparseable`) o un timeout grabado por `record`.

7. **docs/requirements.md RF-11** menciona `minutos` / `horaLlegada`, que son nombres del XML `getSAE`. Es un detalle de redacción y no bloquea. Propongo a la persona cambiarlo por "minutos / hora `HH:MM` / próximo".

## Riesgos

- **R-01 (agravado):** EMT ya ha cerrado un endpoint (`getSAE`) a terceros. `QR.php` lo enlaza el propio Ajuntament y está pensado para los QR de las marquesinas, pero puede cambiar sin aviso (el aviso legal, apartado 5, lo permite). Mitigación ya prevista: parser aislado, respaldo GTFS, grabaciones. Además, el parser debe fallar de forma explícita (`unparseable`) ante un HTML irreconocible en vez de devolver una lista vacía.
- **Legal:** el aviso legal de EMT prohíbe reproducir sus contenidos sin autorización. Para un TFM con caché de 20 s y un User-Agent identificable el riesgo es bajo, pero conviene que la persona valore pedir permiso por escrito a EMT o mencionarlo en la memoria. No es asesoramiento jurídico.
- **Fragilidad del HTML:** la línea solo está en un atributo `title` y el destino y el tiempo van en un solo texto. Si un destino contuviera `" - "`, separar en el último `" - "` sigue funcionando; si el tiempo no está al final, no. Un nombre de parada con `" - "` en la cabecera no afecta.
- **Casos sin muestra real** (`HH:MM`, sin llegadas, otros marcadores, textos de error de servicio): el parser se apoya en supuestos para ellos. AC-06 y la regla de la cabecera limitan el daño.
- **Máximo de 2 llegadas por línea:** para `alert_expiry` y `stop_arrivals_api`, la "siguiente llegada" de una línea solo se conoce dentro de esa ventana. No afecta a esta feature.
- **`Cache-Control: private`** y sin cabeceras de límite: no sabemos qué límite aplica EMT. La caché de 20 s y la concurrencia 4 de la spec son prudentes.

## Recomendación

Usar `https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}` con el User-Agent identificativo de AC-01 y descartar `getSAE`. Antes de implementar, hacer un **CP-3 ligero**: que la persona confirme el cambio de fuente (`emtvlcapi`/XML → `QR.php`/HTML), la regla para la parada inexistente (propuesta 3) y si acepta muestras derivadas para `HH:MM` y "sin llegadas" en AC-19 (propuesta 5). Con eso, el spec-writer actualiza «Contexto», design §4/§7 y AC-04 sin tocar interfaces. La implementación puede seguir el plan de `tasks.md` tal cual. Conviene programar una grabación nocturna corta (508 hacia las 23:30) para conseguir `HH:MM` real.

### Índice de muestras (`progress/explore_sae_samples/`)

Cada petición tiene `.body` (cuerpo bruto), `.headers.txt` (cabeceras de respuesta) y `.meta.txt` (URL, código, `content_type`, tiempos, hora UTC).

- `stop508_qrphp_http_20261102T105909Z`: minutos, por HTTP.
- `stop508_qrphp_https_20261102T110011Z`: minutos, por HTTPS.
- `stop508_qrphp_https_series_…110136Z / …110209Z / …110241Z`: serie de minutos.
- `stop2070_qrphp_20261102T105959Z`: minutos + **Próximo**.
- `stop2070_qrphp_https_series_…110138Z / …110211Z / …110243Z`: minutos; la 95 ya ha pasado.
- `stop99999_qrphp_nonexistent_20261102T110003Z`: parada inexistente.
- `stop2070_getsae_20261102T105917Z`: `getSAE` en www, error "no disponible desde el plano".
- `stop508_geoportal_getsae_20261102T110120Z`: `getSAE` en geoportal.emtvalencia.es, el mismo error.
- `geoportal_226_stops_508_2070.json`, `opendata_emt_package_metadata.json`: origen de la URL y licencia.
- `extract_qrphp.py`: extractor de exploración (solo biblioteca estándar).

---
**Resumen para el orquestador:** el SAE accesible es `https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}`, la URL del dataset del Ajuntament. Devuelve HTML UTF-8 con línea (`img[title]`) y `"destino - N min."` o `"destino - Próximo"`, en 80–250 ms. El endpoint XML de `emtvlcapi` (`getSAE`) está cerrado a terceros. He observado minutos, "Próximo", el paso de un bus y la parada inexistente (200 con cabecera vacía). No he observado `HH:MM` ni "sin llegadas". Los AC y las interfaces sirven, pero el cambio de fuente (bloqueo y HTML) es una condición explícita de CP-3 en design §4 y hay un hueco con la parada inexistente: **requiere CP-3 ligero** antes de implementar (propuestas 1–5).
