# Guía visual — AvisaBus

> Estado: **APROBADO** (v1.0 · 2026-11-03, PR #7).
> Deriva de `docs/requirements.md` (RNF-03, RNF-05, RNF-14, RNF-15) y del boceto revisado por la
> persona el 2026-11-03.

## 1. Propósito y alcance

Esta guía fija el **aspecto** de la interfaz para que todas las features de frontend se vean como
una sola aplicación. No define comportamiento: el comportamiento lo fijan las specs.

- Si una spec y esta guía chocan en **comportamiento** (qué se muestra, cuándo, con qué texto
  accesible), manda la spec.
- Si chocan en **aspecto** (tipografía, color, tamaños, disposición), manda esta guía; la
  discrepancia se anota en `progress/` como cualquier otra contradicción (AGENTS.md §2).
- Lo que esta guía no fija es decisión local del implementer (márgenes exactos, sombras, etc.),
  siempre respetando los mínimos de accesibilidad de §2.

**Boceto de referencia:** lienzo de diseño "AvisaBus · bocetos" en claude.ai
(<https://claude.ai/artifact/XdyYqwtc2KyhN24pt5hNFT>) con tres pantallas de 390 × 1040 px:
"Parada · tiempo real", "Mapa · posición estimada" y "Parada · sin tiempo real (valencià)". El
lienzo es privado de la persona; los agentes trabajan **con esta guía**, que recoge todo lo que
necesitan de él. Los datos del boceto (paradas, minutos, ocupaciones) son ilustrativos.

## 2. Principios

1. **Accesibilidad primero.** WCAG 2.1 AA como mínimo; el público incluye personas con baja visión,
   con lector de pantalla y con poca soltura tecnológica.
2. **Nada solo con color.** Ocupación, origen de los datos y estados llevan siempre texto (y, si
   ayuda, icono). El color refuerza, nunca informa por sí solo.
3. **Lo importante, grande.** El tiempo de llegada y el destino son lo primero que se lee.
4. **Objetivos táctiles generosos.** Mínimo 44 × 44 px en toda la aplicación; **48 px de alto** en
   las acciones de una llegada ("Ver en el mapa", "Solicitar").
5. **Móvil primero.** Diseño para 360–430 px de ancho; en tablet el contenido se centra con un ancho
   máximo de 640 px. Sin desplazamiento horizontal con zoom del 200 % ni a 320 px de ancho.
6. **Sin peticiones a terceros** para recursos de la interfaz (tipografías, iconos): todo se sirve
   desde el propio dominio. Las únicas excepciones son las teselas del mapa (ADR-005, RNF-14).

## 3. Tipografía

**Atkinson Hyperlegible** (pesos 400 y 700), diseñada por el Braille Institute para baja visión.
Se **autoaloja** con el paquete `@fontsource/atkinson-hyperlegible` (sin Google Fonts: privacidad y
funcionamiento de la PWA sin conexión). Respaldo: `system-ui, sans-serif`. Tamaños en `rem`
(base 16 px) para que respeten el tamaño de letra del sistema.

| Uso | Tamaño (px) | Peso | Notas |
|---|---|---|---|
| `h1` de vista (nombre de parada) | 28 · interlineado 1,15 | 700 | En la vista de mapa, 22 |
| `h2` de sección principal ("Próximas llegadas") | 22 | 700 | |
| Rótulo de sección secundaria ("Líneas") | 15 | 700 | Mayúsculas, espaciado 0,04 em, color `text-muted` |
| Tiempo de llegada (cifra) | 30 · interlineado 1 | 700 | Unidad "min" a 18 px |
| Tiempo "Llegando" / hora `HH:MM` | 24 | 700 | |
| Destino | 18 · interlineado 1,2 | 700 | Precedido de "hacia" a 14 px `text-muted` |
| Número de línea en tarjeta | 22 | 700 | En la lista de líneas, 20 |
| Texto normal, botones | 16 | 400 / 700 | Botones en 700 |
| Texto secundario ("Actualizado a las…", "Parada 508") | 14–16 | 400 | `text-muted` |
| Ocupación | 15 | 700 + 400 | Nivel en negrita, asientos en normal |
| Pie, etiquetas del mapa, "programado" | 13 | 400 / 700 | **Mínimo absoluto: 12 px** (solo atribución dentro del mapa) |

## 4. Color

Tokens para el tema de Tailwind (`@theme` en `src/index.css`). Contrastes calculados con la
fórmula WCAG 2.x.

| Token | Valor | Uso | Contraste |
|---|---|---|---|
| `text` | `#14171F` | Texto principal | 17,9:1 sobre blanco |
| `text-muted` | `#4B5563` | Texto secundario | 7,6:1 sobre blanco |
| `surface` | `#FFFFFF` | Fondo | — |
| `accent` | `#0B3D91` | Marca, enlaces, botones, foco | 10,0:1 sobre blanco |
| `accent-hover` | `#072A66` | Hover de enlaces y botones | — |
| `accent-surface` | `#F4F7FD` | Fondo de avisos y del resumen del mapa | `accent` 9,4:1 · `text` 16,7:1 |
| `border` | `#D5DAE2` | Borde de tarjetas (decorativo) | — |
| `divider` | `#E3E6EC` | Separador de cabecera y pie | — |
| `control-border` | `#8A93A3` | Borde de controles (selector, zoom) | 3,1:1 (≥ 3:1, componente) |

**Ocupación** (fondo / texto e icono):

| Nivel | Fondo | Texto | Contraste | Texto (es / ca-valencia) | Icono |
|---|---|---|---|---|---|
| `FREE` | `#E6F4EA` | `#1E5E2E` | 6,9:1 | Poco ocupado / Poc ocupat | 1 silueta rellena + 2 en contorno |
| `MEDIUM` | `#FFF4D6` | `#7A4A00` | 6,8:1 | Ocupación media / Ocupació mitjana | 2 rellenas + 1 en contorno |
| `FULL` | `#FDE7E5` | `#9B1C14` | 6,9:1 | Lleno / Ple | 3 rellenas |
| `null` | `#F1F3F6` | `#4B5563` | 6,8:1 | Ocupación no disponible / Ocupació no disponible | 3 en contorno |

**Color de línea:** se usa el `line_color` / `line_text_color` del GTFS pasado por
`accessibleLineColors()` (`passenger_stop_view.AC-11`, contraste ≥ 4,5:1). El rojo de EMT
(`#FE0000`, 4,0:1 con blanco) queda en torno a `#E40000` (4,9:1). El `#C40000` del boceto es solo
ilustrativo; no se fija ningún color de línea en el código.

**Modo oscuro:** fuera de alcance del MVP.

## 5. Componentes

### 5.1 Estructura común

- **Cabecera:** logotipo (icono de autobús 28 px + "AvisaBus" 20 px en `accent`) a la izquierda;
  selector de idioma con etiqueta visible "Idioma" / "Llengua" a la derecha (alto 44 px, borde
  `control-border`, radio 8 px). Separador inferior `divider`. Relleno 12 × 16 px.
- **Contenido:** relleno 20 px arriba, 16 px a los lados; secciones separadas 20 px.
- **Pie:** 13 px, `text-muted`, separador superior `divider`, con la atribución de datos de
  `frontend_i18n` (y la del mapa en la vista de mapa).
- **Foco:** contorno de 3 px `accent` con separación de 2 px (`frontend_i18n` design §5).

### 5.2 Distintivo de línea

Rectángulo con radio 8 px, cifra en 700 centrada. En la lista de líneas: alto 36 px, ancho mínimo
48 px, 20 px. En la tarjeta de llegada: alto 40 px, ancho mínimo 52 px, 22 px.

### 5.3 Tarjeta de llegada

Elemento de lista con borde `border` de 1 px, radio 14 px, relleno 14 px y separación de 12 px
entre tarjetas y entre filas internas:

```
┌──────────────────────────────────────────────┐
│ [93]  hacia                         4 min    │  fila 1: distintivo · destino (texto del SAE) · tiempo
│       Pass. Marítim                          │
│ ┌──────────────────────────────────────────┐ │
│ │ 👤👤○  Ocupación media · hay asientos     │ │  fila 2: insignia de ocupación (ancho completo)
│ └──────────────────────────────────────────┘ │
│ [ 🗺 Ver en el mapa ]  [ ✋ Solicitar      ]  │  fila 3: acciones a partes iguales
└──────────────────────────────────────────────┘
```

- El tiempo con horario programado lleva debajo "programado" / "programat" a 13 px `text-muted`.
- Las llegadas con `in_network = false` omiten las filas 2 y 3 (`passenger_stop_view.AC-08`);
  con `occupancy = null` se muestra la insignia "Ocupación no disponible"; una acción que no aplica
  (p. ej. sin sentido resuelto, `passenger_map_view.AC-01`) no se pinta.
- La fila 3 la completan dos features: "Ver en el mapa" (`passenger_map_view`, bloque 2) y
  "Solicitar" (`passenger_alert_ui`, bloque 3). Mientras solo exista una, ocupa todo el ancho.

### 5.4 Insignia de ocupación

Caja de radio 8 px, relleno 8 × 10 px, colores de §4, icono SVG de tres siluetas (40 × 18 px,
`aria-hidden`) y texto "**Nivel** · asientos" a 15 px.

### 5.5 Botones

| Tipo | Aspecto | Uso |
|---|---|---|
| Principal | Fondo `accent`, texto blanco 700, borde 2 px `accent`, radio 10 px | "Solicitar" (bloque 3) |
| Secundario | Fondo blanco, texto `accent` 700, borde 2 px `accent`, radio 10 px | "Ver en el mapa", "Actualizar", "Reintentar" |

Icono a la izquierda (18 px, trazo 2–2,2, `aria-hidden`) y texto **siempre visible**: no hay
botones solo con icono salvo el zoom del mapa, que lleva `aria-label`.

### 5.6 Avisos de estado

Aviso de horario programado, sin conexión y errores: caja con fondo `accent-surface`, borde 2 px
`accent`, radio 12 px, relleno 12 px, icono informativo y texto de 16 px con la primera frase en
negrita ("**Sin datos en tiempo real.** Se muestra el horario programado.").

### 5.7 Vista de mapa

De arriba abajo:

1. Enlace "Volver a la parada" (con flecha, 44 px de alto).
2. `h1` "Línea {línea} hacia {destino}" (22 px).
3. **Resumen** "Dónde está el autobús": caja `accent-surface` con borde 2 px `accent`, radio 14 px,
   insignia "Posición estimada" (o "Posición según horario") y el texto de
   `passenger_map_view.AC-04` con distancia, paradas y tiempo en negrita.
4. **Mapa:** 360 px de alto, radio 14 px, borde `control-border`. Trazado con el color accesible de
   la línea; paradas como círculos blancos con borde; parada del pasajero destacada con la
   etiqueta "Tu parada"; autobús con icono orientado y etiqueta "Estimada" (o "Según horario")
   sobre fondo `text` y letra blanca de 13 px. Botones de zoom "+"/"−" de 44 × 44 px arriba a la
   derecha. Atribución de OpenStreetMap abajo a la derecha (12 px, fondo blanco al 92 %).
5. **Sin leyenda:** las etiquetas "Tu parada" y "Estimada" sobre el propio mapa, más el resumen en
   texto, cubren lo que diría una leyenda (decisión de la persona, 2026-11-03).

## 6. Iconos

SVG propios en línea, de trazo (2–2,2 px, extremos redondeados), `aria-hidden="true"` y
`currentColor`. Sin fuentes de iconos ni librerías externas. Conjunto mínimo: autobús (logotipo),
actualizar, mapa, mano (Solicitar), información, siluetas de ocupación, flecha atrás.

## 7. Textos de interfaz

- **Terminología de la acción del pasajero:** en la interfaz se habla de **solicitar parada**, no
  de "avisar": botón "Solicitar" / "Sol·licita"; estado "Parada solicitada"; acción "Cancelar
  solicitud". En docs y código sigue siendo "aviso" / `Alert` (glosario de `docs/conventions.md`).
  El nombre accesible del botón incluye línea y destino: "Solicitar parada a la línea 93 hacia
  Passeig Marítim - Hospital Malva-rosa".
- **Destino de una llegada:** regla en `passenger_stop_view.AC-05`: en pantalla, el texto del SAE
  (lo que el pasajero ve en el letrero del autobús); en el texto accesible, el headsign del GTFS
  (más legible al oírlo).
- Nombres de paradas, líneas y destinos tal como vienen del GTFS/SAE, marcados con
  `lang="ca-ES-valencia"` (`frontend_i18n.AC-06`).

## Historial

| Versión | Fecha | Cambio | Motivo |
|---|---|---|---|
| 1.0 | 2026-11-03 | Versión inicial a partir del boceto | Revisión visual de la persona tras el bloque 1. Aprobada por la persona (PR #7). |
