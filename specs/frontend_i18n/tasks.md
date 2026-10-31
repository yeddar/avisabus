# Idiomas y base de accesibilidad del frontend — tasks

> Feature: `frontend_i18n` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-31, RF-32, RNF-03, RNF-14, RNF-15 · Casos de uso: CU-06 · Depende de: project_scaffold

## Exploración

No necesaria.

## Tareas

- [ ] **T-01** — Dependencias (`i18next`, `react-i18next`, `eslint-plugin-i18next`), `languages.ts`,
  `detectLanguage.ts`, `safeStorage`.
  - AC: frontend_i18n.AC-01
  - Ficheros: `package.json`, `src/shared/i18n/{languages,detectLanguage}.ts`, `src/shared/device/storage.ts`, tests
  - Verificación: `cd frontend && npm run test -- detectLanguage`

- [ ] **T-02** — Ficheros de traducción iniciales, `initI18n`, actualización de `lang` y
  persistencia; helper `renderWithProviders`.
  - AC: frontend_i18n.AC-03, AC-05
  - Ficheros: `src/locales/**`, `src/shared/i18n/i18n.ts`, `src/main.tsx`, `src/test/render.tsx`, tests
  - Verificación: `cd frontend && npm run test -- i18n`

- [ ] **T-03** — Test de paridad de claves y regla `i18next/no-literal-string` con su test.
  - AC: frontend_i18n.AC-07, AC-08
  - Ficheros: `eslint.config.js`, `tests/lint/literal-string.tsx`, `src/__tests__/{eslint-i18n,locales-parity}.test.ts`
  - Verificación: `cd frontend && npm run lint && npm run test -- parity eslint-i18n`

- [ ] **T-04** — Utilidades de formato (`formatMinutes`, `formatClockTime`, `formatDistance`) y
  `GtfsText`.
  - AC: frontend_i18n.AC-06, AC-09
  - Ficheros: `src/shared/i18n/{format.ts,GtfsText.tsx}`, tests
  - Verificación: `cd frontend && npm run test -- format GtfsText`

- [ ] **T-05** — Componentes base de UI (`Button`, `LinkButton`, `SkipLink`, `VisuallyHidden`),
  estilos de foco, `AnnouncerProvider`/`useAnnounce`, `usePageTitle`.
  - AC: frontend_i18n.AC-11, AC-12, AC-13
  - Ficheros: `src/shared/ui/**`, `src/index.css`, tests
  - Verificación: `cd frontend && npm run test -- ui`

- [ ] **T-06** — `Layout` accesible (cabecera con selector, `main#main`, pie con atribución,
  anuncios) y `LanguageSelector`.
  - AC: frontend_i18n.AC-02, AC-04, AC-10, AC-14
  - Ficheros: `src/app/Layout.tsx`, `src/shared/i18n/LanguageSelector.tsx`, tests
  - Verificación: `cd frontend && npm run test -- Layout LanguageSelector`

- [ ] **T-07** — `HomePage` traducida (quitar el literal temporal) y E2E de idioma con axe en `es`
  y `ca` (incluida la persistencia tras recargar).
  - AC: frontend_i18n.AC-02, AC-04, AC-10, AC-13, AC-15
  - Ficheros: `src/app/routes/HomePage.tsx`, `e2e/i18n.spec.ts`
  - Verificación: `cd frontend && npm run e2e`

- [ ] **T-08** — Verificación completa.
  - Verificación: `./init.sh verify --e2e`
