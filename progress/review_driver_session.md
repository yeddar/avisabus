# Revisión: driver_session
Ciclo: 2 · Fecha: 2026-11-09 · Agente: reviewer · Spec: specs/driver_session/ v1.2 (APPROVED)
Base: `origin/feat/position_estimation-v1.4...HEAD` (74bfef9)

## Veredicto: APPROVED

F-01 corregido. AC-09 y AC-10 cumplen v1.2 en metros reales, y el test `slow` mide lo que pide AC-09. No
hay hallazgos bloqueantes.

**Aviso para la persona:** el umbral de 150 m solo se cumple con la semilla del test. Con otras
semillas hay retrasos de hasta 422 m, que no son un defecto de implementación (ver N-05). Conviene
decidir si se acepta antes de `driver_demand`.

## Matriz AC → evidencia

Rutas relativas a `backend/tests/`. Las líneas son las de HEAD. Los AC sin cambios de código en este
ciclo se han comprobado con la suite completa.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `integration/test_driver_api.py:169–195`; `unit/test_driver_login.py:86–120` | OK | Sin cambios desde el ciclo 1. |
| AC-02 | `integration/test_driver_api.py:207–245`; `unit/test_driver_login.py:127–247` | OK | N-02 cerrado: `test_driver_api.py:226`, dígitos no ASCII con el *hasher* real. Mut. `code-ascii` detectado. |
| AC-03 | `integration/test_driver_api.py:258`; `unit/test_driver_login.py:256` | OK | |
| AC-04 | `integration/test_driver_api.py:290–321`; `unit/test_driver_sessions.py:728` | OK | |
| AC-05 | `integration/test_driver_api.py:332,714`; `integration/test_network_departures.py:119–137`; `unit/test_departures.py:71–77` | OK | |
| AC-06 | `integration/test_driver_api.py:354–429`; `integration/test_network_departures.py:142–232`; `unit/test_departures.py:83–214` | OK | |
| AC-07 | `integration/test_driver_api.py:441–520`; `unit/test_driver_sessions.py:163–247` | OK | |
| AC-08 | `integration/test_driver_api.py:532–612`, en especial `:601`; `unit/test_driver_sessions.py:266–340`, en especial `:325` | OK | **F-01 cerrado.** Ambos extremos dan `422` `problem+json` por HTTP, y no se guarda nada ni se avisa al *listener*. Mut. `f01-no-guard` detectado. |
| AC-09 | `integration/test_upcoming_stops_real_shapes.py:216–229`; `unit/test_driver_sessions.py:351–643`; `unit/test_upcoming_stops.py:68–246` | OK | Ventana, regla de la primera posición, marca, persistencia y metros reales. Bucle, ida y vuelta, dos pasadas a 400 m y hueco de 5 min, cubiertos. Ver N-05. |
| AC-10 | `unit/test_driver_sessions.py:534–675`; `unit/test_upcoming_stops.py:261–326` | OK | Con un feed inflado ×3: paradas y distancias en metros reales. Mut. `feed-stops`, `upcoming-ge`, `finished-gt` detectados. |
| AC-11 | `integration/test_driver_api.py:623–678`; `unit/test_driver_sessions.py:683–719` | OK | |
| AC-12 | `integration/test_driver_api.py:696`; `unit/test_driver_sessions.py:744–761` | OK | |
| AC-13 | `integration/test_main_driver.py:82–92`; `unit/test_reap_driver_sessions.py:68–234` | OK | |
| AC-14 | `integration/test_cli_driver_codes.py:547–570` | OK | |
| AC-15 | `integration/test_driver_api.py:734–825`; `unit/test_driver_login.py:270–284`; `unit/test_driver_sessions.py:254–777` | OK | T-08 no añade logs. |

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `CI=1 ./init.sh verify --e2e` (puerto 4173 libre) | **Salida 0, "verify: todo en verde"**: pytest 1711 passed, 12 deselected, cobertura 99,61 %; Vitest 563 passed y 2 skipped; Playwright + axe 126 passed; ruff, mypy, lint-imports (2 contratos), build y trazabilidad, OK |
| `cd backend && uv run pytest -m slow` | **12 passed.** La salida es distinta de 0 solo porque `--cov-fail-under=80` se aplica a este subconjunto (72,82 %); no hay ningún test fallido |
| `uv run pytest -k upcoming_stops -m "slow or not slow" --no-cov` (comando de T-08, sin cobertura) | 47 passed |

**Mutaciones** (copia en el scratchpad; línea base verde: 236 rápidos y 6 `slow`): 26 mutantes, 25
detectados. El superviviente es `off-ge` (frontera exacta de 150,0 m), igual que en el ciclo 1:
irrelevante, "más de 150 m" se cumple.

El test `slow` detecta por sí solo `feed-shape` (volver a unidades del feed), `window-3km`,
`window-no-elapsed`, `first-fix-nearest`, `first-fix-always` y `no-max`. No detecta
`mark-only-if-advances`, que sí detecta `test_driver_sessions.py:400`.

**Comprobación adicional:** `recorded_at` en `0001-01-01T00:00:00Z` da `204` y las peticiones siguientes
funcionan. AC-08 solo rechaza el futuro, y no queda ningún `500` de la clase de F-01.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

**N-05 · AC-09 · limitación de la regla, no defecto · `backend/src/avisabus/application/driver_sessions.py:495-500`, `backend/src/avisabus/domain/services/upcoming_stops.py:84-86`**

Reproducido el aviso del implementer con el código real y los 94 trazados:

| Ruido σ 10 m | Semillas con posiciones > 150 m | Posiciones | Máx. delante / detrás |
|---|---|---|---|
| Correlado ρ 0,95, semillas 1–20 | 5 de 20 | 28 de 374 280 | 130,8 / 422,2 m |
| Independiente, semillas 1–20 | 1 de 20 | 1 de 374 280 | 157,1 / 121,9 m |
| Semilla del test (control) | 0 | 0 | 97,5 / 66,9 m y 104,7 / 56,7 m |

*Diagnóstico* (traza paso a paso de la semilla 17, `1040_2172_2253`; el mismo patrón en las semillas 2, 4, 6 y 18):

1. El trazado hace un giro en U, con la ida y la vuelta separadas entre 4 y 35 m (`1027_*`: 4 m;
   `1040_*`: 20–37 m).
2. Ya en la vuelta, el error correlado deja la posición más cerca de la **ida**. El candidato queda
   detrás del progreso y `max` lo descarta.
3. La posición sigue a menos de 150 m, así que es "aceptada" y **mueve la marca**: Δt vale 5 s y la
   ventana no pasa de `[progreso − 100, progreso + 150]`.
4. El autobús sale de la ventana. Solo se recupera cuando la distancia a la ventana supera 150 m: se
   marca `off_route`, deja de moverse la marca y la ventana crece. Se recupera en 1–2 muestras.

En la semilla 17, el progreso se queda en 119,5 m mientras el autobús llega a 541,7 m (unos 50 s), con
2 muestras de `off_route` falso con el autobús en su recorrido (6 de 374 280 en total).

*Clasificación: limitación aceptable para esta feature; no es defecto de implementación ni CP-3.* El
código aplica la regla aprobada, AC-09 fija una semilla y con ella se cumple. El retraso se corrige
solo y es el error menos dañino: una parada ya pasada sigue en pantalla unos segundos, no desaparece
una por pasar (el problema de P-01). **Lo que no se puede afirmar** es que 150 m sea una cota de la
regla: se fijó en v1.2 mirando una sola realización del ruido (139 m máximo).

*Dos datos para decidir*, de una simulación mía que **no forma parte de AC-09** (mismos trazados y
semillas, con 30 s parado cada 300 m):
- Regla actual: posiciones a más de 150 m en 12 de 20 semillas con ruido correlado (máx. 169,5 delante,
  430,5 detrás) y 19 de 20 con ruido independiente (máx. 191,3 delante). Hay errores **por delante**
  con el autobús parado, que es la dirección dañina.
- Mover la marca solo cuando avanza el progreso (ver N-06): baja el retraso a 172–184 m, pero con paradas
  el adelanto llega a **590 m** en 20 de 20 semillas. Reintroduce P-01, así que no es la solución.

Es ruido sintético; no hay trazas GPS reales. **Propuesta para la persona:** aceptar la limitación ahora
y volver a medir con `driver_gps_simulator`, con paradas y giros en U, antes de apoyarse en esto en
`driver_demand`.

**N-06 · redacción de la spec · `specs/driver_session/design.md:95-96` frente a `specs/driver_session/requirements.md:92-93`**
AC-09 dice "la última aceptada"; el design añade "(la que fijó el progreso)", que no cubre una posición
aceptada que no avanza. El implementer sigue AC-09, que manda sobre el design, y lo fija
`test_driver_sessions.py:396-400`; los datos de N-05 respaldan esa lectura. Conviene quitar el paréntesis
en la próxima revisión. No requiere CP-3.

**N-07 · `backend/tests/integration/test_upcoming_stops_real_shapes.py:190-196`.** `design.md` §6 pide
informar del máximo "por trazado"; el test lo da por nivel de ruido. Solo afecta al informe: las
aserciones cubren cada posición.

**N-08 · redacción de la spec · `specs/driver_session/design.md:52-61,153-156`.** `progress_recorded_at`
falta en el modelo de §3 y en la tabla de §4; solo aparece en el texto de §3. Sin efecto en el código.

**N-09 · `docs/conventions.md` §7 · commit `f34e3de`.** El tipo `wip(...)` no es habitual en el repositorio.
Irrelevante si la rama se aplasta al fusionar.

Del ciclo 1: **N-02 cerrado**; N-01, N-03 y N-04 siguen abiertos, sin cambios.

### Comprobaciones pedidas

**Metros reales.** `TripRoutes._load` usa `cumulative_distances` para la forma y `stop_distances` para las
paradas (`application/driver_sessions.py:331-334`). `project_progress`, `_window`, `OFF_ROUTE_M` y
`upcoming_stops` operan sobre esos valores. Ningún cálculo de AC-09/AC-10 usa ya unidades del feed
(`shape_distances` no aparece en `application/` ni en `upcoming_stops.py`).

**Test `slow`.** Mide lo que dice AC-09: los 94 trazados, 30 km/h, posición cada 5 s, σ 10 m correlado
ρ 0,95 e independiente, con `UpdateDriverPosition` y `TripRoutes` reales, y el error en metros reales. El
umbral es 150 m, el de v1.2; las constantes 100/20/50/30/150 coinciden con la spec. El paso de 100 a
150 m (`587702a`) es el autorizado por la persona en v1.2.

**Semilla.** No hay indicios de que se eligiera mirando resultados:
- `SEED = 20261109` (la fecha del día) y la clave del generador ya están en el primer commit del test
  (`f34e3de`), cuando el test **fallaba** con 100 m, y no han cambiado después.
- Con las semillas 1–20, pasan la prueba 15 de 20 (correlado) y 19 de 20 (independiente): que la del test
  pase no es un resultado raro.
- **Límite:** git no prueba qué se hizo antes de ese commit. Las cifras de P-03 (139,1 m), obtenidas con un
  experimento en el scratchpad que no está en el repositorio, no coinciden con las del test (66,9 m), así
  que corresponden a otra realización del ruido.

**Decisiones del implementer.**

| Decisión | Valoración |
|---|---|
| `_stop_distances` → `stop_distances` en `position_estimator.py` | Cabe. Es un renombrado sin cambio de comportamiento que evita duplicar la lógica que el design pide usar "exactamente como" `position_estimation` v1.4. No está en los ficheros de T-08; se acepta por ser mínimo. |
| `progress_recorded_at` con toda posición aceptada | Cabe: es la lectura de AC-09, y la alternativa empeora con paradas (N-05, N-06). |
| `elapsed_s` = 0 sin marca | Cabe. Solo es alcanzable con filas anteriores a la columna; es la opción conservadora. |
| Distancia mínima en la primera posición | Cabe: AC-09 define "fuera de recorrido" por la distancia al trazado. |
| Sin migración (ADR-011) | Cabe. `driver_session` no existe en `data/avisabus.sqlite` y los datos son efímeros. |

**Regresiones.** Ninguna. En `position_estimator.py` el único cambio es el renombrado y sus tests pasan.
**Alcance:** fuera de la feature solo el renombrado y `test_main_position.py`, ya valorado en el ciclo 1.
Contrato OpenAPI sin cambios en T-08. Sin textos de interfaz. `qr/` ignorada.

---

Ciclo: 1 · Fecha: 2026-11-09 · Agente: reviewer · Spec: specs/driver_session/ v1.0 (APPROVED)
Base: `origin/feat/driver_codes_cli...HEAD` (20704eb)

## Veredicto: CHANGES_REQUESTED

Un hallazgo bloqueante de código (F-01, AC-08) y un **problema de spec que requiere CP-3** (P-01,
AC-09). El resto del comportamiento coincide con la spec.

## Matriz AC → evidencia

Rutas relativas a `backend/tests/`. "Mut." son las mutaciones que comprueban ese AC (detalle más abajo).

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `integration/test_driver_api.py:169,186,195`; `unit/test_driver_login.py:86,103,120` | OK | Token de 32 bytes `token_urlsafe`; en BD solo el SHA-256 (fila real comparada con `hashlib.sha256`). Mut.: `tok-plain/short/md5`, `code-spaces`. |
| AC-02 | `integration/test_driver_api.py:207,220,225,237`; `unit/test_driver_login.py:127–247` | OK | 5.º fallo `401`, `429` desde el siguiente intento, hasta 15 min tras el último fallo (`:186`, fallos espaciados), `Retry-After`, mal formado cuenta. Mut.: `lim-*` (5). |
| AC-03 | `integration/test_driver_api.py:250`; `unit/test_driver_login.py:256` | OK | Motivo `REPLACED` y token antiguo invalidado. |
| AC-04 | `integration/test_driver_api.py:282,304,313`; `unit/test_driver_sessions.py:539` | OK | Los 6 endpoints × 4 cabeceras. Excepción menor: N-01. |
| AC-05 | `integration/test_driver_api.py:324,690`; `integration/test_network_departures.py:119,137`; `unit/test_departures.py:71,77` | OK | |
| AC-06 | `integration/test_driver_api.py:346–421`; `integration/test_network_departures.py:142–232`; `unit/test_departures.py:83–214` | OK | Ventana inclusiva, día de servicio anterior, cambio de hora, `taken`. Mut.: `dep-*`, `net-*` en `departures`. |
| AC-07 | `integration/test_driver_api.py:433–512`; `unit/test_driver_sessions.py:160–244` | OK | |
| AC-08 | `integration/test_driver_api.py:524–591`; `unit/test_driver_sessions.py:263–321` | **FALLA** | **F-01**: fechas extremas dan `500`. El resto, OK. |
| AC-09 | `unit/test_upcoming_stops.py:61–182`; `unit/test_driver_sessions.py:332–454` | OK contra la spec | Bucle e ida y vuelta cubiertos. **P-01**: la regla de la spec falla con trazados reales. |
| AC-10 | `unit/test_upcoming_stops.py:197–262`; `unit/test_driver_sessions.py:466–486` | OK | Mut.: `us-upcoming-ge`, `us-finished-gt`, `us-limit`. |
| AC-11 | `integration/test_driver_api.py:602–657`; `unit/test_driver_sessions.py:494–530` | OK | |
| AC-12 | `integration/test_driver_api.py:672`; `unit/test_driver_sessions.py:555–572` | OK | |
| AC-13 | `unit/test_reap_driver_sessions.py:68–234`; `integration/test_main_driver.py:82,92` | OK | Arranque y parada con `lifespan` reales. |
| AC-14 | `integration/test_cli_driver_codes.py:547,559,570` | OK | CLI real contra la tabla real. |
| AC-15 | `integration/test_driver_api.py:710–801`; `unit/test_driver_login.py:270–284`; `unit/test_driver_sessions.py:251,579,588` | OK | Comprobado además con uvicorn real (abajo). |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` con el puerto 4173 libre: **salida 0, "verify: todo en verde"**.

| Paso | Resultado |
|---|---|
| ruff format, ruff check, mypy | OK |
| lint-imports | 2 contratos respetados |
| pytest | 1667 passed, 6 deselected; cobertura `domain`+`application` 99,60 % |
| Frontend: format, lint, typecheck, build | OK |
| vitest | 563 passed, 2 skipped |
| Playwright + axe | 126 passed |
| Trazabilidad AC → test | OK |

**Mutaciones** (copia en el scratchpad; línea base verde, 285 tests): 57 mutantes, **53 detectados, 4
supervivientes**. Una primera pasada se descartó por inválida: la copia estaba incompleta y todos los
mutantes "morían" al recoger los tests. Tres mutantes se repitieron con corrección: `net-no-service`
(había mutado otro método) y `main-no-stop`/`main-no-reaper` (el subproceso importaba el código sin
mutar); los tres se detectan.

| Superviviente | Valoración |
|---|---|
| `sel-no-holder` | Equivalente: `save` también lanza `DepartureTakenError` (real y falso). |
| `off-ge` | Frontera exacta de 150,0 m sin fijar; "más de 150 m" se cumple. Irrelevante. |
| `mask-no-query` | `/api/v1/driver?x` no es ninguna ruta. Irrelevante. |
| `code-ascii` | Hueco de test real: ver N-02. |

**Reproducciones en la copia** (no forman parte de la suite):
- `recorded_at` extremo por HTTP: F-01.
- uvicorn real en loopback: `"- - \"POST /api/v1/driver/sessions HTTP/1.1\" 401"` y
  `"- - \"GET /api/v1/driver/lines?x=1 HTTP/1.1\" 401"` con la IP enmascarada en el JSON final;
  `/api/v1/health` conserva `127.0.0.1:puerto`. El filtro funciona con la configuración real de logging.
- AC-09 con los 94 trazados del feed real: P-01.

## Hallazgos

### Bloqueantes

**F-01 · AC-08, RNF-07 · `backend/src/avisabus/application/driver_sessions.py:465`**
`command.recorded_at.astimezone(UTC)` lanza `OverflowError` con fechas en los extremos del calendario,
antes de la comprobación del futuro. Reproducido con sesión válida:

| `recorded_at` | Respuesta | Esperado |
|---|---|---|
| `9999-12-31T23:59:59-14:00` | `500` (`OverflowError`) | `422` (más de 30 s en el futuro, AC-08) |
| `0001-01-01T00:00:00+14:00` | `500` (`OverflowError`) | Ninguna entrada debe dar `500`; `422` es lo razonable |
| `9000-01-01T00:00:00Z` | `422` | `422` |

Corrección: tratar el desbordamiento como `InvalidPositionError` y añadir un test con ambos extremos.

### Problema de spec → CP-3

**P-01 · AC-09 y `design.md` §3 (regla "segmento más cercano" + `progress = max(previous, candidato)`)**
El código cumple la spec al pie de la letra (`domain/services/upcoming_stops.py:52-66`,
`application/driver_sessions.py:490-497`), pero la regla hace que el progreso salte hacia delante con
trazados reales. Los trazados pasan a pocos metros de sí mismos a unos cientos de metros de recorrido
(en la muestra, puntos separados 2–8 m y 330–490 m a lo largo del trazado). Basta con que una posición
con ruido quede más cerca de la pasada posterior: `max` hace el salto permanente hasta que el autobús
llega de verdad a ese punto. Mientras tanto, las paradas intermedias **desaparecen de las próximas
paradas sin haberlas pasado**, que es el objetivo de RF-26.

Simulación con los 94 trazados del feed activo y `project_progress` real (paso de 40 m):

| Ruido GPS | Trazados con salto > 300 m | Posiciones > 100 m por delante |
|---|---|---|
| Sin ruido (control) | 0 / 94 | 0 % |
| σ 3 m, correlado (ρ 0,95) | 56 / 94 | 4,4 % |
| σ 5 m, correlado | 67 / 94 | 7,1 % |
| σ 5 m, independiente | 87 / 94 | 12,6 % |
| σ 10 m, correlado | 91 / 94 | 13,6 % |

Límite de esta evidencia: el ruido es sintético, no hay trazas GPS reales. El trazado sí es real y el
control sin ruido descarta un error de la simulación.

Variantes probadas, ninguna lista para adoptarse:
- Ventana hacia delante de 300 m en lugar de 3 km: casi no ayuda (61/94 con σ 5 m).
- El tramo más temprano dentro de 20 m de la mejor distancia: 0/94 con σ 5 m, pero 42/94 con σ 10 m y
  un retraso de más de 60 m en un tercio de las posiciones.

**Propuesta para la persona:** decidir en CP-3 si AC-09 cambia antes de `driver_demand`. Vías sin
probar: elegir el mínimo local de distancia más próximo al progreso anterior, en vez del mínimo global
de la ventana, o usar el rumbo del movimiento. Conviene validarlo con trazas reales o con
`driver_gps_simulator` añadiendo ruido.

### No bloqueantes

- **N-01 · AC-04.** Un JSON mal formado sin token responde `422` en lugar de `401`: FastAPI analiza el
  cuerpo antes que las dependencias. Un cuerpo válido, o inválido según el esquema, sí da `401`. No expone nada.
- **N-02 · AC-02 · `backend/tests/unit/test_driver_login.py:130`.** El caso de dígitos no ASCII usa un
  *hasher* falso, así que quitar `isascii()` no rompe ningún test. Falta un caso por HTTP con el *hasher* real.
- **N-03 · despliegue (AC-02).** El limitador usa `request.client.host`. Tras un proxy que no sea
  127.0.0.1, sin `forwarded-allow-ips`, todas las tabletas compartirían IP y cinco fallos bloquearían a
  todas. Deducido de la lectura, no probado. A tener en cuenta en `deployment_rpi`.
- **N-04 · redacción de la spec.** T-06 cita `http/app.py`, y `design.md` §2 no lista
  `InvalidPositionError` ni `AuthenticateDriverSession`. Ajustar en la próxima revisión.

### Comprobaciones pedidas

**Seguridad y privacidad**
- Token: `secrets.token_urlsafe(32)`, entrega única, fuera de `repr`, solo SHA-256 en BD. Correcto.
- Comparación en tiempo constante: **no la hay ni la exige la spec**. El design fija la búsqueda por
  `by_token_hash`, y al comparar el SHA-256 de un token de 256 bits el atacante no controla los bytes
  comparados. Aceptable.
- Códigos: HMAC con la misma clave en CLI y API; fuera de `repr`; nunca en logs.
- AC-15: sin código, token, coordenadas ni IP en logs de aplicación; `driver.login_failed` sin datos;
  `no-store` también en `401`, `404`, `422` y `500`. `access_log.py` correcto (formato de
  `uvicorn/protocols/http/h11_impl.py:477` y ejecución real).

**Limitador:** cumple. `max_failures − 1` hace que `acquire` rechace justo el fallo que completa la
cuenta; el bloqueo se fija a `ahora + 15 min`; durante el bloqueo no se registran fallos, y al terminar
todos han salido de la ventana. Quinto fallo `401`, `429` desde el siguiente. Mal formado: `401` y cuenta.

**Decisiones no fijadas por la spec** (ninguna requiere CP-3)

| Decisión | Valoración |
|---|---|
| `InvalidPositionError` → `422` `about:blank` | Cabe: AC-08 pide `422` y no fija tipo. Afectada por F-01 solo en el desbordamiento. |
| `STALE`/`IDLE` sobre `last_position_at` | Cabe: el design lo define como instante de servidor. |
| `REVOKED` gana a `IDLE`; código inexistente como revocado | Cabe: AC-13 no fija precedencia. |
| Casos límite de progreso (sin progreso, viaje retirado, empates) | Caben; `driver_ui.AC-08` cubre la espera de GPS. |
| Tarea de fondo en `main.py` | Cabe y es obligado: `.importlinter` pone `adapters` y `background` al mismo nivel, y `alert_expiry` T-03 hace lo mismo. Error de redacción de T-06 (N-04). |

**`tests/integration/test_main_position.py`:** cambio correcto y mínimo. El endpoint nuevo termina en
`/position` y rompería la sonda; excluir `/api/v1/driver/` mantiene lo que comprueba
`position_estimation`. Ninguna tarea lo lista, pero es consecuencia directa de T-05.

**Código de otras features:** `list_lines` y `departures` son adiciones autorizadas por T-02 y sin
regresiones (suite completa en verde; mutantes de `departures` detectados). La sustitución de
`_no_open_session` es correcta y la cubre AC-14.

**Alcance:** sin cambios fuera de la feature, salvo los justificados arriba. Las 5 variables nuevas
están en `.env.example`. Commits conforme a la convención. Sin textos de interfaz.

**Avisos del implementer**

| # | Aviso | Clasificación |
|---|---|---|
| 1 | C2/C3 (un `headsign` por sentido; AC-09 contra el viaje elegido) | **Nota.** La implementación sigue la spec: AC-05, `driver_ui.AC-02` y ADR-018 son explícitos, y AC-06 muestra el destino por salida. La nota de `progress/current.md` es anterior y no es fuente de verdad; conviene retirarla. CU-08 4b y su postcondición siguen diciendo "línea y sentido": es un resto de redacción de la PR #46, a corregir por la persona (CP-4). |
| 2 | IP en el log de acceso fuera de `/driver` | **Nota, con seguimiento necesario.** Confirmado con uvicorn real en `/health`. Fuera del alcance de esta feature, pero `alert_create` exige que ningún log incluya la IP (`specs/alert_create/requirements.md:116`), así que es un incumplimiento de una feature ya cerrada. Debe resolverse con una tarea propia (generalizar el filtro, o sin log de acceso en `deployment_rpi`). |
| 3 | Riesgo de AC-09 con GPS real | **CP-3** (P-01). No es un caso raro de calles de ida y vuelta: afecta a la mayoría de los trazados simulados. |
