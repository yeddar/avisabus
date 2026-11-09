# Revisión: driver_session
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
