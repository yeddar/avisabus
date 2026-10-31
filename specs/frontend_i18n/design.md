# Idiomas y base de accesibilidad del frontend — design

> Feature: `frontend_i18n` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-31, RF-32, RNF-03, RNF-14, RNF-15 · Casos de uso: CU-06 · Depende de: project_scaffold

## 1. Resumen

i18next se inicializa de forma síncrona con los dos recursos empaquetados. Un detector propio
decide el idioma inicial (preferencia guardada → navegador → castellano). El `Layout` existente
pasa a ser la estructura accesible común con cabecera (marca + selector), `main`, pie y región de
anuncios. Una regla de ESLint y un test de paridad impiden textos sin traducir.

## 2. Componentes

```
frontend/src/
├── shared/
│   ├── i18n/
│   │   ├── i18n.ts                # initI18n(): instancia i18next (react-i18next)
│   │   ├── languages.ts           # SUPPORTED_LANGUAGES, Language, toHtmlLang()
│   │   ├── detectLanguage.ts      # detectInitialLanguage(storage, navigatorLanguages)
│   │   ├── LanguageSelector.tsx
│   │   ├── GtfsText.tsx           # <GtfsText>{nombre}</GtfsText>
│   │   ├── format.ts              # formatMinutes, formatClockTime, formatDistance
│   │   └── __tests__/…
│   ├── device/
│   │   └── storage.ts             # safeStorage: get/set con try/catch (localStorage)
│   └── ui/
│       ├── Button.tsx · LinkButton.tsx   # objetivos ≥ 44 px, foco visible
│       ├── SkipLink.tsx
│       ├── VisuallyHidden.tsx
│       ├── Announcer.tsx          # <AnnouncerProvider> + useAnnounce()
│       └── usePageTitle.ts        # usePageTitle(titleKey) → document.title + foco en h1
├── locales/
│   ├── es/translation.json
│   └── ca-valencia/translation.json
└── app/
    ├── Layout.tsx                 # SkipLink, header(banner), main#main, footer(contentinfo), Announcer
    └── routes/HomePage.tsx        # traducida
```

`safeStorage` encapsula `localStorage` (convención §4 "Estado local del dispositivo"); las
features posteriores guardan ahí `device_id` y el perfil de accesibilidad.

## 3. Interfaces

```ts
// shared/i18n/languages.ts
export type Language = 'es' | 'ca';
export const SUPPORTED_LANGUAGES: readonly Language[] = ['es', 'ca'];
export const LANGUAGE_STORAGE_KEY = 'avisabus.language';
export function toHtmlLang(lang: Language): 'es' | 'ca-ES-valencia';
```

> Códigos internos `es` y `ca` (no `ca-valencia`): i18next y `Intl.PluralRules` resuelven el plural
> por el código base `ca`. Los recursos del valenciano viven en `locales/ca-valencia/` (convenciones)
> y se registran bajo `ca`. Hacia fuera (atributo `lang`) se usa `ca-ES-valencia`.

```ts
// shared/i18n/detectLanguage.ts
export function detectInitialLanguage(
  stored: string | null,
  navigatorLanguages: readonly string[],
): Language;
// stored válido → stored; si no, primer idioma del navegador que empiece por 'ca' (sin distinguir
// mayúsculas) → 'ca'; si no → 'es'. Solo se mira el PRIMER idioma preferido.

// shared/i18n/i18n.ts
export function initI18n(options?: { language?: Language }): i18n;
// i18next.use(initReactI18next).init({ lng, fallbackLng: 'es', resources, initImmediate: false,
//   interpolation: { escapeValue: false }, returnNull: false,
//   saveMissing: import.meta.env.DEV, missingKeyHandler: console.warn en DEV })
// Suscripción a 'languageChanged': guarda en safeStorage y actualiza document.documentElement.lang

// shared/i18n/GtfsText.tsx
export function GtfsText(props: { children: string; as?: 'span' | 'strong' }): JSX.Element;
// Renderiza el texto tal cual; añade lang="ca-ES-valencia" si el idioma activo es 'es'.

// shared/i18n/format.ts  (usan Intl con el idioma activo y timeZone 'Europe/Madrid')
export function formatMinutes(minutes: number, lang: Language): { short: string; long: string };
//   short: "5 min"; long: "5 minutos" | "5 minuts" (plural con Intl.PluralRules)
export function formatClockTime(iso: string, lang: Language): string;   // "22:41"
export function formatDistance(meters: number, lang: Language): string; // "850 m" | "1,2 km"

// shared/ui/Announcer.tsx
export function AnnouncerProvider(props: { children: ReactNode }): JSX.Element;
export function useAnnounce(): (message: string, politeness?: 'polite' | 'assertive') => void;
// Dos regiones VisuallyHidden: role="status" aria-live="polite" y role="alert" aria-live="assertive".
// Para repetir un mismo mensaje, se vacía la región y se escribe en el siguiente frame.

// shared/ui/usePageTitle.ts
export function usePageTitle(title: string): void;
// document.title = `${title} · AvisaBus`; al montar la vista, enfoca el h1 (tabIndex=-1)
// si la navegación no es la carga inicial.
```

### Selector de idioma

`<select>` nativo con `<label>` visible pequeño (`t('language.label')`). Opciones con texto fijo
por idioma, que **no** se traduce (cada idioma se nombra en sí mismo); estas dos cadenas son la
única excepción permitida a la regla de literales y se toman de `SUPPORTED_LANGUAGE_NAMES` en
`languages.ts` (constante fuera de JSX):

```ts
export const SUPPORTED_LANGUAGE_NAMES: Record<Language, string> = { es: 'Castellano', ca: 'Valencià' };
```

### ESLint

`eslint-plugin-i18next`, configuración flat:

```js
{ files: ['src/**/*.tsx'], ignores: ['src/**/*.test.tsx', 'src/**/__tests__/**'],
  plugins: { i18next }, rules: { 'i18next/no-literal-string': ['error', {
    mode: 'jsx-only',
    'jsx-attributes': { include: ['aria-label', 'alt', 'title', 'placeholder', 'aria-description'] },
  }] } }
```

Fixture de prueba inválida en `frontend/tests/lint/literal-string.tsx` (ya excluida del lint
normal por `tests/lint`).

## 4. Datos (claves iniciales)

```json
{
  "app": { "name": "AvisaBus", "tagline": "…" },
  "home": { "title": "…", "scanQr": "…" },
  "language": { "label": "Idioma" },
  "layout": { "skipToContent": "Saltar al contenido", "attribution": "Datos: EMT València (GTFS y tiempos de llegada) · Ajuntament de València" },
  "time": { "minutesShort": "{{count}} min", "minutes_one": "{{count}} minuto", "minutes_other": "{{count}} minutos", "arriving": "Llegando" },
  "distance": { "meters": "{{value}} m", "kilometers": "{{value}} km" }
}
```

Valenciano: "Llengua", "Botar al contingut", "Dades: EMT València (GTFS i temps d'arribada) ·
Ajuntament de València", "minut/minuts", "Arribant". Los textos finales los redacta el
implementer; la persona los revisa en CP-6 (decisión local permitida: redacción, no claves de
ámbito distinto a estas).

`HomePage`: `h1` = nombre de la app; párrafo con `home.scanQr` ("Escanea el código QR de tu
parada para ver cuándo llega tu autobús y avisar al conductor.").

## 5. Estilos

En `index.css`:
- `:focus-visible { outline: 3px solid #0b3d91; outline-offset: 2px; }` (contraste ≥ 3:1 sobre
  blanco), y variante clara sobre fondos oscuros.
- `Button`/`LinkButton`: `min-h-11 min-w-11` (44 px) y `px-4`.
- `SkipLink`: oculto hasta recibir foco.

## 6. Estrategia de test

| AC | Test |
|---|---|
| AC-01 | `detectLanguage.test.ts` (tabla: `['ca-ES']`, `['ca-ES-valencia','es']`, `['es-ES','ca']` → es, `[]` → es, guardado válido/inválido) |
| AC-02 | `LanguageSelector.test.tsx` (cambio y persistencia) + e2e `i18n.spec.ts` (recarga mantiene idioma) |
| AC-03 | `i18n.test.ts` |
| AC-04 | `LanguageSelector.test.tsx` (label, opciones con `lang`) + e2e axe |
| AC-05 | `i18n.test.ts` (clave solo en `es`, idioma `ca`) |
| AC-06 | `GtfsText.test.tsx` |
| AC-07 | `src/__tests__/eslint-i18n.test.ts` (patrón del de `jsx-a11y`) |
| AC-08 | `src/__tests__/locales-parity.test.ts` (aplana claves; compara conjuntos; valores no vacíos) |
| AC-09 | `format.test.ts` |
| AC-10, AC-14 | `Layout.test.tsx` + e2e |
| AC-11 | `usePageTitle.test.tsx` con `createMemoryRouter` y navegación |
| AC-12 | `Announcer.test.tsx` |
| AC-13 | `Button.test.tsx` (clases/estilos mínimos) + e2e axe |
| AC-15 | `HomePage.test.tsx` en ambos idiomas + e2e `i18n.spec.ts` con axe en `es` y `ca` |

Los tests de componentes usan un helper `renderWithProviders(ui, { language })` en
`src/test/render.tsx` que inicializa i18n en el idioma pedido y monta `AnnouncerProvider`.

El test de humo existente (`project_scaffold.AC-17`) debe seguir pasando sin cambios en su
intención (sigue habiendo un `h1` y un `main`).

## 7. Decisiones locales permitidas

- Redacción exacta de los textos (manteniendo las claves y el significado).
- Maquetación visual de cabecera y pie.

## 8. Preguntas abiertas

Ninguna.
