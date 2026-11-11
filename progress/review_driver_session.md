# Revisión: driver_session
Ciclo: 1 de la v1.5 · Fecha: 2026-11-11 · Agente: reviewer · Spec: specs/driver_session/ v1.5 (APPROVED)
Base: `origin/develop...HEAD` (HEAD 0642cf2). Rama `feat/driver_session-v1.4`. Cubre T-10 (commits fea106a de la
v1.4 y 97c4377 de la v1.5) y T-07 repetida.

## Veredicto: CHANGES_REQUESTED

El test fija bien el percentil, las fronteras, las semillas 1–20, los dos modelos de ruido y el máximo de 200 m
por delante. Pero al reescribirlo en la v1.4 se perdió la aserción `no_progress == 0` del test anterior. Ahora
una posición sin progreso solo cuenta contra el 0,5 % del percentil. Es una relajación que no autoriza ni la v1.4
ni la v1.5, y deja vivo un mutante que incumple AC-09 y que ningún otro test detecta (B-01). La corrección es de
una línea, en el fichero de T-10.

## Matriz AC → evidencia

Rutas relativas a `backend/tests/`. El único cambio de código del diff es
`integration/test_upcoming_stops_real_shapes.py`. No cambia producción (`git diff` vacío en `backend/src`,
`frontend`, `deploy`, `docs`, `specs` y `.env.example`). Los AC distintos de AC-09 no cambian desde la v1.3
(revisión APPROVED). Se dan por comprobados con la suite completa y la trazabilidad en verde.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01–AC-08, AC-10–AC-15 | Los mismos que en la revisión de la v1.3 | OK | Sin cambios en el diff. `./init.sh verify` en verde. |
| AC-09 (unit) | `unit/test_upcoming_stops.py:68–246`; `unit/test_driver_sessions.py` (28 citas) | OK | Sin cambios. Detectan los mutantes de constantes y ventana que el test real ya no ve con 200 m (ver N-13). |
| AC-09 (real, v1.5) | `integration/test_upcoming_stops_real_shapes.py:242–267` (σ 10 m correlado e independiente, semillas 1–20); control `:270–280` | **Incompleto (B-01)** | Fija bien: σ 10 m con ρ 0,95 y con ruido independiente (`:236–239`), semillas `range(1, 21)` (`:48`), 30 km/h cada 5 s (`:46–47`), `abs(error) < 150` (`:99`), `near >= 0,995 · positions` (`:265`), `error > 200` (`:95`, `:266`) y `-error > 500` (`:97`, `:267`). Los 94 trazados en cada semilla (`:264`) y el informe por semilla que se imprime aunque el test pase (`:229–233`). Falta exigir `no_progress == 0` en los dos tests con ruido (`:87–92`, `:264–267`). |

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `CI=1 ./init.sh verify --e2e` (puerto 4173 libre) | **Salida 0, "verify: todo en verde".** pytest: 1915 passed y 9 deselected; cobertura `domain`+`application` del 99,66 %. Vitest: 660 passed y 2 skipped. Bundle: 5 passed. Playwright + axe: 132 passed y 12 skipped (la vista del conductor solo se ejecuta en tablet, `e2e/driver.spec.ts:235`). ruff, mypy, lint-imports, build, `feature_list.json` y trazabilidad: OK. |
| `cd backend && uv run pytest -m slow` | 9 passed y 1915 deselected, pero **salida 1** solo por "Required test coverage of 80% not reached. Total coverage: 69.51%". Es el umbral global aplicado al subconjunto, como en la v1.2 y la v1.3. |
| `cd backend && uv run pytest -m slow --no-cov` | **9 passed, salida 0** (57,9 s). |
| `uv run pytest -m slow --no-cov -rA tests/integration/test_upcoming_stops_real_shapes.py` | 3 passed. Por semilla, cifras **idénticas** a las de `progress/impl_driver_session.md`. Correlado: 99,993 %, 130,8 m máx. por delante, 422,2 m por detrás. Independiente: 99,9997 %, 157,1 m por delante (semilla 16), 121,9 m por detrás. `ahead>200 = 0`, `behind>500 = 0` y `no_progress = 0` en todas. Control: 100 %, 0,0 y 41,7 m. |
| `avisabus openapi export` al scratchpad, comparado con `frontend/src/shared/api/openapi.json` | Iguales en JSON. T-07 no tiene cambios que *commitear*. |
| Hechos del feed (P-04), con un script de solo lectura sobre `data/gtfs/emt/` | `1026_2253_2186`: puntos 461–466 con las mismas coordenadas que 477–482. `route_id` 1026 es la línea 25. Hay 94 `shape_id` usados en `trips.txt` (= `REAL_SHAPES`). |

### Mutantes

Copia de `backend/` en el scratchpad, fuera del repositorio. Se ejecutó con el intérprete del `.venv` y
`PYTHONPATH` apuntando a la copia (verificado: `avisabus.__file__` está en la copia). El feed se enlazó por
*symlink*. La línea base dio 3 passed, con las mismas cifras que en el repositorio.

| Mutante | Test real v1.5 | Detectado por |
|---|---|---|
| `MAX_SPEED_MPS = 200` | **Rojo**: 1 019 y 1 336 posiciones a más de 200 m por delante (máx. 1 051,3 m) | Test real |
| `FIRST_FIX_TOLERANCE_M = 0` | **Rojo**: 46 y 40 por delante (máx. 1 202,8 m) | Test real |
| `_TIE_M = 30` (variante descartada en P-04) | **Rojo** (3 de 3): 13 y 7 por detrás (máx. 636,2 m); control al 99,615 % | Test real |
| `return max(` (la pasada más tardía) | **Rojo** (3 de 3): 447 y 491 por delante; control con 5 | Test real |
| Ventana sin `Δt` (`ahead_m = AHEAD_MARGIN_M`) | **Rojo** (3 de 3): percentil del 94–95 % y miles de posiciones por detrás | Test real |
| `OFF_ROUTE_M = 20` | **Rojo**: 98,514 % y 615 por detrás | Test real |
| Sin `max(previous, candidate)` (progreso que retrocede) | **Rojo** (3 de 3): 741 y 473 por detrás (máx. 3 528,9 m) | Test real |
| `AHEAD_MARGIN_M = 150` | **Rojo**: 13 y 15 por delante (máx. 231,6 m) | Test real |
| `MAX_SPEED_MPS = 30` | Verde (máx. 185,4 m por delante) | Unit: `test_constants_of_the_design`, `test_search_ahead_is_what_the_bus_could_have_travelled` y 2 de `test_driver_sessions.py` |
| `AHEAD_MARGIN_M = 100` | Verde (máx. 185,4 m) | Unit: 6 tests de `test_upcoming_stops.py` y `test_driver_sessions.py` |
| `MAX_SPEED_MPS = 25` | Verde (157,7 m; el original ya da 157,1 m) | Unit: 3 tests |
| `back_m = 0` | Verde (lógico: con `max(previous, …)` no empeora el progreso) | Unit: 3 tests |
| **`firstoff15`**: sin progreso previo, fuera de ruta a más de 15 m (`application/driver_sessions.py:502`) | **Verde**: 3 passed, con `no_progress` de 23 a 74 por semilla en el correlado y de 14 a 32 en el independiente (≈ 950 y ≈ 450 posiciones en total) y el percentil en 99,733 % y 99,880 % | **Ninguno.** Tampoco `tests/unit` ni `integration/test_driver_api.py`. El test de `origin/develop` (v1.3) lo detecta: 4 failed por `assert figures.no_progress == 0`. → **B-01** |

La copia se restauró tras cada mutante. El repositorio no cambia: `git status` solo muestra `?? qr/`, que ya
estaba.

## Hallazgos

### Bloqueantes

- **B-01 · AC-09 (v1.5) y `docs/verification.md` §4 ("los tests fallarían si se rompe el comportamiento") ·
  `backend/tests/integration/test_upcoming_stops_real_shapes.py:87–92` y `:264–267`.**
  - **Qué pasa.** El test de la v1.3 exigía `figures.no_progress == 0` en todos los niveles (en `origin/develop`,
    `_assert_within`). La reescritura de la v1.4 (fea106a) lo sustituyó por "una posición sin progreso cuenta
    como no a menos de 150 m". Así, hasta el 0,5 % de las posiciones de cada modelo (≈ 1 870) pueden quedarse
    sin progreso y el test pasa. Según `Figures.record`, una posición sin progreso no cuenta como "más de 500 m
    por detrás".
  - **Por qué es un fallo.** AC-09 solo permite no proyectar una posición a más de 150 m del trazado ("SI la
    posición está a más de 150 m … ENTONCES … `off_route` sin cambiar el progreso"). Sin progreso anterior se
    busca "en todo el trazado". Con σ 10 m todas las posiciones están a pocas decenas de metros, así que la spec
    exige que todas tengan progreso. Ni la v1.4 ni la v1.5 relajan esto: la v1.5 solo cambia el máximo por
    delante. La decisión local de la v1.4 que lo relajó no llegó a revisarse, porque T-10 se bloqueó.
  - **Prueba.** El mutante `firstoff15` incumple AC-09: deja sin progreso las primeras posiciones a más de 15 m
    del trazado. Pasa este test, toda la suite unitaria y `test_driver_api.py`. El test anterior lo detectaba.
  - **Corrección** (dentro del fichero de T-10, sin cambio de spec). En el test con ruido, añadir
    `assert all(f.no_progress == 0 for f in per_seed), report`. Otra opción es contar una posición sin progreso
    también en `too_far_behind`. El control ya lo exige de forma implícita (`near == positions`, `:280`), pero
    conviene que sea explícito. Después, comprobar que el mutante `firstoff15` deja el test en rojo.

### No bloqueantes

Abiertos de ciclos anteriores (se conserva la numeración):
- **N-01 · AC-04.** Un JSON mal formado sin token sigue respondiendo `422` en lugar de `401`. Sin cambios.
- **N-03 · despliegue (AC-02).** El limitador usa `request.client.host`
  (`backend/src/avisabus/adapters/inbound/http/routes/driver.py:256`). Hay que tenerlo en cuenta en
  `deployment_rpi`.
- **N-04 · redacción de la spec.** `specs/driver_session/tasks.md:42` (T-06) sigue citando `http/app.py`, y
  `design.md` §2 no lista `InvalidPositionError` ni `AuthenticateDriverSession`.
- **N-06 · redacción de la spec · `specs/driver_session/design.md:97`.** Sigue el paréntesis "(la que fijó el
  progreso)".
- **N-07 · Problema de spec (antes, del test) · `specs/driver_session/design.md:177`.** La fila "AC-09 (v1.1)"
  de §6 no se actualizó en la v1.4 ni en la v1.5:
  - Pide informar "del máximo adelanto y retraso **por trazado**". `requirements.md:111` (v1.5) y
    `tasks.md:61` (T-10) piden el resultado "**por semilla**".
  - No menciona las semillas 1–20, el percentil ni los máximos.
  
  Por la jerarquía de AGENTS.md §2 manda `requirements.md`, y el test hace lo que dicen `requirements.md` y
  T-10: una línea por semilla con los trazados que no están a menos de 150 m y su peor error, `:108–121`.
  No es una contradicción bloqueante, pero conviene alinear §6 en la próxima versión (CP-3 menor, decide la
  persona). El hallazgo sobre el código queda cerrado.
- **N-08 · redacción de la spec · `specs/driver_session/design.md:52–63` y `:155–158`.** `progress_recorded_at`
  solo aparece en el texto (`:101`), no en el modelo de §3 ni en la tabla de §4.
- **N-11 · redacción de la spec · `specs/driver_session/design.md:61`.** El modelo sigue declarando
  `last_position_at` con el comentario "renombrado a `last_fix_at`".

Cerrados en esta revisión:
- **N-05** (retraso con otras semillas): lo resuelven la v1.4 (percentil, 500 m por detrás y limitación de los
  giros en U) y la v1.5.
- **N-10** (`docs/architecture.md:119`): el diagrama ya muestra `last_fix_at` y `last_seen_at`.

Nuevos:
- **N-12 · alcance de T-10 · niveles σ 3 y σ 5 retirados.** Lo acepto:
  - AC-09 solo fija σ 10 m desde la v1.2, y T-10 pide "semillas 1–20, criterio por percentil y máximos de AC-09".
  - Los mutantes muestran que no se pierde detección, salvo `firstoff15`, que en la v1.3 también veían los
    niveles σ 5 (`no_progress = 1`) y que se recupera con B-01.
  - La decisión está documentada en `progress/impl_driver_session.md`.
  
  Si la persona quiere conservar cifras de σ menores para la memoria, debería pedirlo la spec.
- **N-13 · coste de la v1.5 (informativo).** Con el máximo de 200 m, el test real ya no detecta una ventana
  por delante de 200 m en lugar de 150 m (`MAX_SPEED_MPS = 30` o `AHEAD_MARGIN_M = 100`; máx. 185,4 m). Con el
  máximo antiguo de 150 m lo habría detectado. Los tests unitarios sí lo detectan
  (`unit/test_upcoming_stops.py:60`, `:116` y `:130`), así que AC-09 sigue cubierto. Es la consecuencia
  aceptada de la decisión de la persona en la PR #62.
- **N-14 · agregación del percentil.** Se calcula por modelo de ruido sobre las 20 semillas (`:248–265`).
  Es más estricto que agregar los dos modelos juntos. Cabe en la redacción de AC-09, y la decisión está
  documentada.

### Alcance

- **Código:** solo `backend/tests/integration/test_upcoming_stops_real_shapes.py`, el fichero que lista T-10.
  Sin cambios en producción, frontend, contrato OpenAPI, `.env.example`, textos de interfaz, `docs/` ni `specs/`.
- **Progreso:** `feature_list.json`, `progress/current.md` y `progress/history.md` (orquestador) y
  `progress/impl_driver_session.md` (implementer) están dentro de su rol.
- **Commits:** Conventional Commits con el ámbito de la feature (`test(driver_session)`,
  `chore(progress)`, `chore(driver_session)`), más el *merge* de `develop`.
- No se ha tocado `qr/` ni `.env`.
