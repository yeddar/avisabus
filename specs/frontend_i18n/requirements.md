# Idiomas y base de accesibilidad del frontend — requirements

> Feature: `frontend_i18n` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-31, RF-32, RNF-03, RNF-14, RNF-15 · Casos de uso: CU-06 · Depende de: project_scaffold

## Contexto

La interfaz debe estar en castellano y valenciano (D8, RF-31). Los nombres de paradas y líneas
se muestran siempre tal como vienen en el GTFS, en valenciano (RF-32). Todas las vistas
posteriores (pasajero y conductor) se construyen sobre la base que crea esta feature:
configuración de i18n, selector de idioma, estructura de página accesible (layout, salto al
contenido, foco, título del documento, anuncios para lectores de pantalla) y pie con la atribución
de las fuentes de datos (RNF-14).

`project_scaffold` dejó un `h1` con texto literal en `HomePage` y la regla
`i18next/no-literal-string` sin activar; esta feature los sustituye.

## Alcance

- i18next + react-i18next con recursos `es` y `ca-valencia` empaquetados (sin carga diferida).
- Detección del idioma inicial, persistencia de la elección y atributo `lang` del documento.
- Selector de idioma accesible en la cabecera de todas las vistas.
- Regla de lint que prohíbe textos literales en JSX y test de paridad de claves entre idiomas.
- Utilidades de formato dependientes del idioma (horas, minutos, distancias).
- Layout accesible: enlace "saltar al contenido", `header`/`main`/`footer`, foco y título por
  vista, región de anuncios, estilos de foco visible y tamaño mínimo de objetivos táctiles.
- Pie con atribución de fuentes de datos.
- `HomePage` traducida.

## Fuera de alcance

- Traducción del manifiesto PWA (el manifiesto admite un único idioma; se mantiene en castellano).
- Vistas de pasajero y conductor (features siguientes).
- Traducción de nombres de paradas, líneas o destinos (RF-32: nunca se traducen).

## Criterios de aceptación

### Idioma

- **frontend_i18n.AC-01** — CUANDO alguien abre la aplicación por primera vez y el primer idioma
  preferido del navegador empieza por `ca` (`ca`, `ca-ES`, `ca-ES-valencia`…), LA APLICACIÓN
  DEBERÁ mostrarse en valenciano; en cualquier otro caso, en castellano.
  *Verificación:* unit (detector con `navigator.languages` simulado)
- **frontend_i18n.AC-02** — CUANDO la persona elige un idioma en el selector, LA APLICACIÓN DEBERÁ
  cambiar todos los textos de la interfaz sin recargar la página y recordar la elección en el
  dispositivo, de modo que en visitas posteriores prevalezca sobre el idioma del navegador.
  *Verificación:* unit + e2e
- **frontend_i18n.AC-03** — EL DOCUMENTO DEBERÁ tener `lang="es"` en castellano y
  `lang="ca-ES-valencia"` en valenciano, actualizado al cambiar de idioma.
  *Verificación:* unit
- **frontend_i18n.AC-04** — EL SELECTOR DE IDIOMA DEBERÁ estar en la cabecera de todas las vistas,
  tener una etiqueta accesible ("Idioma" / "Llengua"), mostrar cada opción con su nombre en su
  propio idioma ("Castellano", "Valencià") y marcar cada opción con su atributo `lang`.
  *Verificación:* unit + e2e (axe)
- **frontend_i18n.AC-05** — SI falta una clave en el idioma activo, ENTONCES LA APLICACIÓN DEBERÁ
  mostrar el texto en castellano y, en desarrollo, registrar un aviso en la consola.
  *Verificación:* unit
- **frontend_i18n.AC-06** — LOS NOMBRES de paradas, líneas y destinos recibidos de la API
  DEBERÁN mostrarse sin traducir y marcados con `lang="ca-ES-valencia"` cuando la interfaz esté en
  castellano, para que los lectores de pantalla los pronuncien correctamente.
  *Verificación:* unit (componente `GtfsText`)

### Calidad de las traducciones (RNF-15)

- **frontend_i18n.AC-07** — SI un componente contiene texto literal en JSX o en los atributos
  `aria-label`, `alt`, `title`, `placeholder` o `aria-description`, ENTONCES `npm run lint`
  DEBERÁ fallar (los ficheros de test quedan excluidos).
  *Verificación:* unit (ESLint sobre fichero de ejemplo inválido)
- **frontend_i18n.AC-08** — LOS FICHEROS `es` y `ca-valencia` DEBERÁN tener exactamente el mismo
  conjunto de claves y ningún valor vacío; SI no es así, ENTONCES `npm run test` DEBERÁ fallar
  indicando las claves sobrantes o ausentes.
  *Verificación:* unit
- **frontend_i18n.AC-09** — LAS UTILIDADES DE FORMATO DEBERÁN producir, según el idioma: minutos
  con plural correcto ("1 min" / "5 min"; texto accesible "1 minuto"/"5 minutos" y "1 minut"/"5
  minuts"), horas en formato 24 h (`22:41`) en la zona `Europe/Madrid`, y distancias en metros
  por debajo de 1 km y en kilómetros con un decimal a partir de 1 km.
  *Verificación:* unit

### Base de accesibilidad (RNF-03)

- **frontend_i18n.AC-10** — CADA VISTA DEBERÁ tener los landmarks `banner` (cabecera), `main` y
  `contentinfo` (pie), un único `h1`, y como primer elemento enfocable un enlace "Saltar al
  contenido" que lleva el foco a `main`.
  *Verificación:* unit + e2e
- **frontend_i18n.AC-11** — CUANDO se navega a una vista nueva dentro de la aplicación, EL
  SISTEMA DEBERÁ actualizar `document.title` con el formato `<título de la vista> · AvisaBus` y
  mover el foco al `h1` de la vista.
  *Verificación:* unit (router en memoria)
- **frontend_i18n.AC-12** — LA APLICACIÓN DEBERÁ ofrecer un mecanismo único de anuncios para
  lectores de pantalla (región `aria-live` educada y otra asertiva) que las vistas usan mediante un
  hook, sin crear regiones propias.
  *Verificación:* unit
- **frontend_i18n.AC-13** — TODOS LOS ELEMENTOS INTERACTIVOS DEBERÁN mostrar un indicador de foco
  visible (contorno ≥ 2 px con contraste ≥ 3:1) y los componentes base de botón y enlace
  DEBERÁN tener un área táctil mínima de 44 × 44 px.
  *Verificación:* unit (estilos calculados de los componentes base) + e2e (axe)

### Atribución y portada

- **frontend_i18n.AC-14** — EL PIE de todas las vistas DEBERÁ mostrar, traducida, la atribución de
  datos: "Datos: EMT València (GTFS y tiempos de llegada) · Ajuntament de València".
  *Verificación:* unit
- **frontend_i18n.AC-15** — CUANDO se abre `/`, LA APLICACIÓN DEBERÁ mostrar en el idioma activo
  el título de la aplicación y una explicación breve de que se accede escaneando el QR de la
  parada, sin textos literales.
  *Verificación:* unit + e2e (axe en los dos idiomas)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-31 Castellano y valenciano con selector y persistencia | AC-01, AC-02, AC-03, AC-04, AC-05 |
| RF-32 Nombres del GTFS sin traducir | AC-06 |
| RNF-15 Internacionalización (sin literales, ambos idiomas) | AC-07, AC-08, AC-09 |
| RNF-03 Accesibilidad | AC-04, AC-06, AC-10, AC-11, AC-12, AC-13, AC-15 |
| RNF-14 Atribución | AC-14 |
| CU-06 Cambiar idioma | AC-01, AC-02 |
