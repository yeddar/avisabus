# Visión del producto — AvisaBus (nombre provisional)

> Estado: **APROBADO** (v1.0 · 2026-10-31). Proyecto académico (TFM).
> Este documento es la fuente de verdad del *porqué* del sistema. Los requisitos
> (`docs/requirements.md`) y los casos de uso (`docs/use_cases.md`) derivan de él.

## 1. Contexto

En el transporte urbano en autobús, el pasajero que espera en una parada solo puede indicar
que quiere subir haciendo señas cuando el autobús ya llega. El conductor desconoce con
antelación cuántas personas esperan en cada parada, si alguna necesita rampa o más tiempo
para subir, y si caben en el vehículo. El pasajero, a su vez, solo dispone en el mejor de los
casos de un tiempo estimado de llegada, pero no de la ubicación del autobús ni de su nivel de
ocupación.

Ámbito geográfico y de datos: **EMT València**.

## 2. Problemas

| ID | Problema | Afectados |
|---|---|---|
| P1 | El pasajero no conoce la ubicación del autobús en tiempo real; como mucho, una estimación de tiempo. | Pasajeros |
| P2 | El pasajero no sabe si el autobús viene saturado ni si habrá asientos libres. | Pasajeros, especialmente PMR |
| P3 | El pasajero no tiene garantía de que el conductor sepa que le espera; depende de hacer señas a tiempo. | Pasajeros |
| P4 | El conductor no sabe con antelación si en una parada hay pasajeros que necesitan rampa, más tiempo o asiento. | PMR, conductor |
| P5 | El conductor no sabe cuánta gente espera en las próximas paradas, ni si cabrá o necesitará refuerzo. | Conductor |

## 3. Actores

| Actor | Descripción |
|---|---|
| Pasajero | Persona que espera o planea coger un autobús. Anónimo. Consulta información y avisa de que espera una línea. |
| Pasajero con necesidades de accesibilidad (PMR) | Especialización de Pasajero que indica necesidades: rampa, tiempo extra de subida, asiento. |
| Conductor | Consulta la demanda de sus próximas paradas. No introduce datos de pasajeros. Accede con código. |
| Administrador | Importa/actualiza el feed GTFS, genera QR de paradas y códigos de conductor (vía CLI). |
| SAE de EMT (externo) | Proporciona tiempos de llegada en tiempo real por parada. |
| Sensor de ocupación (externo, simulado) | Proporciona plazas ocupadas/libres por vehículo. |
| GPS del dispositivo del conductor (externo, real o simulado) | Proporciona la posición del conductor para determinar sus próximas paradas. |

## 4. Solución

Aplicación web React (PWA) a la que el pasajero accede **escaneando el QR de la parada**
(el QR identifica la parada). Backend en Python que centraliza datos y distribuye
actualizaciones en tiempo real.

- **Pasajero**: tiempos de llegada en tiempo real, posición estimada del autobús en mapa,
  nivel de ocupación, aviso de espera con necesidades de accesibilidad y confirmación de
  recepción.
- **Conductor**: próximas paradas con número de personas esperando, avisos de accesibilidad
  destacados y alerta de capacidad.

## 5. Fuentes de datos (decisión D1)

| Dato | Fuente | Naturaleza |
|---|---|---|
| Red: líneas, paradas, horarios, trazados | GTFS estático EMT València | Real (feed oficial, renovación ~mensual) |
| Tiempos de llegada | SAE de EMT (endpoint "próximas llegadas" por parada) | Real, tiempo real. API no documentada oficialmente → caché y respaldo GTFS |
| Posición del autobús | Estimada: ETA SAE + tiempos de `stop_times` interpolados sobre `shapes` | Estimada (se indica en la UI) |
| Ocupación | Sensor contador simulado | Simulada |
| Posición del conductor | GPS del dispositivo (real) o simulador (demo) | Real / simulada |

Todas las fuentes se acceden mediante **puertos y adaptadores** intercambiables; los tests
usan grabaciones (replay) y fixtures, nunca la red.

### Hallazgos sobre el GTFS (feed 23-10-2026)

- `stop_id` = `stop_code`, numérico; 1117 paradas. Coinciden con los códigos de parada del
  SAE (verificado con la parada 2070: misma dirección y coordenadas a ~35 m; el **nombre**
  difiere → los nombres se toman del GTFS).
- Una línea comercial (`route_short_name`) puede tener varios `route_id` (24, 62, 73, 98, C2, C3).
- Vigencia del feed: 2026-10-16 → 2026-11-22. Hay que poder reimportarlo.
- `wheelchair_boarding = 0` en todas las paradas: no hay información de accesibilidad de paradas.
- El feed no incluye líneas nocturnas (N*), que el SAE sí puede devolver.
- `trips.txt` **no incluye `direction_id`** (columnas: `route_id, service_id, trip_id,
  trip_headsign, trip_short_name, shape_id`) → el sentido se deriva al importar a partir de los
  extremos y la orientación de cada trazado (`specs/gtfs_import/design.md` §4.3).
- `shape_dist_traveled` está presente en `stop_times` y `shapes`, en metros.
- Nombres en valenciano (`feed_lang = ca`).

## 6. Decisiones

| ID | Decisión |
|---|---|
| D1 | Datos EMT reales (GTFS + ETA SAE) + posición estimada, tras adaptadores. |
| D2 | Ocupación mediante sensor contador simulado tras interfaz. |
| D3 | Pasajero anónimo; perfil de accesibilidad opcional guardado en el dispositivo. |
| D4 | Aviso solo desde el QR de la parada; uno por dispositivo y línea; caduca cuando el autobús pasa por la parada o llega a la siguiente. |
| D5 | "Pedir refuerzos" = alerta en la vista del conductor. Centro de control: trabajo futuro. |
| D6 | Proyecto académico (TFM): RNF realistas, sin exigencias de producción. |
| D7 | El conductor accede con código, elige línea y sentido; la posición de su dispositivo determina sus próximas paradas. |
| D8 | Interfaz bilingüe castellano / valenciano. Los nombres de paradas y líneas se muestran siempre en valenciano (tal como vienen en el GTFS). |
| D9 | Caducidad máxima de seguridad de un aviso: 30 minutos. |
| D10 | La confirmación al pasajero es automática al entregarse el aviso a la vista del conductor (el conductor no pulsa nada). |
| D11 | El Administrador opera exclusivamente mediante CLI en el MVP (sin panel web). |
| D12 | La detección de paso del autobús por una parada (caducidad de avisos) usa solo datos del SAE. El GPS del conductor se usa únicamente para determinar sus próximas paradas. |

Limitaciones conocidas: ver `docs/use_cases.md` § Limitaciones conocidas (LIM-01 a LIM-04).

## 7. Objetivos

| ID | Objetivo | Indicador de éxito |
|---|---|---|
| OBJ-01 | Informar al pasajero del tiempo de llegada en tiempo real de las líneas de su parada, sin instalar nada. | Escaneo QR → tiempos visibles ≤ 3 s; refresco ≤ 30 s. |
| OBJ-02 | Mostrar en un mapa la posición estimada del próximo autobús sobre su recorrido real. | Autobús dibujado sobre el trazado GTFS, actualizado al ritmo del ETA. |
| OBJ-03 | Informar del nivel de ocupación del autobús que se aproxima. | Tres niveles (libre / medio / lleno) e indicación de asientos libres. |
| OBJ-04 | Permitir avisar de que se espera una línea, con necesidades de accesibilidad, y confirmar la recepción. | Aviso en ≤ 2 interacciones; confirmación ≤ 5 s. |
| OBJ-05 | Dar al conductor visión anticipada de la demanda en sus próximas paradas, destacando accesibilidad. | ≥ 3 próximas paradas con nº de personas y avisos de rampa/tiempo extra/asiento. |
| OBJ-06 | Alertar al conductor cuando la demanda prevista supere la capacidad disponible. | Alerta visual cuando Σ personas esperando > plazas libres. |
| OBJ-07 | Garantizar una interfaz accesible. | WCAG 2.1 AA (axe/Lighthouse + revisión manual). |
| OBJ-08 | Desacoplar las fuentes de datos para sustituir datos estimados/simulados por reales. | Cambiar el adaptador no requiere modificar dominio ni UI. |
| OBJ-09 | Aplicar y evaluar Spec Driven Development con agentes IA. | Toda funcionalidad deriva de una spec, con trazabilidad requisito → tarea → test. |

## 8. Fuera de alcance (MVP)

- Centro de control / despacho de refuerzos.
- Registro de usuarios y cuentas.
- Aplicación móvil nativa.
- Integración con GPS/AVL real de la flota o GTFS-Realtime (preparado vía adaptadores).
- Planificación de rutas origen–destino.
