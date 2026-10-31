# Requisitos del sistema — AvisaBus

> Estado: **APROBADO** (v1.0 · 2026-10-31). Deriva de `docs/vision.md`.
> Los requisitos aquí son **globales**. Cada feature en `specs/<feature>/requirements.md`
> los refina en criterios de aceptación EARS y referencia sus IDs (trazabilidad).
>
> Prioridad (MoSCoW): **M** = Must (MVP), **S** = Should, **C** = Could.

## 1. Requisitos funcionales

### 1.1 Datos de red (GTFS)

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-01 | El sistema deberá importar el feed GTFS de EMT València (agency, routes, stops, trips, stop_times, shapes, calendar, calendar_dates) a su base de datos. | M | OBJ-01, OBJ-02 |
| RF-02 | El sistema deberá permitir reimportar el feed sin interrumpir el servicio y avisar (log y CLI) cuando falten ≤ 7 días para `feed_end_date` o el feed haya caducado. | S | OBJ-01 |
| RF-03 | El sistema deberá agrupar los `route_id` en líneas comerciales por `route_short_name`. | M | OBJ-01 |
| RF-04 | El sistema deberá determinar los servicios activos en una fecha según `calendar` y `calendar_dates`. | M | OBJ-01, OBJ-02 |

### 1.2 Paradas y QR

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-05 | La CLI de administración deberá generar un código QR por parada que codifique la URL pública de la parada con un token firmado (HMAC) que la identifica. | M | OBJ-01, OBJ-04 |
| RF-06 | Al abrir la URL de una parada con token válido, el sistema deberá mostrar el nombre de la parada y las líneas que la sirven. | M | OBJ-01 |

### 1.3 Tiempos de llegada

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-07 | El sistema deberá obtener los tiempos de llegada en tiempo real de una parada desde el SAE de EMT. | M | OBJ-01 |
| RF-08 | El sistema deberá cachear las respuestas del SAE por parada con TTL configurable (20 s por defecto). | M | OBJ-01 |
| RF-09 | Si el SAE falla o no responde, el sistema deberá mostrar el horario teórico GTFS indicando "horario programado". | M | OBJ-01 |
| RF-10 | La vista de parada deberá refrescarse automáticamente cada ≤ 30 s sin recargar la página. | M | OBJ-01 |
| RF-11 | El sistema deberá normalizar las respuestas del SAE (`minutos` / `horaLlegada`) y mostrar también líneas ausentes del GTFS (p. ej. nocturnas), sin mapa. | M | OBJ-01 |

### 1.4 Posición estimada

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-12 | El sistema deberá estimar la posición del próximo autobús de cada línea sobre su trazado (`shapes`) a partir del ETA y de los tiempos de recorrido programados (`stop_times`). | M | OBJ-02 |
| RF-13 | El sistema deberá mostrar un mapa con la parada, el trazado de la línea y el autobús, etiquetado como "posición estimada". | M | OBJ-02 |

### 1.5 Ocupación

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-14 | El sistema deberá obtener la ocupación de cada vehículo (capacidad, ocupados, asientos libres) a través de una interfaz de sensor, con una implementación simulada. | M | OBJ-03, OBJ-08 |
| RF-15 | El sistema deberá mostrar el nivel de ocupación (libre / medio / lleno, umbrales configurables) y si hay asientos libres, sin depender solo del color. | M | OBJ-03, OBJ-07 |

### 1.6 Avisos de espera

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-16 | El pasajero deberá poder crear un aviso "espero la línea X (destino Y)" desde la vista de la parada. | M | OBJ-04 |
| RF-17 | El pasajero deberá poder indicar opcionalmente necesidades: rampa, tiempo extra de subida, asiento. | M | OBJ-04 |
| RF-18 | El sistema deberá guardar el perfil de accesibilidad en el dispositivo y precargarlo en avisos posteriores. | S | OBJ-04 |
| RF-19 | El sistema deberá admitir un único aviso activo por dispositivo, parada y línea, identificando el dispositivo con un identificador anónimo aleatorio. | M | OBJ-04 |
| RF-20 | El sistema deberá asignar el aviso al próximo autobús de esa línea y sentido que llegará a la parada. | M | OBJ-04, OBJ-05 |
| RF-21 | El aviso deberá caducar cuando el autobús asignado pase por la parada, cuando llegue a la parada siguiente o, en todo caso, a los 30 minutos de su creación. | M | OBJ-04 |
| RF-22 | El pasajero deberá poder cancelar su aviso activo. | M | OBJ-04 |
| RF-23 | El sistema deberá confirmar automáticamente al pasajero la entrega del aviso a la vista del conductor del servicio; si no hay conductor conectado, deberá indicar "aviso registrado, sin conductor conectado". | M | OBJ-04 |

### 1.7 Conductor

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-24 | El conductor deberá acceder a su vista mediante un código de acceso. | M | OBJ-05 |
| RF-25 | El conductor deberá seleccionar línea y sentido al iniciar el turno. | M | OBJ-05 |
| RF-26 | El sistema deberá determinar las próximas paradas del conductor a partir de la posición GPS de su dispositivo (real o simulada). | M | OBJ-05 |
| RF-27 | La vista del conductor deberá mostrar al menos las 3 próximas paradas con el número de personas esperando y los avisos de accesibilidad destacados. | M | OBJ-05 |
| RF-28 | La vista del conductor deberá actualizarse en tiempo real (push) al crearse, cancelarse o caducar un aviso. | M | OBJ-05 |
| RF-29 | El sistema deberá mostrar una alerta de capacidad cuando la suma de personas esperando en las próximas paradas supere las plazas libres. | M | OBJ-06 |
| RF-30 | El conductor deberá poder finalizar el turno, eliminando su sesión y su posición. | M | OBJ-05 |

### 1.8 Idioma

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-31 | Las interfaces de pasajero y conductor deberán estar disponibles en castellano y valenciano, con selector de idioma; el idioma inicial se toma del navegador y la elección se recuerda en el dispositivo. | M | OBJ-07 |
| RF-32 | Los nombres de paradas y líneas se mostrarán siempre tal como vienen en el GTFS (valenciano), independientemente del idioma de la interfaz. | M | OBJ-07 |

### 1.9 Administración (CLI)

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-33 | La CLI deberá permitir crear, listar y revocar códigos de acceso de conductor. | M | OBJ-05 |

### 1.10 Demo y pruebas

| ID | Requisito | Prio | Objetivo |
|---|---|---|---|
| RF-34 | El sistema deberá incluir un simulador de GPS de conductor que recorra el trazado de una línea a velocidad configurable. | M | OBJ-05, OBJ-08 |
| RF-35 | El sistema deberá permitir grabar respuestas reales del SAE y reproducirlas en lugar de la fuente en vivo. | M | OBJ-08, OBJ-09 |

## 2. Requisitos no funcionales

| ID | Categoría | Requisito | Verificación |
|---|---|---|---|
| RNF-01 | Rendimiento | Escaneo QR → tiempos visibles ≤ 3 s en red 4G; API p95 ≤ 500 ms con caché caliente. | Lighthouse (throttling 4G), test de carga |
| RNF-02 | Tiempo real | Aviso visible en la vista del conductor ≤ 2 s; confirmación al pasajero ≤ 5 s. | Test de integración con reloj medido |
| RNF-03 | Accesibilidad | WCAG 2.1 AA: lectores de pantalla (VoiceOver/TalkBack), zonas táctiles ≥ 44 px, contraste AA, información no transmitida solo por color, respeto a `prefers-reduced-motion`. | axe-core en CI + checklist manual |
| RNF-04 | Usabilidad | Sin registro ni instalación; crear un aviso en ≤ 2 interacciones desde la vista de parada. | Test E2E |
| RNF-05 | Compatibilidad | Safari iOS y Chrome Android (2 últimas versiones); vista de conductor usable en tablet horizontal. | Playwright (perfiles móvil/tablet) |
| RNF-06 | Privacidad | Sin datos personales; necesidades de accesibilidad asociadas solo al aviso y borradas al caducar; posición del conductor no persistida tras el turno. | Tests de borrado + revisión |
| RNF-07 | Seguridad | HTTPS; token de parada HMAC; rate limiting de avisos por dispositivo e IP; validación de entradas; códigos de conductor almacenados con hash. | Tests unitarios + revisión |
| RNF-08 | Resiliencia | ≤ 1 petición al SAE por parada y ventana de caché; degradación a horario GTFS ante fallo. | Tests con adaptador SAE que falla |
| RNF-09 | Mantenibilidad | Arquitectura de puertos y adaptadores para ETA, posición, ocupación y GPS; el dominio no depende de frameworks. | Revisión + test de dependencias (import-linter) |
| RNF-10 | Testabilidad | Tests deterministas sin red (GTFS reducido de fixture, grabaciones SAE, reloj inyectable); cobertura de dominio backend ≥ 80 %. | pytest + coverage |
| RNF-11 | Despliegue | Entorno completo levantable con `init.sh` / `docker compose`. | Ejecución en limpio |
| RNF-12 | Capacidad | 200 clientes concurrentes (demo) sin incumplir RNF-01/RNF-02. | Test de carga (locust) |
| RNF-13 | Observabilidad | Logs estructurados JSON; métricas de aciertos de caché y errores del SAE. | Revisión |
| RNF-14 | Licencias | Atribución visible a EMT València y Ajuntament de València como fuentes de datos. | Revisión UI |
| RNF-15 | Internacionalización | Todos los textos de interfaz en ficheros de traducción (es, ca-valencia); ningún texto literal en componentes. | Lint de i18n en CI |
