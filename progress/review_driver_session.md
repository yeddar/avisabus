# Revisión: driver_session
Ciclo: 2 de la v1.5 · Fecha: 2026-11-11 · Agente: reviewer · Spec: specs/driver_session/ v1.5 (APPROVED)
Base: `origin/develop...HEAD` (HEAD 240c97a). Rama `feat/driver_session-v1.4`. Cubre T-10 (commits fea106a de la
v1.4, 97c4377 de la v1.5 y 744bb37, la corrección de B-01) y la repetición de T-07.

## Veredicto: APPROVED

B-01 está resuelto. El test con trazados reales vuelve a exigir `no_progress == 0` en los dos modelos de ruido
y en el control. El mutante `firstoff15` lo deja en rojo justo por esa aserción, y el resto del test fija
exactamente lo que pide AC-09 v1.5. No hay cambios de producción ni fuera del alcance de T-10.
`CI=1 ./init.sh verify --e2e` y `pytest -m slow --no-cov` están en verde. Quedan no bloqueantes, casi todos de
redacción de la spec.

## Matriz AC → evidencia

Rutas relativas a `backend/tests/`. El único cambio de código del diff es
`integration/test_upcoming_stops_real_shapes.py`. Desde el ciclo 1, ese cambio es solo el commit 744bb37 (+10/−3
líneas). `git diff origin/develop...HEAD` no muestra cambios en `backend/src`, `frontend`, `deploy`, `docs`,
`specs` ni `.env.example`. Los AC distintos de AC-09 no han cambiado desde la v1.3, cuya revisión fue
APPROVED. Se dan por comprobados con la suite completa y la trazabilidad en verde.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01–AC-08, AC-10–AC-15 | Los mismos que en la revisión de la v1.3 | OK | No cambian en el diff. `./init.sh verify --e2e` en verde, trazabilidad OK. |
| AC-09 (unit) | `unit/test_upcoming_stops.py` (26 citas) y `unit/test_driver_sessions.py` (28 citas) | OK | No cambian. Detectan los mutantes de ventana que el test real no ve con 200 m (N-13). Hay un hueco antiguo en el umbral de fuera de ruta de la primera posición (N-15). |
| AC-09 (real, v1.5) | `integration/test_upcoming_stops_real_shapes.py:244–273` (σ 10 m correlado e independiente, semillas 1–20); control `:276–287` | **OK** | Comprobado contra la spec línea a línea: semillas `range(1, 21)` (`:50`); 30 km/h y una posición cada 5 s (`:48–49`); σ 10 m con ρ 0,95 y con ruido independiente (`:238–241`); "a menos de 150 m" como `abs(error) < 150` (`:101`); `near >= 0,995 · positions` por modelo (`:271`); "más de 200 m por delante" como `error > 200` (`:97`, `:272`); "más de 500 m por detrás" como `-error > 500` (`:99`, `:273`); todos los trazados en cada semilla (`:268`). **B-01:** `assert all(figures.no_progress == 0 …)` (`:270`) y `figures.no_progress == 0` en el control (`:286`). El informe por semilla se imprime aunque el test pase (`:231–235`) y ahora incluye `no_progress` en el total (`:264`). El docstring (`:11–16`) recoge las limitaciones que la spec acepta. |

## Verificación ejecutada

| Comando | Resultado |
|---|---|
| `CI=1 ./init.sh verify --e2e` (puerto 4173 libre, comprobado con `lsof`) | **Salida 0, "verify: todo en verde".** Backend: format, lint, types y architecture OK. pytest: 1915 passed y 9 deselected; cobertura `domain`+`application` del 99,66 %. Vitest: 660 passed y 2 skipped (68 ficheros). Build + bundle: 5 passed. Playwright + axe: 132 passed y 12 skipped. `feature_list.json` y trazabilidad AC → test: OK. |
| `cd backend && uv run pytest -m slow --no-cov -rA` | **9 passed, 1915 deselected, salida 0** (56,4 s). Correlado: 374 280 posiciones, 99,993 % a menos de 150 m, 130,8 m como máximo por delante y 422,2 m por detrás. Independiente: 99,9997 %, 157,1 m y 121,9 m. Control: 100 %, 0,0 m y 41,7 m. `ahead>200 = 0`, `behind>500 = 0` y `no_progress = 0` en los tres. Son las mismas cifras que en el ciclo 1 y en `progress/impl_driver_session.md`. |
| T-07 (contrato del frontend) | `integration/test_openapi_snapshot.py` pasa dentro de `verify`. El diff no toca `frontend/src/shared/api/`. No hay nada que regenerar. |

### Mutantes (ciclo 2)

Se trabajó sobre una copia de `backend/` en el scratchpad, fuera del repositorio. Los tests se ejecutaron con el
intérprete del `.venv` y `PYTHONPATH` apuntando a la copia. Comprobado: `avisabus.__file__` y
`tests.support.drivers.__file__` están en la copia. El feed se enlazó por *symlink*. El script aplica cada
mutante con una sustitución que debe aparecer exactamente una vez y restaura el fichero al terminar. La línea
base da 3 passed, con las mismas cifras que en el repositorio.

| Mutante | Test real v1.5 | Nota |
|---|---|---|
| **`firstoff15`**: sin progreso previo, fuera de ruta a más de 15 m (`application/driver_sessions.py:502`) | **Rojo**: 2 failed y 1 passed | Correlado: `no_progress=971` y 99,733 %. Independiente: `no_progress=449` y 99,880 %. Ninguno supera los máximos, así que solo falla la aserción nueva (`:270`). En el ciclo 1 este mutante pasaba. **B-01 resuelto.** |
| `firstskip`: la primera posición de cada trazado no se proyecta | **Rojo**: 3 failed | 1 880 posiciones sin progreso por modelo, una por trazado y semilla. El percentil se queda en 99,490 % y 99,497 %. El control también falla, con `no_progress=94`. |
| `MAX_SPEED_MPS = 200` | **Rojo**: 2 failed | 1 019 y 1 336 posiciones a más de 200 m por delante (máx. 1 051,3 m). |
| `OFF_ROUTE_M = 20` | **Rojo**: 2 failed | 98,514 %, 615 posiciones por detrás y `no_progress` de 292 y 160. |
| Sin `max(previous, candidate)` | **Rojo**: 3 failed | 741 y 473 posiciones por detrás (máx. 3 528,9 m). En el control, 152,4 m en `1026_2253_2186`. |
| `firstoff40`: como `firstoff15`, pero a más de 40 m | Verde | Con σ 10 m ninguna primera posición llega a 40 m del trazado (`no_progress=0`), así que el mutante es equivalente bajo esta carga. Lo que falta es un test unitario (N-15). |

Además, se pasó la suite rápida (`tests/unit` y `tests/integration`, sin `slow`) contra el umbral de fuera de
ruta de la primera posición a 15, 100 y 140 m. Las tres variantes dan 1913 passed, igual que la línea base. Las
2 fallas que aparecen también salen en la línea base y son del entorno de la copia:
`test_env_example_documents_every_setting` y `test_openapi_snapshot`, que leen ficheros fuera de `backend/`. Ver
N-15.

Después de cada mutante, la copia quedó igual que el repositorio (`diff -q`). El repositorio no cambia:
`git status` solo muestra `?? qr/`, que ya estaba antes.

## Hallazgos

### Bloqueantes

Ninguno.

- **B-01 (ciclo 1): cerrado.** Corregido en 744bb37
  (`backend/tests/integration/test_upcoming_stops_real_shapes.py:270` y `:286`). La comprobación con mutantes
  está arriba. El implementer retira, en `progress/impl_driver_session.md`, la decisión local de la v1.4 que
  causaba el problema.

### No bloqueantes

Siguen abiertos de ciclos anteriores (se conserva la numeración). Ni el código de producción ni la spec han
cambiado:
- **N-01 · AC-04.** Un JSON mal formado sin token sigue respondiendo `422` en lugar de `401`.
- **N-03 · despliegue (AC-02).** El limitador usa `request.client.host`
  (`backend/src/avisabus/adapters/inbound/http/routes/driver.py:256`). Hay que tenerlo en cuenta en
  `deployment_rpi`.
- **N-04 · redacción de la spec.** `specs/driver_session/tasks.md:42` (T-06) sigue citando `http/app.py`, y
  `design.md` §2 no lista `InvalidPositionError` ni `AuthenticateDriverSession`.
- **N-06 · redacción de la spec · `specs/driver_session/design.md:97`.** Sigue el paréntesis "(la que fijó el
  progreso)".
- **N-07 · Problema de spec · `specs/driver_session/design.md:177`.** La fila "AC-09 (v1.1)" de §6 sigue diciendo
  "informa del máximo adelanto y retraso por trazado". Tampoco menciona las semillas 1–20, el percentil ni los
  máximos. `requirements.md:112` (v1.5) y `tasks.md:61` piden el resultado "por semilla", y eso es lo que hace
  el test, que además lista los trazados que no están a menos de 150 m (`:110–123`). Por AGENTS.md §2 manda
  `requirements.md`. Conviene alinear §6 en la próxima versión (CP-3 menor, decide la persona).
- **N-08 · redacción de la spec · `specs/driver_session/design.md:52–63` y `:155–158`.** `progress_recorded_at`
  solo aparece en el texto (`:101`), no en el modelo de §3 ni en la tabla de §4.
- **N-11 · redacción de la spec · `specs/driver_session/design.md:61`.** El modelo sigue declarando
  `last_position_at` con el comentario "renombrado a `last_fix_at`".
- **N-12 · alcance de T-10.** Se retiran los niveles σ 3 y σ 5. Se acepta: AC-09 solo fija σ 10 m, y con B-01
  resuelto no se pierde detección.
- **N-13 · coste de la v1.5 (informativo).** Con el máximo de 200 m, el test real ya no detecta una ventana por
  delante de unos 200 m (`MAX_SPEED_MPS = 30` o `AHEAD_MARGIN_M = 100`). Los tests unitarios sí la detectan.
- **N-14 · agregación del percentil.** Se calcula por modelo de ruido sobre las 20 semillas (`:249–271`), que es
  más estricto que agregar los dos modelos. Cabe en la redacción de AC-09.

Nuevo:
- **N-15 · AC-09, `docs/verification.md` §4 ("los tests fallarían si se rompe el comportamiento") · hueco
  antiguo en los tests unitarios, fuera de T-10.** Ningún test fija que la **primera** posición entre unos 40 y
  150 m del trazado tenga progreso (`backend/src/avisabus/application/driver_sessions.py:502`).
  - **Evidencia.** Las variantes del umbral a 40, 100 y 140 m solo para la primera posición pasan la suite
    rápida y el test real.
  - **Por qué no bloquea.** Es anterior a esta versión: los tests unitarios de AC-09 no han cambiado desde la
    v1.3, que fue APPROVED. T-10 solo pide el test con trazados reales, que con σ 10 m no genera primeras
    posiciones tan alejadas. El umbral general sí está cubierto: el mutante `OFF_ROUTE_M = 20` se detecta.
  - **Sugerencia.** Para un próximo ciclo, un test unitario en `unit/test_driver_sessions.py`: primera posición a
    unos 100 m del trazado → `progress_m` no es `None` y `off_route = false`; a unos 160 m → `off_route = true`
    y sin progreso.

Cerrados antes: N-05 y N-10 en el ciclo 1 de la v1.5. Los números que faltan en la lista se cerraron en revisiones anteriores.

### Alcance

- **Código:** solo `backend/tests/integration/test_upcoming_stops_real_shapes.py`, el fichero que lista T-10.
  Sin cambios en producción, frontend, contrato OpenAPI, `.env.example`, textos de interfaz, `docs/` ni `specs/`.
- **Progreso:** `feature_list.json`, `progress/current.md` y `progress/history.md` (orquestador) y
  `progress/impl_driver_session.md` (implementer) están dentro de su rol.
- **Commits:** Conventional Commits con el ámbito de la feature (`test(driver_session)`, `chore(progress)`,
  `chore(driver_session)`), más el *merge* de `develop`.
- No se ha tocado `qr/` ni `.env`.
