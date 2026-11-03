# Implementación: frontend_i18n
Spec: specs/frontend_i18n/ (v1.0, APPROVED) · Ciclo de revisión: 0 · Rama: `feat/frontend_i18n`

## Tareas
- [x] T-01 Dependencias (`i18next` 26.7, `react-i18next` 17.1, `eslint-plugin-i18next` 6.1),
      `languages.ts`, `detectLanguage.ts`, `safeStorage` (commit bf27e81)
- [x] T-02 Traducciones iniciales, `initI18n`, `lang` y persistencia; `renderWithProviders` (commit 54fc450)
- [x] T-03 Paridad de claves y regla `i18next/no-literal-string` (commit ac11078)
- [x] T-04 Utilidades de formato y `GtfsText` (commit 755ac86)
- [x] T-05 Tema visual (`@fontsource/atkinson-hyperlegible` 5.3, tokens), componentes base de UI,
      foco, `Announcer`, `usePageTitle` (commit 12f25fa)
- [x] T-06 `Layout` accesible y `LanguageSelector` (commit 10cb502)
- [x] T-07 `HomePage` traducida y E2E de idioma con axe, peticiones y capturas (commit 1d3415b)
- [x] T-08 Verificación completa: `./init.sh verify --e2e` en verde (ver "Verificación")

Todos los tests se escribieron antes que el código y se vieron en rojo (fallo de importación o
de aserción) antes de implementar.

### Matriz AC → test
| AC | Evidencia |
|---|---|
| AC-01 | `src/shared/i18n/__tests__/detectLanguage.test.ts` (tabla del design §6 y más) + `i18n.test.ts` (detección con `navigator.languages` simulado) |
| AC-02 | `src/shared/i18n/__tests__/LanguageSelector.test.tsx` (cambio sin recarga + `localStorage`), `i18n.test.ts` (solo se guarda la elección; lo guardado prevalece) + `e2e/i18n.spec.ts` (selección, marca `window` sin recarga, `page.reload()` con navegador en `es-ES` sigue en valenciano) |
| AC-03 | `src/shared/i18n/__tests__/i18n.test.ts` (+ `toHtmlLang` en `detectLanguage.test.ts`) |
| AC-04 | `LanguageSelector.test.tsx` (etiqueta `<label>` visible, nombres y `lang` de las opciones), `src/app/Layout.test.tsx` (selector en `banner`) + e2e axe en `es` y `ca` |
| AC-05 | `i18n.test.ts` (clave solo en `es` con idioma `ca` → texto en castellano + `console.warn`; clave ausente en todos; sin aviso para claves presentes ni fuera de DEV) |
| AC-06 | `src/shared/i18n/__tests__/GtfsText.test.tsx` |
| AC-07 | `src/__tests__/eslint-i18n.test.ts` + fixture `tests/lint/literal-string.tsx` (9 casos, uno por línea, incl. `aria-description`, `<a>` y `<svg>`) |
| AC-08 | `src/__tests__/locales-parity.test.ts` (ficheros reales + casos sintéticos que muestran claves sobrantes/ausentes y valores vacíos) |
| AC-09 | `src/shared/i18n/__tests__/format.test.ts` |
| AC-10 | `src/app/Layout.test.tsx`, `src/shared/ui/__tests__/SkipLink.test.tsx` + e2e (landmarks, un `h1`, primer enfocable = enlace de salto, Enter → foco en `main`) |
| AC-11 | `src/shared/ui/__tests__/usePageTitle.test.tsx` (`createMemoryRouter`, `Link`, `navigate` y atrás) + `HomePage.test.tsx` (título por idioma) |
| AC-12 | `src/shared/ui/__tests__/Announcer.test.tsx` (rAF simulado) + `Layout.test.tsx` (un único par de regiones) |
| AC-13 | `Button.test.tsx`, `SkipLink.test.tsx`, `LanguageSelector.test.tsx` (clases ≥ 44 px), `theme.test.ts` (regla `:focus-visible` y contrastes ≥ 3:1 calculados) + e2e (estilos calculados en navegador real: contorno `3px solid rgb(11, 61, 145)`, separación 2 px, caja ≥ 44 × 44 px en enlace de salto y selector; axe) |
| AC-14 | `src/app/Layout.test.tsx` (pie en `es` y `ca`) + e2e |
| AC-15 | `src/app/routes/HomePage.test.tsx` (ambos idiomas), `eslint-i18n.test.ts` (HomePage y Layout sin literales con `allowInlineConfig: false`) + e2e axe en `es` y `ca` |
| AC-16 | e2e (todas las peticiones al propio origen; `woff2` 400 y 700 de Atkinson cargados; `document.fonts.check`, `FontFace` 400/700 en `loaded` y `font-family` del `body`) + `theme.test.ts` (imports y `--font-sans`) |
| AC-17 | Revisión (capturas, ver abajo) + apoyo automático: `theme.test.ts` (los 17 tokens de `docs/design.md` §4 con su valor), `Button.test.tsx` (variantes §5.5), `Layout.test.tsx` (separadores `divider`, columna de 640 px, pie 13 px `text-muted`) |

### Capturas para la revisión visual (AC-17)
`npm run e2e` (o `./init.sh verify --e2e`) las regenera en cada ejecución en
`frontend/e2e-captures/frontend_i18n/<perfil>/<nombre>.png`, con `<perfil>` = `iphone`, `pixel`,
`tablet-landscape`, página completa, animaciones desactivadas y tras `document.fonts.ready`:

| Fichero | Contenido |
|---|---|
| `home-es.png` / `home-ca.png` | Portada en cada idioma (navegador en `es-ES` / `ca-ES`) |
| `home-es-skip-link-focused.png` / `home-ca-skip-link-focused.png` | Enlace "Saltar al contenido" visible con foco |
| `home-es-language-selector-focused.png` | Selector con el contorno de foco |
| `home-ca-after-reload.png` | Valenciano elegido en el selector y mantenido tras recargar |

La carpeta está en `frontend/.gitignore` (no se versiona). Las he revisado en los tres perfiles:
cabecera con logotipo en `accent` e "Idioma"/"Llengua" + selector a la derecha, separadores
`divider`, contenido centrado a 640 px en tablet y pie de 13 px en `text-muted`.

## Decisiones locales
Dentro de lo que permite design §7 (redacción y maquetación no fijada por `docs/design.md`):
- **Textos:** `app.tagline` = "Próximos autobuses de EMT València y solicitud de parada,
  accesibles para todas las personas." / "Pròxims autobusos de l'EMT València i sol·licitud de
  parada, accessibles per a totes les persones."; `home.title` (título del documento de la
  portada) = "Inicio" / "Inici"; `home.scanQr` en valenciano = "Escaneja el codi QR de la teua
  parada per a vore quan arriba el teu autobús i sol·licitar parada al conductor.". El resto,
  literal del design §4. Pendiente de revisión por la persona en CP-6.
- **Portada:** `h1` (`app.name`, 28 px/1,15 según `docs/design.md` §3 para el `h1` de vista),
  párrafo `app.tagline` a 18 px y párrafo `home.scanQr` a 16 px.
- **Cabecera:** el logotipo no es enlace (solo existe `/`); icono de autobús propio (SVG de
  trazo 2,2, `aria-hidden`) en `shared/ui/icons/BusIcon.tsx`; `flex-wrap` para que no desborde a
  320 px. Selector con borde de 1 px `control-border`, radio 8 px, alto 44 px.
- **Selector:** `appearance-none` y chevrón SVG propio (`ChevronDownIcon`), porque WebKit ignora
  `min-height` en `<select>` con apariencia nativa (el e2e midió 25 px en iPhone/iPad).
- **Pie:** relleno vertical 16 px; contenido con relleno inferior 32 px.
- **Foco:** además de `:focus-visible` (3 px `accent`, separación 2 px), clase `.focus-light`
  (contorno blanco) para fondos oscuros; sin contorno en `main` y `h1` con `tabindex="-1"` cuando
  reciben el foco por programa (no son controles).
- **Botones:** componente `ButtonIcon` compartido (icono 18 px `aria-hidden` a la izquierda),
  `type="button"` por defecto, variante por defecto `secondary`; hover con `accent-hover`.
- **Detección de idioma:** "empieza por `ca`" se interpreta como subetiqueta principal `ca`
  (`ca` o `ca-*`, sin distinguir mayúsculas), para no confundir otros idiomas cuyo código empieza
  por esas letras (p. ej. `cak`).
- **Persistencia:** solo se guarda el idioma cuando la persona lo cambia (suscripción a
  `languageChanged` tras `init`); el idioma detectado no se guarda, para que siga mandando el
  navegador hasta que haya una elección (AC-02).
- **`SkipLink`:** el clic enfoca `main` explícitamente (`preventDefault`) en lugar de seguir el
  fragmento `#main`, para no alterar la URL del router; `href="#main"` se mantiene.
- **`usePageTitle`:** distingue la carga inicial guardando a nivel de módulo la clave de la última
  ubicación (robusto frente al doble efecto de `StrictMode`); `resetPageTitleTracking()` existe
  solo para aislar los tests (se llama en `src/test/setup.ts`).
- **`AnnouncerProvider` anidado** reutiliza las regiones del exterior (así `renderWithProviders`
  y `Layout` no duplican regiones) y `useAnnounce()` fuera del proveedor lanza un error.
- **Formato:** `format.ts` usa las traducciones empaquetadas (`shared/i18n/resources.ts`, módulo
  nuevo compartido con `i18n.ts`) con `Intl.PluralRules` / `Intl.NumberFormat` /
  `Intl.DateTimeFormat`, de modo que son funciones puras que no dependen de la instancia global.
  Distancias: se redondea a metros enteros antes de decidir la unidad (999,6 m → "1,0 km").
- **E2E:** `/// <reference lib="dom" />` en `e2e/i18n.spec.ts` en lugar de añadir `DOM` a
  `tsconfig.node.json` (compartido con `vite.config.ts`).

## Desviaciones respecto al design (para que el reviewer y la persona las validen)
No cambian ningún contrato ni comportamiento de los AC; son necesarias para cumplirlos con las
versiones reales de las librerías. **Propuesta:** reflejarlas en el design en la próxima revisión
de la spec.

1. **AC-05 · aviso de clave ausente.** Con `saveMissing` + `missingKeyHandler` (design §3),
   i18next 26 **no** avisa cuando la clave falta en `ca` pero existe en `es`: la resolución recorre
   `ca → es` y la da por encontrada (comprobado con un script contra la librería). Se añade, solo en
   DEV, un post-procesador (`postProcessPassResolved: true`) que avisa cuando `usedLng` ≠ idioma
   activo; `missingKeyHandler` se mantiene para claves ausentes en todos los idiomas. Además,
   `initImmediate: false` se escribe `initAsync: false` (renombrado en i18next ≥ 24).
2. **AC-07 · regla de literales.** Con la configuración del design, `eslint-plugin-i18next` 6.1
   deja pasar: `aria-description` en cualquier elemento HTML nativo (en etiquetas nativas solo
   comprueba `placeholder`, `alt`, `aria-label`, `value` y `title`) y **cualquier** atributo en las
   etiquetas que clasifica como SVG, entre las que están `a` y `title` (p. ej.
   `<a aria-label="Inicio">`). Se mantiene la configuración del design tal cual y se añade
   `no-restricted-syntax` con selectores que cubren exactamente esos huecos (cada literal se
   informa una sola vez; lo comprueba el test). Además, la regla se aplica a `src/**/*.tsx` y el
   fixture vive en `tests/lint/`: el test lo analiza con `lintText` como si estuviera en
   `src/features/LiteralStrings.tsx`.
3. **Test de otra feature ajustado:** `project_scaffold.AC-15` ("acepta una imagen con `alt`")
   contaba todos los errores de ESLint y ahora el `alt="Bus"` literal es un error i18n. Se filtra
   por reglas `jsx-a11y/`, que es lo que ese test verifica; su intención no cambia.
4. **`HomePage` en T-03/T-06:** en T-03 se silenció de forma temporal (`eslint-disable-next-line`)
   el `h1` literal para que `npm run lint` pasara; en T-06 se quitó su `<main>` porque el
   landmark pasa a `Layout` (si no, habría dos `main`). En T-07 se tradujo y se quitó la directiva
   (el test de AC-15 lo comprueba con `allowInlineConfig: false`). El test de humo
   `project_scaffold.AC-16/AC-17` sigue pasando sin cambios.

## Observaciones (no bloqueantes, para features futuras)
- **PWA sin conexión:** el service worker (`globPatterns` por defecto de Workbox: js/css/html) no
  precachea los `woff2` de la tipografía; sin conexión se usaría `system-ui`. `docs/design.md` §3
  menciona el funcionamiento sin conexión → a considerar en `deployment_rpi` o en la feature que
  trate la PWA offline.
- **`npm run e2e` en local** (`reuseExistingServer` sin `CI`) reutiliza un servidor ya abierto en
  el puerto 4173 aunque sea de un build antiguo; `./init.sh verify --e2e` lo usa igual. Para
  evitar capturas obsoletas, ejecutar con el puerto libre o con `CI=1`.

## Bloqueos
Ninguno.

## Verificación
`./init.sh verify --e2e` (2026-11-03, tras T-07) → código 0, "verify: todo en verde":
- backend: format, lint, types, architecture OK; pytest 853 passed, 6 deselected, cobertura 99,66 %.
- frontend: format, lint, types OK; Vitest 18 ficheros, 150 tests passed; build OK
  (fuentes `atkinson-hyperlegible-*.woff2` en `dist/assets`).
- frontend e2e + a11y: 24 passed (8 tests × iPhone 14, Pixel 7, iPad gen 7 landscape), axe WCAG
  2.1 A/AA sin violaciones en `es` y `ca`.
- harness: `feature_list.json` OK; trazabilidad AC→test OK (AC-01…AC-17 citados).
