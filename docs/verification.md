# Verificación — AvisaBus

> Estado: **APROBADO** (v1.0 · 2026-10-31). Define cuándo algo está terminado y cómo se revisa.

## 1. Niveles

| Nivel | Cuándo | Quién | Cómo |
|---|---|---|---|
| Tarea | Al cerrar cada `T-xx` | implementer | Comando de verificación de la tarea |
| Feature | Antes de `in_review` | implementer | `./init.sh verify` en verde |
| Revisión | `in_review` | reviewer | §3 y §4 de este documento |
| Bloque | Fin de bloque | persona | Demo manual (CHECKPOINTS CP-6) |
| Sistema | Bloque 5 | `nfr_validation` | Pruebas de carga, accesibilidad y tiempos (RNF) |

## 2. `./init.sh verify`

Ejecuta, y falla si falla cualquiera (las partes aún no creadas se omiten con aviso):

| Paso | Backend | Frontend |
|---|---|---|
| Formato | `uv run ruff format --check .` | `npm run format:check` |
| Lint | `uv run ruff check .` | `npm run lint` |
| Tipos | `uv run mypy` | `npm run typecheck` |
| Arquitectura | `uv run lint-imports` | — |
| Tests + cobertura | `uv run pytest` (cobertura `domain`+`application` ≥ 80 %, sockets desactivados) | `npm run test` |
| Build | — | `npm run build` |
| Trazabilidad | `python3 scripts/check_traceability.py` (raíz) | |

`./init.sh verify --e2e` añade `npm run e2e` (Playwright + axe). Obligatorio para features de
frontend.

`scripts/check_traceability.py` comprueba, para cada feature con estado ≥ `implementing`, que
cada `<feature>.AC-n` de su `requirements.md` aparece citado en al menos un test.

## 3. Definición de terminado (DoD) de una feature

- [ ] Todas las tareas de `tasks.md` hechas y registradas en `progress/impl_<feature>.md`.
- [ ] Cada AC tiene al menos un test que lo cita y lo verifica de verdad.
- [ ] `./init.sh verify` (y `--e2e` si hay frontend) en verde.
- [ ] Sin cambios fuera del alcance de la feature.
- [ ] Variables de configuración nuevas documentadas en `.env.example`.
- [ ] Textos de interfaz nuevos en `es` y `ca-valencia`.
- [ ] Revisión con veredicto `APPROVED`.

## 4. Lista de comprobación del reviewer

**Contrato**
- [ ] El comportamiento coincide con los AC (incluidos los casos `SI … ENTONCES`).
- [ ] Interfaces, endpoints, eventos y errores coinciden con `design.md`.

**Arquitectura**
- [ ] `domain/` sin dependencias externas (lint-imports) y sin I/O.
- [ ] Puertos usados en lugar de implementaciones concretas fuera de `main.py`.
- [ ] Sin `datetime.now()` / `time.time()` fuera de `SystemClock`.

**Tests**
- [ ] Sin red (sockets bloqueados) ni sleeps reales; reloj con `FakeClock`.
- [ ] Los tests fallarían si se rompe el comportamiento (no son tautológicos).
- [ ] Fixtures pequeñas y con origen documentado.

**Privacidad y seguridad**
- [ ] No se registra `device_id`, códigos ni necesidades asociadas a un identificador.
- [ ] Entradas validadas; secretos solo por configuración.
- [ ] Datos efímeros borrados según RNF-06.

**Frontend (si aplica)**
- [ ] Sin textos literales (lint i18n) y claves en ambos idiomas.
- [ ] axe sin violaciones en las vistas nuevas (perfiles móvil y tablet).
- [ ] Información no transmitida solo por color; objetivos táctiles ≥ 44 px; foco visible.
- [ ] Anuncios `aria-live` / `role="status"` donde la spec lo pide.

**Convenciones**
- [ ] Nombres según el glosario de `docs/conventions.md`.
- [ ] Commits Conventional Commits con ámbito de la feature.

## 5. Evidencias

La revisión deja en `progress/review_<feature>.md` la matriz AC → test → resultado y el resumen
de la salida de `./init.sh verify`. Estas evidencias se usan en la memoria del TFM (OBJ-09).
