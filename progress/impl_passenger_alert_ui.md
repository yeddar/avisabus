# Implementación: passenger_alert_ui
Spec: specs/passenger_alert_ui/ (v1.1, APPROVED, PR #45) · Ciclo de revisión: 0 de la v1.1 · Rama:
`feat/passenger_alert_ui-v1.1` (apilada sobre `feat/realtime_events-v1.2`, PR #47). La v1.0 (PR #37) se
hizo en `feat/passenger_alert_ui`. Exploración: no necesaria (tasks.md).

## Estado
T-01 a T-09 terminadas. `CI=1 ./init.sh verify --e2e` en verde (ver "Verificación"). Sin bloqueos de
T-09; un hueco de spec anotado en "Bloqueos" para decidir aparte.

## Tareas
- [x] T-01 `getDeviceId`, perfil de necesidades, `apiSend` con `X-Device-Id` y `Retry-After` (commit 5504833)
- [x] T-02 `NeedsFieldset`, `NeedsPage` (`/necesidades`) y enlace en la portada (commit 72af4b8)
- [x] T-03 Reconexión, `usePassengerSocket`, `alertsReducer`, `alertMessages`, `AlertsProvider` (commit f1351d9)
- [x] T-04 `AlertAction`, `AlertStatus`, `HandIcon` y fila de acciones de `ArrivalRow` (commit 1e8745b)
- [x] T-05 `RequestDialog` (commit b93a1a8)
- [x] T-06 Integración en `StopPage`: `AlertsProvider`, `OrphanAlerts`, cancelación, anuncios y foco (commit ad91f69)
- [x] T-07 E2E con API y WebSocket simulados, axe y capturas (commit ea41214)
- [x] T-09 (v1.1) Con el diálogo abierto, `alert.registered`/`alert.delivered` de la misma parada y línea lo cierra y lleva el foco a "Cancelar solicitud" (commit 7bf4ab6)
- [x] T-08 Verificación completa (este fichero; repetida para la v1.1)

Tests escritos antes del código y vistos en rojo en todas las tareas, salvo `AlertsProvider.test.tsx`
(T-03), escrito justo después del proveedor: se comprobó con dos mutaciones temporales, ya revertidas
(sondeo también con conexión → 1 fallo; sin mover el foco al quitar una solicitud → 2 fallos).

Ficheros de test por AC: `deviceId.test.ts`, `client.test.ts` (AC-01); `needsProfile.test.ts`,
`NeedsPage.test.tsx`, `HomePage.test.tsx` (AC-02); `AlertAction.test.tsx` (AC-03, AC-07);
`RequestDialog.test.tsx` (AC-04–AC-06); `StopPage.alerts.test.tsx` (AC-06, AC-08, AC-09, AC-10, AC-11);
`reconnect.test.ts`, `usePassengerSocket.test.tsx`, `AlertsProvider.test.tsx` (AC-10, AC-11);
`alertsReducer.test.ts`, `alertMessages.test.ts` (AC-07, AC-10, AC-11); `e2e/alerts.spec.ts` (AC-02–AC-06,
AC-08, AC-09, AC-11, AC-12, AC-13).

## Decisiones locales
(Dentro de design §6: maquetación no fijada por `docs/design.md`, redacción y WebSocket simulado.)
- **WebSocket simulado:** `src/test/FakeWebSocket.ts`, instalado como `WebSocket` global en
  `src/test/setup.ts` para **todos** los tests unitarios (ningún componente puede abrir un socket real).
  En `setup.ts` también un `showModal`/`close`/Escape mínimo para jsdom (design §5).
- **Diálogo:** hoja inferior a ancho completo en móvil y caja centrada de 480 px desde 640 px (`sm:`);
  `max-h-[90dvh]` con desplazamiento. Los botones "Solicitar parada" y "Volver" se desactivan mientras
  se envía, y Escape no cierra durante el envío (se perdería la respuesta).
- **Casilla "Recordar…"** desmarcada al abrir (no se cambia el perfil salvo que la persona lo pida).
- **Hora en el diálogo:** "El autobús {{time}}." con la misma frase hablada de la tarjeta ("llega en 4
  minutos", "está llegando", "llega a las 08:52 según el horario programado"); se extrajo a
  `stop/spokenTime.ts` y `ArrivalRow` la usa (sin cambio de comportamiento).
- **Título del diálogo y aviso de solicitud huérfana** con el destino hablado (headsign GTFS), igual
  que el nombre accesible de AC-03 y el `h1` del mapa, marcado con `lang` de valenciano.
- **Estado en la tarjeta:** `PENDING_DRIVER` → "**Parada solicitada.** Aún no hay…"; `DELIVERED` →
  "**El conductor ha recibido tu solicitud.**"; sin necesidades no se pinta "Has indicado:".
- **Icono de comprobación** (`shared/ui/icons/CheckIcon.tsx`) para la caja de estado (lo pide
  `docs/design.md` §5.8; no está en la lista de ficheros del design §2). `Button` acepta `ref`.
- **"Cancelar solicitud"** sin icono; no se desactiva durante la petición (perdería el foco); las
  pulsaciones repetidas se ignoran mientras hay una en curso.
- **Anuncios:** todos educados (`polite`), también "No se ha podido cancelar la solicitud".
- **Foco:** los destinos programáticos `h2[tabindex=-1]` (título del diálogo y "Próximas llegadas")
  no muestran contorno, como ya pasaba con el `h1` (`src/index.css`).
- **Reapertura rápida:** cada apertura del diálogo es una instancia nueva (`key`); el evento `close`
  del diálogo anterior, que el navegador entrega en una tarea posterior, ya no cierra el nuevo
  (detectado en el e2e de teclado; test unitario en `RequestDialog.test.tsx`).

### v1.1 (T-09)
AC-04 (título con destino hablado) y AC-06 (429 sin `Retry-After` → 10 min) ya estaban implementados
(ver arriba y D-3); la v1.1 solo añade código para AC-11. No hay textos nuevos.
- **Cierre del diálogo:** no se llama a `close()`. Al llegar la solicitud, las tarjetas dejan de ofrecer
  "Solicitar" y `RequestDialog` se desmonta, lo que lo saca de la capa superior sin evento `close` (que
  devolvería el foco a "Solicitar"). `RequestDialog` avisa al proveedor con `registerDialog(stopId, line)`
  (ampliación de `useAlerts`) y este mueve el foco con el mismo mecanismo que AC-05 y AC-09.
- **`AlertAction` olvida el diálogo** cuando la tarjeta pasa a "Ya has solicitado otro autobús…": si
  no, reaparecía al terminar esa solicitud (lo mostró el test en rojo).
- **"Sin anuncio adicional":** `alert.registered` no anuncia nada y `alert.delivered` mantiene su anuncio
  propio de AC-11; el cierre del diálogo no añade ninguno.
- **Evento de la propia solicitud antes de la respuesta del `POST`:** se trata igual (diálogo cerrado,
  foco en "Cancelar solicitud"); al llegar el `201` se anuncia "Parada solicitada…" (AC-05).
- **Comprobación en navegador real:** AC-11 se verifica con tests unitarios, y T-09 no incluye e2e. El
  foco tras quitar un `<dialog>` modal se comprobó con un spec Playwright temporal, no versionado (tarjeta
  y aviso huérfano, en los 3 perfiles: 6 passed).
- **Tests:** 6 en rojo antes del cambio. Los 2 casos de guarda (otra línea, otra parada) pasan
  también antes, porque el diálogo ya seguía abierto; se comprobaron con dos mutaciones temporales,
  ya revertidas (sin filtro de parada → 1 fallo; sin filtro de línea → 1 fallo).

## Desviaciones y huecos menores (resueltos sin cambiar contratos; a confirmar en la revisión)
- **D-1 `GET /alerts/mine` necesita `X-Device-Id`** (`alert_create.AC-05`) pero el design §3 limita
  `apiSend` a `'POST' | 'DELETE'`. `apiSend` admite también `'GET'` para el respaldo; el identificador
  sigue viajando solo en la cabecera (AC-01). Alternativa si se prefiere: una opción en `apiGet`.
- **D-2 `apiSend` y los errores:** lanza `ApiError` como `apiGet` (design: "mismos errores"); para el
  429, `ApiError.retryAfterS` lleva los segundos de `Retry-After`. El resultado de éxito también trae
  `retryAfterS` (normalmente `null`). Se aceptan solo segundos enteros; una fecha HTTP da `null`.
- **D-3 429 sin `Retry-After` utilizable:** se muestran 10 minutos (`RATE_FALLBACK_MIN`, la ventana
  por defecto de `alert_create.AC-08`). N se redondea hacia arriba con un mínimo de 1.
- **D-4 Otros estados del `POST`** (400, 500…) muestran el mensaje de red de AC-06; en el `DELETE`,
  cualquier error que no sea 404 se trata como error de red (AC-09).
- **D-5 Respaldo `GET /alerts/mine`:** cada 30 s mientras el socket no está conectado (la primera, a
  los 30 s), **pero no sin conexión de red**: `passenger_stop_view.AC-18` exige no llamar a la API sin
  conexión (lo detectó su test). Una respuesta que llega con el socket ya conectado, o después de un
  alta o cancelación local, se descarta.
- **D-6 `connected`** pasa a verdadero con la instantánea (no al abrir el socket). Al volver la red se
  reconecta en el acto; los temporizadores de espera se reinician con cada instantánea.
- **D-7 AC-03 "las demás tarjetas de la línea":** el texto "Ya has solicitado otro autobús…" sustituye
  al botón, así que solo aparece en tarjetas con `can_alert = true`.
- **D-8 AC-11 caducidad de una solicitud desconocida** (no está en el estado): no se anuncia, porque
  no se sabe su línea. Se anuncian eventos de solicitudes de cualquier parada del dispositivo (AC-11 no
  filtra por parada); solo se pintan las de la parada abierta.
- **D-9 Solicitud huérfana** = solicitud de esta parada sin ninguna llegada **en red** del mismo
  `trip_id` y `service_date`. Solo se calcula cuando hay llegadas cargadas. Va justo después de la fila
  "Actualizado a las…", antes del aviso de horario programado y de la lista.
- **D-10 `shared/ws/usePassengerSocket.ts` importa `PassengerMessage` y el validador de
  `features/passenger/alerts/alertsReducer.ts`**, como dice el design §3 (shared → feature).
- **D-11 Specs de otras features tocadas por "sin red":** `e2e/stop-view.spec.ts` y
  `e2e/map-view.spec.ts` añaden `page.routeWebSocket('**/ws/passenger', () => {})`: la vista de
  parada abre ahora el WebSocket y `vite preview` lo reenviaría a `localhost:8000`. `src/test/mockApi.ts`
  admite cabeceras de respuesta y `text()`.
- **D-12 Teclado en WebKit:** el e2e de foco usa `Alt+Tab` en WebKit (iPhone, iPad), que solo recorre
  botones y casillas así (como Safari sin "Acceso total con teclado"); Tab en Chromium.

## Textos nuevos (para revisión de la persona en CP-6)
| Clave | es | ca-valencia |
|---|---|---|
| `home.needsLink` | Mis necesidades | Les meues necessitats |
| `alert.request` | Solicitar | Sol·licita |
| `alert.requestLabel` | Solicitar parada a la línea {{line}} hacia {{destination}} | Sol·licita parada a la línia {{line}} cap a {{destination}} |
| `alert.dialogTitle` | (igual que `requestLabel`, destino marcado) | (ídem) |
| `alert.arrivalInfo` | El autobús {{time}}. | L'autobús {{time}}. |
| `alert.needsLegend` | ¿Necesitas algo al subir? | Necessites alguna cosa en pujar? |
| `alert.remember` | Recordar mis necesidades en este dispositivo | Recorda les meues necessitats en este dispositiu |
| `alert.confirm` | Solicitar parada | Sol·licita la parada |
| `alert.back` | Volver | Torna |
| `alert.sending` | Enviando… | Enviant… |
| `alert.requested` | Parada solicitada para la línea {{line}} | Parada sol·licitada per a la línia {{line}} |
| `alert.pending` | **Parada solicitada.** Aún no hay conductor conectado en esta línea. | **Parada sol·licitada.** Encara no hi ha cap conductor connectat en esta línia. |
| `alert.delivered` | **El conductor ha recibido tu solicitud.** | **El conductor ha rebut la teua sol·licitud.** |
| `alert.youIndicated` | Has indicado: {{needs}} | Has indicat: {{needs}} |
| `alert.cancel` | Cancelar solicitud | Cancel·la la sol·licitud |
| `alert.cancelled` | Solicitud cancelada | Sol·licitud cancel·lada |
| `alert.alreadyGone` | La solicitud ya no estaba activa | La sol·licitud ja no estava activa |
| `alert.cancelFailed` | No se ha podido cancelar la solicitud | No s'ha pogut cancel·lar la sol·licitud |
| `alert.otherBus` | Ya has solicitado otro autobús de esta línea | Ja has sol·licitat un altre autobús d'esta línia |
| `alert.orphanTitle` | Línea {{line}} hacia {{destination}} | Línia {{line}} cap a {{destination}} |
| `alert.error.gone` | Este autobús ya no se puede solicitar. | Este autobús ja no es pot sol·licitar. |
| `alert.error.rate_one/_other` | Has hecho demasiadas solicitudes. Inténtalo dentro de {{count}} minuto(s). | Has fet massa sol·licituds. Torna-ho a intentar d'ací a {{count}} minut(s). |
| `alert.error.notFound` | La parada ya no está disponible. Vuelve a escanear el código QR. | La parada ja no està disponible. Torna a escanejar el codi QR. |
| `alert.error.network` | No se ha podido enviar la solicitud. Comprueba la conexión. | No s'ha pogut enviar la sol·licitud. Comprova la connexió. |
| `alert.event.delivered` | El conductor de la línea {{line}} ha recibido tu solicitud | El conductor de la línia {{line}} ha rebut la teua sol·licitud |
| `alert.event.expired` | Tu solicitud de la línea {{line}} ha terminado: {{reason}} | La teua sol·licitud de la línia {{line}} ha acabat: {{reason}} |
| `alert.event.reason.PASSED` | el autobús ha pasado por la parada | l'autobús ha passat per la parada |
| `alert.event.reason.NEXT_STOP` | el autobús ya ha llegado a la parada siguiente | l'autobús ja ha arribat a la parada següent |
| `alert.event.reason.TIMEOUT` | han pasado 30 minutos | han passat 30 minuts |
| `needs.RAMP / EXTRA_TIME / SEAT / VISUAL` | Necesito la rampa / Necesito más tiempo para subir / Necesito un asiento / Tengo discapacidad visual | Necessite la rampa / Necessite més temps per a pujar / Necessite un seient / Tinc discapacitat visual |
| `needs.short.*` | rampa / más tiempo / asiento / discapacidad visual | rampa / més temps / seient / discapacitat visual |
| `needsPage.title` | Mis necesidades | Les meues necessitats |
| `needsPage.intro` | Marca lo que necesitas al subir al autobús. Se guarda solo en este dispositivo y aparecerá marcado cuando solicites parada. | Marca el que necessites en pujar a l'autobús. Només es guarda en este dispositiu i apareixerà marcat quan sol·licites parada. |
| `needsPage.save` / `clear` | Guardar / Borrar mis necesidades | Guarda / Esborra les meues necessitats |
| `needsPage.saved` / `cleared` | Necesidades guardadas / Necesidades borradas | Necessitats guardades / Necessitats esborrades |

Nota: el botón de confirmación en valenciano es "Sol·licita la parada" (el design §4 lo da como
referencia); el resto sigue la referencia del design.

## Capturas para la revisión visual (AC-13)
Las genera `e2e/alerts.spec.ts` en cada ejecución de `npm run e2e` (Playwright vacía `test-results/`
al empezar; no se versionan), igual que `passenger_stop_view` y `passenger_map_view`:
`frontend/test-results/passenger_alert_ui/<perfil>/<nombre>-<es|ca>.png`, con perfil `iphone`, `pixel`
y `tablet-landscape`:
- `stop-request-buttons`: tarjetas sin solicitud ("Ver en el mapa" + "Solicitar"; la 70 sin sentido
  y la N4 sin fila de acciones).
- `dialog-open`: diálogo abierto (captura de la ventana, no de página completa, porque el diálogo
  está fijo a la ventana).
- `card-requested`: tarjeta con solicitud (estado, necesidades, "Cancelar solicitud" con el foco) y
  "Ya has solicitado otro autobús de esta línea" en la otra 93.
- `card-expired`: tras el evento de caducidad, "Solicitar" de nuevo con el foco.
- `dialog-error-429`: diálogo con el error 429 (ventana).
- `orphan-request`: aviso de solicitud cuyo autobús ya no está en la lista.
- `needs-page`: "Mis necesidades".
Las capturas de `passenger_stop_view` (`test-results/passenger_stop_view/…`) muestran ahora también
el botón "Solicitar" en las tarjetas.

## Bloqueos
Ninguno que impida T-09. Hueco de spec para decidir aparte (no improvisado):
- **`alerts.snapshot` con el diálogo abierto.** AC-11 v1.1 solo regula `alert.registered` y
  `alert.delivered`. Si la solicitud de otra pestaña llega por una instantánea (reconexión, o el
  respaldo `GET /alerts/mine`), el diálogo también desaparece, pero el foco cae en `body`, como en la
  v1.0 (por lectura del código, sin test). Propuesta: ampliar AC-11 a `alerts.snapshot` en la próxima versión.

## Verificación
`CI=1 ./init.sh verify --e2e` (2026-11-09, v1.1, puerto 4173 libre): **todo en verde** (exit 0).
- backend: format, lint, types, architecture OK; pytest 1325 passed, 6 deselected; cobertura 99,59 %.
- frontend: format, lint, types OK; vitest 55 ficheros, 563 passed, 2 skipped.
- build + bundle: JS inicial `index-*.js` 147,05 KB gzip (presupuesto 200 KB); Leaflet solo en
  `MapPage-*.js` (50,23 KB gzip, bajo demanda); `test:bundle` 5 passed.
- e2e + a11y: 126 passed (39 de `alerts.spec.ts`: 13 por perfil), axe sin violaciones, sin
  `waitForTimeout`.
- harness: `feature_list.json` y trazabilidad AC→test OK (AC-01…AC-13 citados).
