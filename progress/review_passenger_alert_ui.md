# Revisión: passenger_alert_ui

## Revisión de la v1.1

Ciclo: 1 de la v1.1 · Fecha: 2026-11-09 · Agente: reviewer
Spec: `specs/passenger_alert_ui/` v1.1 (APPROVED, PR #45) · Rama: `feat/passenger_alert_ui-v1.1`, apilada
sobre `feat/realtime_events-v1.2` (PR #47). Diff revisado: `git diff origin/feat/realtime_events-v1.2..HEAD`
(commit de código 7bf4ab6; 7482463, c3e75db y 7c8c569 son de progreso).

## Veredicto: APPROVED

No hay hallazgos bloqueantes. `CI=1 ./init.sh verify --e2e` está en verde y AC-11 v1.1 se cumple en
tarjeta, aviso huérfano, otro autobús de la línea, otra línea y otra parada. Lo comprobé también
en navegador real (Chromium y WebKit), con un spec temporal en la copia del scratchpad: 30 de 30.
De 23 mutantes, 17 se detectan, 3 son equivalentes y 3 son huecos de test con el código correcto
(H-10, H-11 y el H-01 de la v1.0). El hueco de `alerts.snapshot` es una nota para la siguiente
versión de la spec, no un CP-3 (H-12).

## Matriz AC → evidencia

Solo T-09 cambia código. Los AC sin cambios conservan la evidencia de la v1.0 (abajo) y sus tests
siguen en verde en esta ejecución; donde cito mutantes, son de esta revisión.

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01, AC-02 | Los de la v1.0 | OK | El diff no toca identificador, perfil ni `apiSend` |
| AC-03 | Los de la v1.0 | OK, con hueco | V19 (quitar `can_alert`) sigue sobreviviendo: H-01 de la v1.0, abierto |
| AC-04 (v1.1: destino hablado en el título) | `RequestDialog.test.tsx:100` y `:132` (nombre accesible y `h2` con el headsign, es/ca) | OK | V23 (título con `sae_destination`) detectado: 5 fallos |
| AC-05 | Los de la v1.0; `StopPage.alerts.test.tsx:338` (carrera con el `POST`) | OK | V14 (sin anuncio tras el 201) y V15 (sin foco tras el 201) detectados |
| AC-06 (v1.1: sin `Retry-After`, N = 10) | Los de la v1.0; `client.test.ts:253` (cabecera ausente o inválida → `null`) | OK, con hueco | **V20 (`RATE_FALLBACK_MIN = 5`) sobrevive** → H-10 |
| AC-07, AC-08, AC-09, AC-10 | Los de la v1.0 | OK | El diff no toca su lógica; V16 y V17 confirman el foco de AC-09/AC-11 |
| AC-11 (v1.0) | `alertMessages.test.ts`, `alertsReducer.test.ts`, `AlertsProvider.test.tsx`, `StopPage.alerts.test.tsx:219-264` | OK | V16 y V18 detectados |
| AC-11 (v1.1, cierre y foco) | `StopPage.alerts.test.tsx:276` (`registered`, tarjeta), `:288` (`delivered`), `:302` (otro autobús), `:314` (huérfano), `:325` (no reaparece) | OK | V03, V04, V05, V06, V09, V10, V11 y V17 detectados. Spec temporal en navegador real: 3 perfiles |
| AC-11 (v1.1, guardas) | `StopPage.alerts.test.tsx:365-381` (otra línea, otra parada: mismo diálogo y foco en el título) | OK, con hueco | V01 y V02 detectados. Diálogo ya cerrado sin test: V07 sobrevive → H-11 |
| AC-11 (v1.1, "sin anuncio adicional") | `:276` (región vacía), `:288` (`textContent` exacto) | OK | V12 detectado |
| AC-12 | `e2e/alerts.spec.ts`, sin cambios | OK | 126 e2e en verde, axe sin violaciones |
| AC-13 | Sin cambios visuales en el diff | OK | No hay textos ni estilos nuevos; vale el cotejo de capturas de la v1.0 |

## Verificación ejecutada

- `git fetch`; puerto 4173 libre (`lsof` sin resultados).
- `CI=1 ./init.sh verify --e2e` → **exit 0, "verify: todo en verde"**:
  - backend: format, lint, types y architecture OK; pytest 1325 passed, 6 deselected.
  - frontend: format, lint y types OK; vitest 55 ficheros, 563 passed y 2 skipped (la v1.0 tenía
    555; son los 8 casos nuevos de T-09).
  - build + bundle y `test:bundle` (5 passed) OK.
  - e2e + a11y: 126 passed.
  - harness: `feature_list.json` y trazabilidad AC→test OK.
- Mutaciones en una copia de `frontend/` en el scratchpad, sin tocar el repositorio. Base de la
  copia: 563 passed, igual que el repositorio.
  - Detectados (17): V01–V06, V09–V12, V14–V18, V22 y V23.
  - Huecos de test (3): V07 (H-11), V19 (H-01 de la v1.0) y V20 (H-10).
  - Equivalentes (3):
    - V08: quitar la comparación de identidad de `registerDialog`. React ejecuta la limpieza del
      diálogo anterior antes del efecto del nuevo, así que no cambia nada.
    - V13: quitar la guarda `mounted` tras el `POST`, una línea anterior a la v1.1. Sin efecto
      visible: el `ref` ya es nulo y los `setState` se ignoran.
    - V21: `arrival.destination` es lo que devuelve `spokenDestination`. Lo sustituí por V23.
  - Descarté una primera tanda porque la base de la copia fallaba (287 tests): el enlace
    `frontend/node_modules/node_modules` (sin versionar) apunta en absoluto al repositorio y
    duplicaba React. Lo quité solo en la copia. Las 3 etiquetas que el script dio mal por un error
    de análisis (V01, V02 y V12) las repetí con el script corregido.
- Spec Playwright temporal en la copia (`e2e/zz-review.spec.ts`, sin versionar), 10 casos en los 3
  perfiles: **30 passed**. Cubre `registered` y `delivered`, otro autobús, huérfano, otra línea y
  otra parada con los dos eventos, evento propio antes del 201 y el hueco de la instantánea.
- `git status` después de la revisión: solo `qr/`, que ya estaba y se ignora por indicación.

## Decisiones del implementer (v1.1)

| Decisión | Valoración |
|---|---|
| Cierre por desmontaje sin `close()` | **Correcta.** Quitar un `<dialog>` modal lo saca de la capa superior sin evento `close`. En Chromium y WebKit el diálogo desaparece, el foco llega a "Cancelar solicitud" y `Shift+Tab` sigue recorriendo la página, así que no queda nada inerte. El cierre por el usuario sigue yendo por `close` (AC-04). |
| `registerDialog` en `useAlerts()` (`AlertsProvider.tsx:67`, `:254-260`; `RequestDialog.tsx:82-85`) | **Cabe; sin CP-3.** No está en el design §3, y el design §6 no lo lista como decisión local. Pero T-09 pide tocar justo esos ficheros, el design v1.1 no dice cómo sabe el proveedor que hay un diálogo abierto, es una ampliación interna y aditiva y no toca ningún contrato de API. Es el mismo caso que `requestButtonRef`, `statusRef` y D-1, aceptados en la v1.0. Ver H-13. |
| Bug corregido en `AlertAction` (`AlertAction.tsx:59`) | **Correcto y dentro de AC-11.** Un diálogo que reaparece al terminar la solicitud no se ha cerrado. Es la forma admitida de ajustar estado durante el render, y la condición evita el bucle. V10 lo confirma. T-09 incluye el fichero. |
| "Sin anuncio adicional" | **Lectura correcta.** `alert.delivered` tiene su anuncio propio en la primera frase de AC-11; "adicional" significa no añadir otro por cerrar el diálogo. Así lo fijan `:276` y `:288`. |
| Carrera con el propio `POST` | **Correcta, y no es un caso raro.** `alert_create` publica el evento antes de responder (design, orden de `execute`, paso 8), así que el evento puede llegar antes que el 201 en cualquier solicitud. El diálogo se cierra, el foco va a "Cancelar solicitud" y el 201 anuncia "Parada solicitada…" (AC-05). Comprobado en unitario y en navegador. Con `alert.delivered` antes del 201, los dos anuncios van seguidos y el segundo puede pisar al primero si caen en el mismo frame; es el `Announcer` de siempre y el estado queda en la tarjeta. |

## Comprobaciones de §4 de docs/verification.md

- **Contrato.** AC-11 v1.1 coincide. Interfaces de design §3 respetadas, salvo la ampliación
  `registerDialog` (H-13).
- **Tests.** Fake timers y `FakeWebSocket`, sin red. Citan el AC en el nombre. No son
  tautológicos, salvo los huecos señalados.
- **Privacidad.** El diff no añade registros, almacenamiento ni identificadores.
- **Accesibilidad.** Foco verificado en navegador. Anuncios como pide AC-11. Sin cambios visuales.
- **i18n.** Sin textos nuevos.
- **Arquitectura y backend.** El diff no toca `backend/`.
- **Alcance.** El código tocado es exactamente la lista de ficheros de T-09. Los demás cambios son
  `progress/` y `feature_list.json`, del orquestador y el implementer. Commits Conventional con
  ámbito y tarea.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **H-10 (tests, AC-06 v1.1).** La cláusula "sin `Retry-After`, N = 10" no tiene ningún test que la
  fije. Los casos de `RequestDialog.test.tsx:275-286` llevan siempre cabecera y
  `client.test.ts:253` se queda en `retryAfterS = null`. Por eso V20 (`RATE_FALLBACK_MIN = 5` en
  `RequestDialog.tsx:15`) sobrevive. El código es correcto: no bloquea, igual que H-01 de la v1.0
  (cláusula de un AC con otros tests, código correcto). Es el hueco más claro de esta versión, porque
  la cláusula es nueva en la v1.1 y T-09 no la cubría.
  - **Propuesta:** un caso más en `it.each`: 429 sin cabecera → "Inténtalo dentro de 10 minutos.".
    Conviene hacerlo en cuanto se reabra la rama.
- **H-11 (tests, AC-11).** Ningún test comprueba que, con el diálogo ya cerrado por "Volver" o
  Escape, un `alert.registered` de esa línea no mueva el foco. V07 (no deshacer el registro en
  `AlertsProvider.tsx:258`) sobrevive. El código es correcto.
  - **Propuesta:** abrir, "Volver", recibir el evento y comprobar que el foco sigue en "Solicitar"
    o en el elemento donde estaba.
- **H-12 (Problema de spec, nota para la próxima versión; no CP-3).** Con el diálogo abierto, si la
  solicitud llega por `alerts.snapshot` (reconexión o `GET /alerts/mine`, que pasa por el mismo
  `handleMessage`), el diálogo desaparece y el foco cae en `body`. Lo reproduje en los 3 perfiles.
  `arrived` solo se calcula para `registered` y `delivered` (`AlertsProvider.tsx:145-156`).
  - **Por qué no es CP-3.** AC-11 v1.1 enumera dos eventos sin ambigüedad y la spec no se contradice.
    El implementer no inventó nada y el comportamiento es el de la v1.0. No impide terminar la
    feature y exige coincidencia poco frecuente: diálogo abierto, socket caído y solicitud creada
    en ese intervalo. Tiene el mismo tratamiento que H-05, H-06 y H-07 de la v1.0.
  - **Otro desencadenante, sin otra pestaña** (por lectura del código): al recargar con una
    solicitud activa, la tarjeta ofrece "Solicitar" hasta que llega la primera instantánea. Si se
    pulsa en ese intervalo, pasa lo mismo. Con el `POST` en curso se corrige solo, porque el 201 mueve
    el foco.
  - **Impacto.** Pérdida de foco para teclado y lector de pantalla (RNF-03), sin pérdida de datos:
    la solicitud se ve en la tarjeta. El diálogo no reaparece (`AlertAction.tsx:59` no depende del
    evento).
  - **Propuesta para AC-11:** añadir `alerts.snapshot` a la condición ("…y llega `alert.registered`,
    `alert.delivered` o `alerts.snapshot` que contenga una solicitud de la misma parada y línea…"),
    sin anuncio. El cambio es pequeño, en `handleMessage`, y cubre también `GET /alerts/mine`.
    Conviene que la persona lo vea en el próximo checkpoint.
- **H-13 (design, próxima versión).** Añadir `registerDialog(stopId, line): () => void` a `useAlerts()`
  en el design §3, y una línea sobre el cierre sin `close()` en "Gestión del foco" (AC-11).
- **Siguen abiertos de la v1.0, fuera del alcance de T-09:** H-01 (confirmado de nuevo con V19),
  H-02, H-03 y H-04.

---

# Revisión de la v1.0 (conservada)

Ciclo: 1 · Fecha: 2026-11-05 · Agente: reviewer
Spec: `specs/passenger_alert_ui/` v1.0 (APPROVED) · Rama: `feat/passenger_alert_ui`, apilada sobre
`feat/alert_expiry` (PR #43). Diff revisado: `git diff origin/feat/alert_expiry...HEAD`
(commits 5504833, 72af4b8, f1351d9, 1e8745b, b93a1a8, ad91f69, ea41214 y 3b4038b, más los de progreso).

## Veredicto: APPROVED

No hay hallazgos bloqueantes. `CI=1 ./init.sh verify --e2e` está en verde y los 13 AC tienen tests
que verifican el comportamiento. Hice 28 mutaciones en una copia del scratchpad: 25 se detectan y
3 sobreviven. Las 3 son huecos de test con el código correcto y no bloquean, como el precedente
H-02 de `position_estimation`: H-01 (`can_alert = false`, AC-03), H-02 (filtro por parada, AC-08)
y H-03. Las decisiones D-1…D-12 caben en la spec y el design; ninguna necesita CP-3. Hay dos
puntos de spec menores para la siguiente versión o para CP-6 (H-06 y H-07).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `deviceId.test.ts` (4: `randomUUID`, reutiliza, reemplaza inválido, en memoria sin almacenamiento); `client.test.ts` `apiSend` (cabecera en POST, DELETE y GET, nunca en URL ni cuerpo); `usePassengerSocket.test.tsx` (URL sin id, `hello` con id); e2e `expectPrivateAndLocal` (ninguna URL lleva el id; `X-Device-Id` igual al del `hello`) | OK | Mutantes M02 (id en la URL del WS), M14 (sin caché en memoria) y M19 (sin cabecera) detectados |
| AC-02 | `needsProfile.test.ts` (7), `NeedsPage.test.tsx` (4 casillas en orden, "Guardar", "Borrar", `localStorage`, anuncio educado, sin `fetch`; es/ca), `HomePage.test.tsx` (enlace `/necesidades` es/ca); e2e "Mis necesidades" (persiste tras recargar, precarga en el diálogo, axe) | OK | M20 (sin anuncio) detectado |
| AC-03 | `AlertAction.test.tsx` (nombre accesible es/ca, "Ya has solicitado otro autobús…", otra parada, otro `service_date`); e2e de solicitud (48 px) | OK, con hueco | M23 (`alertFor` sin parada) y M25 (sin `service_date`) detectados. **M12 (quitar `arrival.can_alert`) sobrevive** → H-01 |
| AC-04 | `RequestDialog.test.tsx` (`showModal`, título enfocado, hora, casillas precargadas, "Recordar" desmarcada, "Volver" y Escape devuelven el foco, reapertura rápida); e2e de teclado (Tab/Shift+Tab dentro del diálogo, Escape, "Volver", foco de vuelta) | OK | M07 (título sin foco) y M09 (sin foco de vuelta) detectados |
| AC-05 | `RequestDialog.test.tsx` (cuerpo del POST con el viaje de la tarjeta y las necesidades marcadas, "Enviando…" desactivado, 201 y 200, anuncio, foco en "Cancelar solicitud", "Recordar" guarda el perfil); e2e de solicitud | OK | M16 (ignorar "Recordar") detectado |
| AC-06 | `RequestDialog.test.tsx` (422, 429 con 125/60/1 s, 404, 503 y red; `role="alert"` enfocado; reintento; 429 en valenciano; 422 invalida `['arrivals', stopId]`); `StopPage.alerts.test.tsx` (422 → segunda petición de llegadas); `client.test.ts` (Retry-After); e2e 429 | OK | M08 (`floor`), M17 (sin refresco) y M18 (error sin foco) detectados |
| AC-07 | `AlertAction.test.tsx` (PENDING_DRIVER y DELIVERED es/ca, "Has indicado: rampa y asiento" / "rampa i seient", sin necesidades, "Ver en el mapa" encima); `alertMessages.test.ts` | OK | M22 (estado cambiado) detectado |
| AC-08 | `StopPage.alerts.test.tsx` (aviso encima de la lista con línea, destino `lang`, estado, necesidades y "Cancelar"; no se repite si la tarjeta existe; valenciano); e2e de solicitud huérfana | OK, con hueco | **M13b (`alertsAt` sin filtro de parada) sobrevive** → H-02 |
| AC-09 | `StopPage.alerts.test.tsx` (DELETE sin diálogo y con `X-Device-Id`; 204 → "Solicitud cancelada" y foco en "Solicitar"; 404 → "La solicitud ya no estaba activa"; sin tarjeta → foco en el `h2`; red → anuncio y foco mantenido); e2e de cancelación | OK | M10 (404 como red), M15 (sin foco al `h2`) y M26 (quitarla con error de red) detectados |
| AC-10 | `reconnect.test.ts` (1, 2, 4, 8, 16, 30 s, ±20 %); `usePassengerSocket.test.tsx` (`hello`, `pong`, marcos inválidos, **reconexión con 1000, 1001, 1006, 1011, 1012, 1013, 4400, 4408 y 4429**, secuencia de esperas, reinicio tras la instantánea, jitter, sin red, cierre al desmontar); `AlertsProvider.test.tsx` (sondeo cada 30 s con cabecera, no con conexión, no sin red, fallo); `StopPage.alerts.test.tsx` (WS al abrir la parada) | OK | M01 (no reconectar con 1001/1012), M03, M04, M05, M06 y M21 detectados |
| AC-11 | `alertMessages.test.ts` (tres motivos, silencio con registered/cancelled/snapshot/ping); `alertsReducer.test.ts`; `AlertsProvider.test.tsx` y `StopPage.alerts.test.tsx` (anuncios, foco a "Solicitar" o al `h2`, foco ajeno intacto, cancelación silenciosa); e2e de caducidad | OK | M11 (anunciar registered) detectado |
| AC-12 | `e2e/alerts.spec.ts`: 13 tests por perfil (iphone, pixel, tablet-landscape) = 39, es y ca, `page.route` + `page.routeWebSocket`, axe WCAG 2.1 A/AA en botones, **diálogo abierto**, tarjeta solicitada, caducidad, 429, huérfana y "Mis necesidades"; `expectPrivateAndLocal` (solo el origen propio) | OK | 126/126 e2e en verde |
| AC-13 | Capturas `frontend/test-results/passenger_alert_ui/<perfil>/*.png` (regeneradas en esta ejecución, 08:46) cotejadas con `docs/design.md` §5.3, §5.5, §5.8, §6 y §7 | OK | Detalle abajo; observaciones visuales H-07 y H-08 para CP-6 |

### AC-13: cotejo de capturas

Revisé `stop-request-buttons`, `dialog-open`, `card-requested`, `card-expired`, `dialog-error-429`,
`orphan-request` y `needs-page` en pixel, iphone y tablet-landscape, en es y ca.

- **§5.3 / §5.8, fila de acciones.** "Ver en el mapa" (secundario, icono de mapa) y "Solicitar"
  (principal, icono de mano, texto visible) van a partes iguales y miden 48 px. El 70 sin sentido no
  tiene fila 3 y el N4 (fuera de red) tampoco.
- **§5.8, estado en la tarjeta.** Caja `accent-surface` con borde 2 px `accent` e icono de
  comprobación. "**Parada solicitada.**" va en negrita y el detalle en normal. "Has indicado: rampa y
  asiento" va en `text-muted`. "Cancelar solicitud" es secundario, a ancho completo y de 48 px, y
  "Ver en el mapa" queda encima de la caja.
- **§5.8, otro autobús.** El texto `text-muted` de 15 px sustituye al botón.
- **§5.8, diálogo.** En móvil es una hoja inferior con radio superior y telón oscuro. En tablet es
  una caja centrada de ≤ 480 px. Título de 22 px en 700; casillas de 24 px en filas ≥ 48 px;
  "Solicitar parada" (principal) encima de "Volver" (secundario), a ancho completo. El error 429 va
  con fondo y texto `occ-full` y borde de 2 px.
- **§5.8, Mis necesidades.** "Guardar" es principal y "Borrar mis necesidades" secundario.
- **§7, terminología.** "Solicitar" / "Sol·licita", "Parada solicitada" y "Cancelar solicitud". El
  nombre accesible incluye línea y destino.

## Verificación ejecutada

- Puerto 4173 libre (`lsof -i :4173` sin resultados).
- `CI=1 ./init.sh verify --e2e` → **exit 0, "verify: todo en verde"**:
  - backend: format, lint, types y architecture OK. pytest: 1325 passed, 6 deselected. Cobertura
    99,59 %. El aviso de `socket.socket` es el test intencionado `test_no_network.py`.
  - frontend: format, lint (incluido i18n) y types OK. vitest: 55 ficheros, 555 passed y 2 skipped.
  - build + bundle: `index-*.js` 146,92 KB gzip y `MapPage-*.js` 50,23 KB gzip. `test:bundle` 5
    passed.
  - e2e + a11y: **126 passed** (39 de `alerts.spec.ts`).
  - harness: `feature_list.json` y trazabilidad AC→test OK.
- Mutaciones, hechas en una copia de `frontend/` en el scratchpad (sin tocar el repositorio):
  28 mutantes, 25 detectados y 3 que sobreviven (M12, M13b y M24; ver H-01…H-03). Un primer M13
  sobrevivió por la misma causa que M13b, y M04 se repitió con un patrón exacto (detectado).
- `git status` limpio después de la revisión.

## Decisiones D-1…D-12 (de `progress/impl_passenger_alert_ui.md`)

| D | Valoración |
|---|---|
| D-1 `apiSend` acepta `GET` (`client.ts:52`) | **Cabe.** El design §1 exige el respaldo `GET /alerts/mine`, y `alert_create.AC-05` obliga a enviar `X-Device-Id` en él. AC-01 permite el identificador solo en esa cabecera, así que hace falta un camino HTTP que la lleve. Ampliar el tipo de `method` es compatible: el contrato de la API no cambia y la firma del design queda contenida en la nueva. Propuesta para la próxima versión del design §3: `'GET' \| 'POST' \| 'DELETE'`. Sin CP-3. |
| D-2 `ApiError.retryAfterS` | **Cabe.** El design dice "mismos errores que apiGet" y "para 429 rellena retryAfterS". Llevar el dato en el error es la única forma coherente de cumplir las dos cosas. |
| D-3 429 sin `Retry-After` → 10 min (`RequestDialog.tsx:15`) | **Cabe como defensa.** `alert_create.AC-08` siempre envía `Retry-After` en segundos, así que con nuestro backend el caso no se da. Los 10 min son la ventana por defecto de ese AC, no un valor inventado. Ver H-06. |
| D-4 Otros estados del POST → mensaje de red; otros del DELETE → red | **Cabe.** AC-06 y AC-09 no enumeran 400/500. El 400 (`invalid-device-id`) no puede darse con un UUID v4 válido. |
| D-5 Sin sondeo sin conexión (`AlertsProvider.tsx:159`) | **Cabe.** AC-10 ya prohíbe reconectar sin red, y `passenger_stop_view.AC-18` obliga a no reintentar hasta recuperarla. "Desconectada" se lee como "socket caído con red"; sin red, el `fetch` fallaría igual. Las dos specs se armonizan y ninguna se contradice. |
| D-6 `connected` desde la instantánea | **Cabe.** Coincide con el design ("reset del contador tras snapshot"). Evita dejar de sondear con un socket abierto que nunca entrega estado. |
| D-7 "Ya has solicitado…" solo con `can_alert` | **Cabe.** AC-03 dice "en lugar del botón", y sin `can_alert` no hay botón que sustituir. |
| D-8 Anuncios de otras paradas; caducidad desconocida sin anuncio | **Cabe.** AC-11 no filtra por parada y el estado es del dispositivo (`alert_create.AC-10/11`, "en todas las paradas"). Sin la línea no se puede componer el texto de AC-11, así que callar es lo único posible. |
| D-9 Huérfana = sin llegada en red del mismo viaje | **Cabe.** Es coherente con AC-07, que pinta el estado solo en tarjetas en red. Va "encima de las llegadas". Ver H-03 sobre su test. |
| D-10 `shared/ws` importa de `features/` (`usePassengerSocket.ts:3-6`) | **Cabe; no bloquea.** El design §3 define `PassengerMessage` en `alertsReducer.ts` y la firma de `usePassengerSocket` la usa, así que la dependencia del tipo viene del propio design. Importar también el validador va algo más allá (H-04). No hay regla de lint de fronteras en el frontend; `lint-imports` es solo del backend. |
| D-11 e2e de otras features (`stop-view.spec.ts:76`, `map-view.spec.ts:90`) | **Cabe.** Es consecuencia directa de esta feature: la vista de parada abre ahora `/ws/passenger`, y sin la ruta simulada `vite preview` lo reenviaría al backend, en contra de "sin red". Son dos líneas que no cambian ninguna aserción. El cambio de `src/test/mockApi.ts` (cabeceras, `init`, `text()`) es infraestructura de test compatible. |
| D-12 `Alt+Tab` en WebKit | **Cabe.** Es la forma estándar de recorrer botones y casillas en WebKit/Safari sin "Acceso total con teclado". Chromium (pixel) usa Tab, y el e2e de teclado pasa en los tres perfiles. |

Otras decisiones locales revisadas:
- Escape bloqueado durante el envío (`RequestDialog.tsx:111`).
- "Recordar" desmarcada por defecto.
- `CheckIcon` (pedido por §5.8).
- `ref` en `Button`.
- `h2[tabindex=-1]:focus` sin contorno (`index.css:53`), coherente con el `h1` previo; no son controles.

Todas caben en el design §6.

## Comprobaciones de §4 de docs/verification.md

- **Contrato.** Interfaces de design §3 respetadas: `getDeviceId`, `needsProfile`, `apiSend`
  (ampliado, D-1), `nextDelayMs`, `usePassengerSocket`, `alertsReducer` y `useAlerts`. La
  correspondencia tarjeta ↔ solicitud usa `trip_id` + `service_date`.
- **Reconexión.** `ws.onclose` reprograma la conexión sea cual sea el código: no hay rama por
  código. Está probado con 1000, 1001, 1006, 1011, 1012, 1013, 4400, 4408 y 4429, y M01 lo confirma.
- **Privacidad.**
  - El `device_id` solo viaja en `X-Device-Id` (`client.ts:143`) y en el `hello`
    (`usePassengerSocket.ts:45`). Nunca va en una URL, se pinta o se registra: no hay `console.*`
    nuevo.
  - Las necesidades solo viajan en el cuerpo del `POST /alerts`. Ni el `hello` ni el `DELETE` ni la
    página de necesidades llaman a la API con ellas (el e2e comprueba que no hay llamadas `/api/`).
  - `localStorage` tiene solo `avisabus.deviceId`, `avisabus.language`, `avisabus.needsProfile` y
    `avisabus.lastStop`, exactamente lo de `docs/conventions.md` §4. Todo pasa por
    `shared/device/storage.ts`.
  - Las solicitudes activas viven solo en memoria. No hay persistencia de TanStack Query ni caché
    del service worker para `/api` (`navigateFallbackDenylist`, sin `runtimeCaching`).
- **Accesibilidad.**
  - `<dialog>` con `showModal` y `aria-labelledby`. El foco empieza en el título, vuelve a
    "Solicitar" al cerrar sin solicitar y va a "Cancelar solicitud" tras solicitar.
  - El error es un `role="alert"` enfocado.
  - Anuncios educados con el `Announcer` compartido.
  - Cuando desaparece un control, el foco pasa a "Solicitar" o al `h2`.
  - axe sin violaciones (también con el diálogo abierto) en los tres perfiles.
  - Objetivos ≥ 48 px comprobados en el e2e.
  - Información con texto e icono.
- **i18n.** Hay 48 claves nuevas, con paridad total es/ca (comprobada por script, sin claves
  huérfanas). Los textos en castellano coinciden literalmente con AC-02…AC-11. El valenciano sigue
  la referencia del design §4; la única variante es "Sol·licita la parada", ya anotada para CP-6.
  `Intl.ListFormat` da "rampa y asiento" / "rampa i seient".
- **Tests.** Los tests unitarios no usan red: `FakeWebSocket` global en `setup.ts` y `fetch`
  simulado. Usan temporizadores falsos. Los e2e usan `page.route` y `page.routeWebSocket`, sin
  `waitForTimeout`.
- **Alcance.**
  - Solo cambian los ficheros de design §2.
  - Se añaden `spokenTime.ts` (extracción sin cambio de comportamiento, cubierta por los tests de
    `passenger_stop_view`), `CheckIcon.tsx` y el `ref` de `Button`.
  - Infraestructura de test: `FakeWebSocket`, `setup.ts`, `mockApi.ts` y fixtures.
  - Las dos líneas de D-11.
  - Los commits de progreso son del orquestador.
  - No se tocan `backend/`, `specs/` ni `docs/`.
- **Convenciones.** Conventional Commits con ámbito `passenger_alert_ui` y tarea citada. Nombres
  según el glosario: `Alert`, `Need`, `device_id`.

## Hallazgos

### Bloqueantes

Ninguno.

### No bloqueantes

- **H-01 (tests, AC-03).** No hay ninguna tarjeta con `can_alert = false` que tenga vehículo y
  sentido. Por eso el mutante que quita `arrival.can_alert` de
  `frontend/src/features/passenger/stop/ArrivalRow.tsx:113` sobrevive a toda la suite, unitaria y
  e2e. En el fixture `arrivals-realtime`, los únicos `can_alert = false` son el 70 sin vehículo y el
  N4 fuera de red, y `AlertAction` devuelve `null` para ellos por otro motivo. El código es correcto.
  Pero la cláusula "con `can_alert = false` no DEBERÁ mostrarlo" no está fijada, y es el caso real
  de un autobús a más de 30 min (`alert_create.AC-01`).
  - **Propuesta:** en `AlertAction.test.tsx`, una llegada en red con `vehicle` y `direction_id` pero
    `can_alert: false`, comprobando que no hay botón ni "Ya has solicitado…".
  - Recomiendo hacerlo en este ciclo si se reabre la rama por cualquier otro motivo.
- **H-02 (tests, AC-08).** El test "shows above the arrivals a request whose bus is no longer in
  the list" (`StopPage.alerts.test.tsx:111` y `:130`, "Only requests of this stop") no discrimina
  el filtro por parada. La solicitud de otra parada (`stop_id: '1234'`) hereda `trip_id: '12345'`,
  que coincide con una tarjeta visible, así que tampoco se pintaría aunque se ignorase la parada.
  Por eso el mutante `alertsAt: (_stopId) => all` (`AlertsProvider.tsx:245`) sobrevive.
  - **Propuesta:** dar a esa solicitud un `trip_id` que no esté en la lista.
- **H-03 (tests, D-9).** Tampoco hay test de que una solicitud cuyo viaje solo aparece en una
  llegada **fuera de red** se muestre como huérfana. El mutante que quita
  `.filter((arrival) => arrival.in_network)` (`OrphanAlerts.tsx:21`) sobrevive. Es un caso límite
  (el SAE no daría un viaje GTFS fuera de red), así que solo lo anoto.
- **H-04 (organización, D-10).** `shared/ws/usePassengerSocket.ts:3-6` importa en tiempo de
  ejecución `parsePassengerMessage` desde `features/passenger/alerts/`. El design obliga a la
  dependencia del tipo, pero no a la del validador. Hay dos alternativas para una refactorización
  futura (no en este ciclo, fuera de alcance):
  - mover el tipo y el validador a `shared/ws/`;
  - pasar el validador como parámetro.
- **H-05 (comportamiento no especificado).** Si con el diálogo abierto llega `alert.registered` de
  la misma línea (otra pestaña), `AlertAction` se sustituye por el estado o por "Ya has
  solicitado…". El diálogo se desmonta y el foco cae en `body`. AC-11 solo regula el foco cuando
  *desaparece* una solicitud. Es un caso raro y la spec no lo cubre, así que no hay incumplimiento.
  Lo anoto como hueco de spec para la próxima versión.
- **H-06 (Problema de spec, menor).** AC-06 no dice qué mostrar en un 429 sin `Retry-After`
  utilizable (D-3). La implementación usa la ventana de `alert_create.AC-08` (10 min). Propuesta
  para la v1.1: fijarlo en la spec.
- **H-07 (Problema de spec / CP-6).** La spec no fija qué destino lleva el **título visible** del
  diálogo. Usa el destino hablado (headsign GTFS, "Passeig Marítim - Hospital Malva-rosa", con
  `lang`) en `RequestDialog.tsx:128`, mientras la tarjeta muestra el texto del SAE ("Pass.
  Marítim"). AC-04 da el mismo patrón que AC-03 y el título es también el nombre accesible del
  diálogo, así que la elección es razonable. Pero `docs/design.md` §7 dice "en pantalla, el texto
  del SAE". La persona debería decidirlo en CP-6. Mismo caso en el aviso de solicitud huérfana, que
  usa `alert.destination` porque no hay texto del SAE.
- **H-08 (visual, CP-6).** En los perfiles móviles (pixel, iphone) "Ver en el mapa" / "Mostra en
  el mapa" se parte en dos líneas al compartir la fila con "Solicitar" a partes iguales. Lo mismo
  pasa junto a "Ya has solicitado…". Sigue midiendo ≥ 48 px y cumple §5.3, pero la persona debería
  valorarlo en CP-6.
- **H-09 (visual, menor).** En la captura `pixel/dialog-open-*` se ve una pista de barra de
  desplazamiento en el borde derecho de la hoja (`max-h-[90dvh] overflow-y-auto`,
  `RequestDialog.tsx:119`): el contenido roza el 90 % del alto. No afecta al uso; es para CP-6.
