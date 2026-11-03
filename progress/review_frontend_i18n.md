# Revisión: frontend_i18n
Ciclo: 1 · Fecha: 2026-11-03 · Agente: reviewer
Spec: `specs/frontend_i18n/` v1.0 (APPROVED) · Rama: `feat/frontend_i18n` (commits `5b9559b..df5dc8f` sobre `develop`)

## Veredicto: APPROVED

Sin hallazgos bloqueantes. Los 17 AC tienen tests que verifican de verdad el comportamiento.
`./init.sh verify --e2e` pasa con `CI=1` (servidor nuevo). Las capturas e2e y los tokens de
`src/index.css` coinciden con `docs/design.md` §4, §5.1 y §5.5. De las cuatro desviaciones
anotadas, ninguna necesita CP-3. Se propone reflejar las desviaciones 1 y 2 en el design en la
próxima revisión de la spec (no bloqueante).

## Matriz AC → evidencia

| AC | Test(s) | Resultado | Nota |
|---|---|---|---|
| AC-01 | `src/shared/i18n/__tests__/detectLanguage.test.ts` (tabla con `ca`, `ca-ES`, `ca-ES-valencia`, `CA-es`, `['es-ES','ca']`, `['en-GB','ca-ES']`, `[]`, `de-CA`; valores guardados válidos e inválidos); `i18n.test.ts` (`navigator.languages` simulado → `ca`, "Llengua") | OK | Solo cuenta el primer idioma preferido, como pide el design §3. `cak` y `de-CA` no se toman por valenciano: es una lectura razonable de "empieza por `ca`". |
| AC-02 | `LanguageSelector.test.tsx` (con `fireEvent.change`, el texto de otro componente cambia y se guarda `localStorage`); `i18n.test.ts` (la elección se guarda, el idioma detectado no; lo guardado prevalece sobre el navegador); e2e `i18n.spec.ts:155` (marca en `window` = sin recarga; con el navegador en `es-ES`, `reload()` mantiene el valenciano) | OK | En los 3 perfiles |
| AC-03 | `i18n.test.ts` (`lang` al iniciar en `es`/`ca` y al cambiar de idioma en ambos sentidos); `detectLanguage.test.ts` (`toHtmlLang`); e2e `expectHomeIn` (atributo `lang` de `html`) | OK | |
| AC-04 | `LanguageSelector.test.tsx` (`<label>` visible "Idioma"/"Llengua" asociada al `select`; opciones "Castellano"/"Valencià" con `lang` `es`/`ca-ES-valencia`; opción activa); `Layout.test.tsx` (selector dentro de `banner`); e2e `i18n.spec.ts:73` (opciones, `lang` y axe en `es` y `ca`) | OK | |
| AC-05 | `i18n.test.ts`: clave solo en `es` con idioma `ca` → texto en castellano; un único `console.warn` con la clave; aviso para la clave ausente en todos los idiomas; sin aviso para claves presentes (incluido el plural `ca`); sin aviso fuera de DEV (`vi.stubEnv('DEV', false)`) | OK | Ver la desviación 1 |
| AC-06 | `GtfsText.test.tsx` (texto intacto con `lang="ca-ES-valencia"` en `es`; sin `lang` en `ca`; sigue al cambio de idioma; variante `strong`) | OK | |
| AC-07 | `src/__tests__/eslint-i18n.test.ts` con el fixture `tests/lint/literal-string.tsx` (exactamente un error por línea, 6–14) y casos sueltos (texto JSX, `aria-label` en `button`/`a`/`svg`/expresión, `alt`, `title` en `span`/`a`, `placeholder`, `aria-description` literal/plantilla/componente); también se comprueba que no hay falsos positivos y que se excluyen `*.test.tsx` y `__tests__/` | OK | Ver la desviación 2 |
| AC-08 | `src/__tests__/locales-parity.test.ts` (ficheros reales, más casos sintéticos que nombran las claves ausentes de cada lado y los valores vacíos o en blanco) | OK | |
| AC-09 | `format.test.ts`: minutos `es`/`ca` (1/5/0/12, corto y accesible); hora 24 h en `Europe/Madrid` con CET y CEST, `00:05` y la zona horaria de la entrada; distancias en m/km con un decimal y el límite 999,4/999,6 | OK | |
| AC-10 | `Layout.test.tsx` (un `banner`, un `main` y un `contentinfo`; un único `h1` dentro de `main`; el primer enfocable es el enlace de salto y su clic enfoca `main#main`); `SkipLink.test.tsx` (traducido, `href="#main"`); e2e `i18n.spec.ts:87` (landmarks, `h1`, primer enfocable, Enter → `main` con el foco) | OK | |
| AC-11 | `usePageTitle.test.tsx` con `createMemoryRouter`: formato `… · AvisaBus`, sin mover el foco en la carga inicial, foco en el `h1` (`tabindex=-1`) tras navegar con `Link`, con `navigate()` y hacia atrás, título actualizado al cambiar de idioma; `HomePage.test.tsx` ("Inicio · AvisaBus" / "Inici · AvisaBus") | OK | |
| AC-12 | `Announcer.test.tsx` (`role=status` con `aria-live=polite` y `role=alert` con `aria-live=assertive`, ocultas visualmente; `useAnnounce` educado por defecto y asertivo si se pide; repetición vaciando la región y escribiendo en el siguiente frame con rAF simulado; un proveedor anidado reutiliza las regiones; fuera del proveedor lanza un error); `Layout.test.tsx` (un único par de regiones) | OK | |
| AC-13 | `Button.test.tsx`, `SkipLink.test.tsx` y `LanguageSelector.test.tsx` (`min-h-11`, `min-w-11`); `theme.test.ts` (regla `:focus-visible` de 3 px `accent` con separación de 2 px; contrastes ≥ 3:1 calculados, también los de la variante clara); e2e `i18n.spec.ts:118` (estilo calculado en navegador real: `3px solid rgb(11, 61, 145)` con separación de 2px; caja ≥ 44 × 44 en el enlace de salto y en el selector; axe) | OK | |
| AC-14 | `Layout.test.tsx` (atribución literal dentro de `contentinfo`, en `es` y `ca`); e2e `expectHomeIn` | OK | |
| AC-15 | `HomePage.test.tsx` (en `es`/`ca`: un `h1` "AvisaBus" en `main`, texto del QR en `main`, título; cambio de idioma sin recargar); `eslint-i18n.test.ts:90` (`HomePage` y `Layout` sin literales con `allowInlineConfig: false`); e2e axe en `es` y `ca` | OK | |
| AC-16 | e2e `i18n.spec.ts:184` (todas las peticiones salen del propio origen; se piden los `woff2` latin 400 y 700; `document.fonts.check`; `FontFace` 400 y 700 en estado `loaded`; `font-family` del `body`); `theme.test.ts` (imports de `@fontsource` y `--font-sans`) | OK | Comprobado en los 3 perfiles |
| AC-17 | Revisión: tokens de `src/index.css:10-27` frente a `docs/design.md` §4 y capturas frente a §5.1 (ver la sección siguiente). Apoyo automático: `theme.test.ts` (los 17 tokens), `Button.test.tsx` (§5.5) y `Layout.test.tsx` (separadores, columna de 640 px, pie de 13 px `text-muted`) | OK | Queda pendiente la validación manual de la persona en CP-6 |

### Revisión visual (AC-17)
Capturas regeneradas en esta revisión (`CI=1`, puerto 4173 libre) en
`frontend/e2e-captures/frontend_i18n/{iphone,pixel,tablet-landscape}/`. He revisado
`iphone/home-es.png`, `tablet-landscape/home-ca.png`, `pixel/home-es-language-selector-focused.png`
y `pixel/home-ca-skip-link-focused.png`.

- **Tokens (§4):** los 17 valores de `src/index.css` coinciden uno a uno con la guía (los 9 de la
  tabla principal y los 8 de ocupación `occ-*-bg/-fg`). Las mayúsculas y minúsculas de los
  hexadecimales no importan.
- **Cabecera (§5.1):** el icono de autobús mide 28 px (`size-7`) y es SVG de trazo 2,2 con
  `aria-hidden`; "AvisaBus" va a 20 px (`text-xl`) en negrita y color `accent`. A la derecha está
  la etiqueta visible "Idioma"/"Llengua" con el selector de 44 px, borde `control-border` y radio
  de 8 px. Lleva el separador inferior `divider` y un relleno de 12 × 16 px (`py-3 px-4`). Las
  capturas lo confirman.
- **Contenido:** relleno de 20 px arriba y 16 px a los lados; las secciones están separadas
  20 px (`gap-5`). El `h1` mide 28 px con interlineado 1,15 (§3). En la tablet horizontal la
  columna queda centrada a 640 px: se mide ≈ 607 px de texto más 32 px de relleno.
- **Pie:** 13 px, `text-muted`, separador superior `divider`, con la atribución traducida.
- **Foco:** contorno de 3 px `accent` con separación de 2 px, bien visible en el selector y en
  el enlace de salto, que aparece arriba a la izquierda con borde de 2 px y radio de 10 px.
- **Botones (§5.5):** `buttonStyles.ts` aplica radio de 10 px, borde de 2 px `accent`, texto en
  700 y las variantes principal y secundaria, con icono de 18 px `aria-hidden` a la izquierda.
  La portada no tiene botones, así que solo se verifican por clases.

## Evaluación de las desviaciones anotadas por el implementer

| # | Desviación | ¿Cumple la intención del AC? | ¿Cabe en el design? | Clasificación |
|---|---|---|---|---|
| 1 | AC-05: post-procesador solo en DEV (`i18n.ts:22-40`, `:80-81`) porque `missingKeyHandler` no se dispara si la clave existe en el idioma de respaldo; `initImmediate` → `initAsync` (`i18n.ts:71`) | Sí. El texto sale en castellano y en desarrollo se avisa una sola vez por clave; en producción no se avisa (tests en `i18n.test.ts`). | Sí. Mantiene la interfaz `initI18n(options?)`, `fallbackLng: 'es'`, `saveMissing` y `missingKeyHandler` del design §3 y solo añade un mecanismo interno. `initAsync` es el nombre actual de la misma opción en i18next ≥ 24. | **No es CP-3.** La pista de configuración del design §3 está desfasada respecto a i18next 26, pero el AC no es ambiguo ni contradictorio. Se recomienda actualizar el design §3 en la próxima revisión de la spec (no bloqueante). |
| 2 | AC-07: `no-restricted-syntax` complementa a `i18next/no-literal-string` 6.1 para cubrir `aria-description` en etiquetas nativas y los atributos de las etiquetas que el plugin trata como SVG (`a`, `title`) (`eslint.config.js:11-33`, `:63`) | Sí. Sin el complemento, `npm run lint` no fallaría con `<a aria-label="Inicio">` ni con `<div aria-description="…">`, y el AC lo exige. El test comprueba exactamente un error por literal y que no hay falsos positivos. | Sí. La configuración del design §3 se conserva tal cual y la regla añadida solo cubre esos huecos. | **No es CP-3.** Conviene documentar el complemento en el design §3 (no bloqueante). |
| 3 | Test `project_scaffold.AC-15` («acepta una imagen con `alt`») filtrado a reglas `jsx-a11y/` (`src/__tests__/eslint-a11y.test.ts:27-30`) | Sí. La intención de ese AC es comprobar que jsx-a11y acepta una imagen con `alt`, y lo sigue comprobando: fallaría si una regla jsx-a11y diese error. El `alt="Bus"` literal es ahora un error i18n por diseño (AC-07). | Sí. Es una consecuencia directa de activar la regla que la propia spec anuncia («`project_scaffold` … dejó la regla sin activar; esta feature los sustituye»). | **No es CP-3 ni cambio fuera de alcance.** Es un ajuste mínimo y justificado. |
| 4 | Pasos intermedios en `HomePage` (el `eslint-disable` temporal de T-03 y la retirada de su `<main>` en T-06) | Sí. En el estado final no queda ninguna directiva (`grep eslint-disable` en `src/` solo encuentra el nombre de un test) y hay un único `main`, el del `Layout`. AC-15 se comprueba con `allowInlineConfig: false`. | Sí. El design §2 ya coloca `main#main` en el `Layout`, y el test de humo `project_scaffold.AC-16/17` pasa sin cambios. | **No es CP-3.** Es historia de commits, sin efecto en el resultado. |

## Verificación ejecutada

```
CI=1 ./init.sh verify --e2e        (puerto 4173 libre, capturas borradas antes)  → exit 0, "verify: todo en verde"
  backend   format/lint/types/architecture OK · pytest 853 passed, 6 deselected · cobertura 99,66 %
  frontend  format/lint/types OK · Vitest 18 ficheros, 150 tests passed · build OK
            (woff2/woff de Atkinson Hyperlegible 400/700 latin y latin-ext en dist/assets)
  e2e+a11y  24 passed (8 tests × iphone, pixel, tablet-landscape), sin reintentos; axe WCAG 2.1 A/AA sin violaciones
  harness   feature_list.json OK · trazabilidad AC→test OK
git diff --stat develop...HEAD     → 52 ficheros, todos en frontend/ (más progress/ y feature_list.json del orquestador)
```

## Hallazgos

### Bloqueantes
Ninguno.

### No bloqueantes
- **N-01 · Problema de spec menor (no requiere CP-3)** · `specs/frontend_i18n/design.md` §3
  (bloque `initI18n` y bloque ESLint). El design describe `initImmediate` y se apoya solo en
  `missingKeyHandler` para AC-05, y la configuración de `eslint-plugin-i18next` no basta para
  AC-07 con la versión 6.1. La implementación resuelve ambas cosas sin cambiar contratos
  (desviaciones 1 y 2). Propuesta: que el spec-writer lo refleje en la próxima revisión de la
  spec (`initAsync`, post-procesador en DEV y complemento `no-restricted-syntax`).
- **N-02 · Fragilidad ante actualizaciones** · `frontend/eslint.config.js:4`. Importa un módulo
  interno del plugin (`eslint-plugin-i18next/lib/constants.js`), que puede moverse en una
  versión menor. Si ocurre, lo detectarían `npm run lint` y `eslint-i18n.test.ts`, así que el
  riesgo está controlado.
- **N-03 · Falso aviso posible en DEV** · `frontend/src/shared/i18n/i18n.ts:28-33`. El
  post-procesador compara `usedLng` con el idioma activo de la instancia, así que una llamada
  futura `t(key, { lng: 'es' })` con la interfaz en `ca` avisaría sin que falte nada. Ahora no se
  usa y solo afecta a la consola de desarrollo.
- **N-04 · PWA sin conexión y tipografía (fuera del alcance de esta feature)**. El service
  worker precachea 9 entradas, sin los `woff2`, y sin conexión se usaría `system-ui`.
  `docs/design.md` §3 menciona el funcionamiento sin conexión. El implementer ya lo anota para
  `deployment_rpi` o la feature PWA que corresponda; lo dejo constar para el orquestador.
- **N-05 · Medición de AC-10 por orden del DOM** · `frontend/e2e/i18n.spec.ts:97-103`. El
  "primer elemento enfocable" se comprueba con `querySelector` y no recorriendo el orden de Tab.
  Equivale al orden de tabulación porque no hay `tabindex` positivos, y Tab no es fiable en
  WebKit móvil. Aceptable.

### Lista de comprobación (docs/verification.md §4)
- Contrato: los AC se cumplen, incluidos los casos `SI … ENTONCES` (AC-05, AC-07, AC-08), y las
  interfaces coinciden con el design §3 (`Language`, `SUPPORTED_LANGUAGES`,
  `LANGUAGE_STORAGE_KEY`, `toHtmlLang`, `detectInitialLanguage`, `initI18n`, `GtfsText`,
  `format*`, `AnnouncerProvider`/`useAnnounce`, `usePageTitle`, `SUPPORTED_LANGUAGE_NAMES`).
- Arquitectura: solo hay cambios de frontend, sin efecto en `domain/`. `localStorage` está
  encapsulado en `shared/device/storage.ts` (convenciones §4).
- Tests: sin red. El tiempo en `format` llega como ISO fijo, sin reloj real, y rAF está
  simulado en `Announcer`. Los tests no son tautológicos: por ejemplo, comprobar exactamente un
  error por línea fallaría si la regla dejara de detectar un caso o lo informara dos veces.
- Privacidad: solo se guarda el idioma. Los avisos de consola contienen claves de traducción,
  nunca identificadores.
- Frontend: sin literales (lint con `allowInlineConfig: false` en `HomePage` y `Layout`); claves
  idénticas en `es` y `ca-valencia`; axe sin violaciones en los 3 perfiles y en ambos idiomas;
  foco visible; objetivos de 44 px; regiones `aria-live` únicas; `prefers-reduced-motion`
  respetado.
- Convenciones: Conventional Commits con ámbito `frontend_i18n` y referencia `T-xx`; código en
  inglés y progreso en castellano; no hay variables de configuración nuevas, así que
  `.env.example` no cambia.
- Alcance: no hay cambios fuera de la feature, salvo el ajuste justificado del test de
  `project_scaffold.AC-15` (desviación 3).
