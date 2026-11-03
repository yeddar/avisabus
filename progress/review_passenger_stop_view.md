# Revisión: passenger_stop_view
Ciclo: 1 · Fecha: 2026-11-03 · Agente: reviewer
Spec: `specs/passenger_stop_view/` v1.0 (APPROVED) · Rama: `feat/passenger_stop_view` (11 commits sobre `develop`)

## Veredicto: APPROVED

Los 23 AC tienen tests que verifican el comportamiento descrito; `CI=1 ./init.sh verify --e2e`
está en verde; las capturas cumplen `docs/design.md`. Ningún hallazgo es bloqueante. Hay una
contradicción entre `docs/conventions.md` §4 y AC-19 que la propia conventions resuelve a favor
de la spec: no bloquea, pero la persona debe actualizar `docs/` (CP-4).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `backend/tests/integration/test_cli_openapi.py` (4 tests) | OK | URL de BD apuntando a un fichero que se comprueba que no existe; sockets bloqueados por pytest-socket; comprueba que no se importa `avisabus.main`; salida estable (`indent=2`, claves ordenadas, salto final); funciona con `AVISABUS_ENV=prod` sin secreto. |
| AC-02 | `backend/tests/integration/test_openapi_snapshot.py` (4 tests) | OK | Compara la copia real del frontend; con una copia desfasada o ausente falla pidiendo `npm run gen:api`. La comparación es por valor JSON porque Prettier reformatea el fichero; es razonable. |
| AC-03 | `frontend/src/shared/api/__tests__/client.test.ts` (8 tests) | OK | 200 tipado, problem+json 404/503 → `status`/`type`, cuerpo no problem → `type: null`, error de red y timeout de 8 s con temporizadores falsos (el 7 999 ms no resuelve) → `ApiError(0,'network')`. |
| AC-04 | `StopPage.test.tsx` (es/ca), `e2e/stop-view.spec.ts:123` | OK | `h1` con `lang="ca-ES-valencia"`, "Parada 508", líneas sin duplicar, título `… · AvisaBus`, URL pedida con el token. |
| AC-05 | `destination.test.ts` (3 casos), `ArrivalRow.test.tsx`, `ArrivalsList.test.tsx` | OK | Frase accesible exacta del AC; destino visible del SAE y hablado del GTFS; los tres casos de la spec (tiempo real con y sin sentido, horario programado); parte visual con `aria-hidden`; orden de la API. |
| AC-06 | `ArrivalTime.test.tsx` | OK | "N min" (1/4/25), "Llegando"/"Arribant" con 0, `HH:MM` en Europe/Madrid. |
| AC-07 | `OccupancyInfo.test.tsx`, `ArrivalRow.test.tsx` | OK | Texto e icono (1/2/3/0 siluetas rellenas) en es/ca, `null` → "Ocupación no disponible", colores de §4 solo como refuerzo. |
| AC-08 | `ArrivalRow.test.tsx:91` | OK | N4: hora, sin ocupación ni silueta, sin botones ni enlaces. |
| AC-09 | `SourceNotice.test.tsx`, `ArrivalTime.test.tsx:63`, `ArrivalsList.test.tsx:27`, e2e | OK | `role="status"` con el texto literal (es/ca); "programado" en pantalla y en la frase de cada llegada. |
| AC-10 | `ArrivalsList.test.tsx:40` (es/ca), e2e | OK | |
| AC-11 | `shared/color/__tests__/contrast.test.ts`, `LineBadge.test.tsx` | OK | WCAG con tokens de §4, `#FE0000`→`#e50000` (≥ 4,5:1), oscurecimiento por pasos, respaldo negro/blanco, neutro con color nulo o inválido. |
| AC-12 | `StopPage.test.tsx:134,158,170` | OK | Nueva petición a los 20 s (no a los 19,999 s), tope de 30 s, la lista se conserva mientras la petición está pendiente (deferred), pausa con la pestaña oculta, petición inmediata al volver y reanudación. |
| AC-13 | `useServerNow.test.tsx`, `ArrivalTime.test.tsx` (`currentMinutes`), `StopPage.test.tsx:188` | OK | El test integrado pone el reloj del dispositivo 2 min adelantado: sin la corrección mostraría "2 min" y fallaría. Tic de 15 s comprobado en el límite. |
| AC-14 | `StopPage.test.tsx:211,257` | OK | "Actualizado a las 08:40:00"; el botón lanza la petición; "Datos actualizados" solo se anuncia cuando llega la respuesta (no mientras está pendiente); los refrescos automáticos no se anuncian. |
| AC-15 | `useArrivingAnnouncements.test.tsx` (10), `StopPage.test.tsx:234,257`, `StopPage.errors.test.tsx:195` | OK | Un anuncio educado con el headsign, sin repetirlo; silencio en los refrescos rutinarios y en los fallidos; solo la primera llegada de cada grupo. |
| AC-16 | `StopPage.errors.test.tsx:81,104,116`, e2e `:185` | OK | 404 de la parada o de las llegadas (es/ca); `main` sin `stop_id` ni token; sin token no se llama a la API; un 404 no se reintenta. |
| AC-17 | `StopPage.errors.test.tsx:126,151,171`, e2e `:207` | OK | 503 y error de red con "Reintentar" (tras 2 reintentos); datos conservados con "Datos de las 08:40, pueden no estar actualizados" (es/ca). |
| AC-18 | `useOnline.test.tsx`, `StopPage.errors.test.tsx:209,230`, e2e `:231` | OK | `role="status"`, ninguna petición en 120 s sin conexión, petición al volver; si se abre sin conexión no se llama a la API. |
| AC-19 | `lastStop.test.ts`, `StopPage.test.tsx:109,123`, `HomePage.test.tsx:58-101`, e2e `:249` | OK | Guarda `stop_id`, nombre y token al cargar (no tras un 404); enlace "Tu última parada: …" (es/ca) con la URL codificada. |
| AC-20 | `NotFoundPage.test.tsx`, e2e `:267` | OK | `/no-existe`, `/p`, `/p/508/otra`; el enlace lleva a la portada. |
| AC-21 | `src/__tests__/bundle-budget.test.ts` | OK | Cálculo comprobado con un `dist` sintético; en `test:bundle`, encadenado a `e2e`, se midió el `dist/` real: 138,73 KB gzip de un máximo de 200 KB. |
| AC-22 | `e2e/stop-view.spec.ts` | OK | Tiempo real, horario programado, sin llegadas y no encontrada × es/ca × iPhone 14, Pixel 7 e iPad landscape; axe con las etiquetas WCAG 2.1 A/AA sin violaciones. Hay axe también en error, sin conexión, portada y 404 genérico. |
| AC-23 | Capturas `frontend/test-results/passenger_stop_view/{iphone,pixel,tablet-landscape}/` | OK | Ver "Revisión visual". |

## Verificación ejecutada

`CI=1 ./init.sh verify --e2e` (puerto 4173 libre), código de salida 0, "verify: todo en verde":
- backend: format, lint, mypy y lint-imports OK (2 contratos respetados, 0 rotos); pytest 861 passed,
  6 deselected, cobertura 99,66 %.
- frontend: format, lint (con i18n) y typecheck OK; Vitest 35 ficheros y 278 tests passed; build OK
  (`index-*.js` 439,79 kB, 138,73 kB gzip).
- e2e + a11y: 60 passed y 0 reintentos (Playwright CI tiene `retries: 1`; no se usó ninguno).
  `test:bundle` 2 passed.
- harness: `feature_list.json` OK; trazabilidad AC→test OK.

Alcance (`git diff develop...HEAD --stat`): todo está dentro de los ficheros de `tasks.md` o es
soporte directo de los tests (`src/test/render.tsx`, `src/test/mockApi.ts`, fixtures). Los cambios de
`feature_list.json` y `progress/current.md`/`history.md` los hizo el orquestador. Los commits siguen
Conventional Commits con el ámbito de la feature y citan la tarea. No hay variables de configuración
nuevas.

### Revisión visual (AC-23)
Revisadas en los tres perfiles: `stop-realtime-es`, `stop-scheduled-ca`, `stop-error-stale-es`
(pixel), `stop-realtime-es-refresh-focused` (tablet), `stop-offline-es`, `stop-not-found-ca` y
`home-last-stop-es`. Comparadas con `docs/design.md`:
- §3: Atkinson Hyperlegible autoalojada (cero con barra). `h1` grande, `h2` "Próximas llegadas",
  rótulo "LÍNEAS" en mayúsculas `text-muted`, cifra del tiempo grande con "min" más pequeño,
  "hacia" en pequeño `text-muted` sobre el destino en negrita, "programado" pequeño bajo la hora.
- §4: insignias FREE, MEDIUM, FULL y `null` con sus fondos y textos. El rojo EMT está corregido; N4 lleva el
  estilo neutro.
- §5.2 y §5.3: distintivos con radio y tamaños de lista y tarjeta; tarjeta con borde, radio y la
  fila 1 (distintivo, destino, tiempo) y la fila 2 (insignia a todo el ancho); N4 sin fila 2.
- §5.4: icono de tres siluetas (relleno o contorno según el nivel) y "**Nivel** · asientos".
- §5.5: "Actualizar" y "Reintentar" como botones secundarios con icono a la izquierda y texto
  visible; foco de 3 px `accent` con separación.
- §5.6: avisos con fondo `accent-surface`, borde 2 px `accent`, icono de información y la primera
  frase en negrita.
- Principio 5: en la tablet el contenido se centra en una columna de unos 640 px.
- No vi desbordamientos ni texto cortado. "Ocupación media · hay asientos libres" pasa a dos
  líneas en el iPhone, lo cual es aceptable.

## Desviaciones declaradas por el implementer

1. **`openapi-typescript` 7.13 con TypeScript 6 mediante `overrides`**: cumple AC-03 y el design §2,
   que pide la generación con `openapi-typescript`. El override está limitado a ese paquete; los
   tipos generados están versionados, `tsc` los valida y el test de desfase protege el contrato.
   Es deuda técnica, no un problema de spec. **No bloqueante.** Recomendación: anotarlo en el
   design en la próxima revisión y quitar el override cuando haya una versión compatible con TS 6.
2. **Rojo EMT `#e50000` en vez de `#E40000`**: es lo que da el algoritmo del design §3 (pasos de
   5 puntos de L en HSL) y tiene 4,85:1 con blanco, por encima de 4,5:1. La guía §4 dice "en torno a
   `#E40000` (4,9:1)" y "no se fija ningún color de línea en el código". Cumple AC-11 y la guía.
   **No bloqueante**, no requiere CP-3. Si la persona quiere precisión, puede cambiar la guía a
   "`#E50000` (4,8:1)" (CP-4).
3. **Texto del aviso de horario programado**: el texto es comportamiento y en eso manda la spec
   (`docs/design.md` §1: "qué se muestra… con qué texto"), así que el literal de AC-09 es correcto.
   La negrita hasta los dos puntos respeta la intención de §5.6 (destacar el inicio). Cumple el AC y
   cabe en la guía. **No bloqueante.** Para que el ejemplo de §5.6 coincida con AC-09, se puede
   ajustar uno de los dos en una revisión futura; no hace falta CP-3.
4. **`avisabus.lastStop` en `localStorage` frente a `docs/conventions.md` §4**: **sí hay una
   contradicción** entre `docs/` y la spec. Conventions §4 dice que en `localStorage` solo se
   guardan `device_id`, idioma y perfil de accesibilidad. AC-19 obliga a guardar `stop_id`, nombre y
   token, y el design §3 fija la clave `avisabus.lastStop` y el uso de `safeStorage`. **No bloquea:**
   la cabecera de conventions establece que "si una convención entra en conflicto con una spec,
   manda la spec y se anota en `progress/`". El implementer lo anotó y la persona aprobó AC-19 en
   CP-1 con ese contenido explícito. Tampoco hay un problema de privacidad: el token de parada es
   el del QR público de la parada, no identifica al dispositivo ni a la persona, y no se registra en
   logs. **Basta con que la persona actualice `docs/conventions.md` §4 (CP-4).** Propuesta de
   texto: "solo `device_id`, idioma, perfil de accesibilidad y última parada consultada (`stop_id`,
   nombre y token), en `localStorage`, encapsulado en `shared/device`". No requiere CP-3.

## Decisiones locales revisadas

- **Anuncios de "llegando" (AC-15)**: interpretan "pase a" como una transición. (a) Solo se
  anuncian las llegadas `MINUTES`, coherente con AC-06. (b) No se anuncian los autobuses que ya
  llegaban cuando aparecen los primeros datos: no hay transición y la lista ya dice "está llegando".
  (c) Sin vehículo, si el grupo ya estaba llegando en la evaluación anterior no se repite, lo que
  cumple "una sola vez". Un mensaje con varias frases si llegan varios a la vez. Está dentro del AC
  y de la clave del design. Casos límite aceptables (no bloqueantes): sin `trip_id`, si un grupo
  oscila 0 → 1 → 0 entre respuestas se anunciaría dos veces, y si el autobús siguiente del mismo
  grupo pasa a primero ya a 0 min justo después, se callaría. Conviene que la persona valide (b)
  en CP-6 con lector de pantalla.
- **Cuenta atrás (AC-13)**: `ceil((arrival_at − ahora_servidor)/60 s)`, limitado a [0, `minutes` de la
  API]. Al recibir los datos se ve exactamente lo que dice la API y luego solo baja. Correcto.
  `useServerNow` recalcula el desfase con cada `generated_at` nuevo, como pide el design §3. El
  fichero se llama `useServerNow.ts` y no `useServerClock.ts` como en el árbol del design §2
  (tasks T-03 sí dice `useServerNow`). Diferencia de nombre sin impacto; **no bloqueante**.
- **Estado inicial de la conexión**: `onlineManager.setEventListener` toma `navigator.onLine` al
  arrancar (`shared/api/queryClient.ts:8-19`). Es necesario para AC-18 ("abierta sin conexión no
  llama a la API") porque TanStack Query v5 arranca siempre "en línea". El test la cubre.
  Correcto.
- **Dejar de refrescar tras un 404** (`useStopQueries.ts:45-48`): coherente con AC-16 (la parada no
  existe y la vista ya muestra "Parada no encontrada") y con `retry` del design. Evita peticiones
  inútiles. Correcto y cubierto (`StopPage.errors.test.tsx:104`).
- **El aviso de error no es región viva**: correcto. AC-15 prohíbe anunciar los refrescos
  automáticos, incluidos los fallidos, y ni AC-17 ni conventions §4 piden `role` para los errores.
  Ver el hallazgo N-1, un hueco de la spec relacionado.

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-1 (hueco de spec, accesibilidad)**, `frontend/src/features/passenger/stop/StopPage.tsx:75-78,117-133`:
  si la persona pulsa "Actualizar" y la petición falla, no se anuncia nada (`refresh()` solo anuncia
  si acierta), y el botón enfocado desaparece porque se sustituye por "Datos de las…". El foco cae al
  `body`. Lo mismo pasa con "Reintentar" cuando acierta, porque el aviso se desmonta. La spec no dice
  qué hacer tras una acción manual fallida ni dónde dejar el foco, así que el implementer no debía
  inventarlo. Propuesta para la próxima revisión de la spec, sin CP-3 urgente: anunciar de forma
  educada el fallo de una acción **manual** y conservar el foco (p. ej. mantener el botón en su
  sitio o mover el foco al aviso o a "Reintentar"). Que la persona lo pruebe en CP-6.
- **N-2**, `StopPage.tsx:101-111`: si falla solo la petición de la parada (503) y las llegadas
  cargan, el aviso dice "No se han podido cargar **las llegadas**" mientras se ven las llegadas, y
  como `useStop` no se refresca solo, el aviso sigue hasta pulsar "Reintentar". Es un caso raro y
  AC-17 se cumple. Se puede mejorar el texto o refrescar la parada junto con las llegadas.
- **N-3**, `frontend/src/shared/device/storage.ts:2`: el comentario dice que en `localStorage` solo
  hay `device_id`, idioma y perfil; desde AC-19 no es cierto. Hay que actualizarlo cuando la persona
  cambie conventions §4 (desviación 4).
- **N-4 (CP-4, `docs/`)**: actualizar `docs/conventions.md` §4 (desviación 4) y, si se quiere,
  `docs/design.md` §4 (`#E50000`, 4,8:1) y el ejemplo de §5.6 (desviación 3).
- **N-5**, `frontend/src/app/routes/HomePage.tsx:31`: repite a mano la conversión de idioma
  (`i18n.language === 'ca' ? 'ca' : 'es'`) en lugar de usar `useUiLanguage()`; y `StopHeader.tsx:24`,
  `StopNotFound.tsx:16` y `NotFoundPage.tsx:13` repiten las clases del `h1` que `StopPage.tsx:26` define
  como constante. Detalles de estilo.
- **N-6**, `backend/src/avisabus/adapters/inbound/http/app.py:43-50`: el documento exportado sale de
  `create_app(schema_only=True)`, no de la app real de `avisabus.main`. Hoy son iguales (solo están
  los routers de salud y paradas), pero si una feature futura registra routers solo en `main.py`, el
  test de AC-02 no lo detectaría. Recomendación para futuras features: registrar los routers siempre
  en `create_app`.
