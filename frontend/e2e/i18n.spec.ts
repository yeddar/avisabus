/// <reference lib="dom" />
/// <reference lib="dom.iterable" />
// Browser globals are only used inside page.evaluate() callbacks.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

/**
 * Screenshots for the visual review of frontend_i18n.AC-17 (docs/design.md §5.1 and §5.5).
 * Regenerated on every run: frontend/e2e-captures/frontend_i18n/<project>/<name>.png
 */
const CAPTURES_DIR = fileURLToPath(new URL('../e2e-captures/frontend_i18n/', import.meta.url));

const TEXTS = {
  es: {
    htmlLang: 'es',
    title: 'Inicio · AvisaBus',
    languageLabel: 'Idioma',
    skip: 'Saltar al contenido',
    scanQr:
      'Escanea el código QR de tu parada para ver cuándo llega tu autobús y solicitar parada al conductor.',
    attribution: 'Datos: EMT València (GTFS y tiempos de llegada) · Ajuntament de València',
  },
  ca: {
    htmlLang: 'ca-ES-valencia',
    title: 'Inici · AvisaBus',
    languageLabel: 'Llengua',
    skip: 'Botar al contingut',
    scanQr:
      'Escaneja el codi QR de la teua parada per a vore quan arriba el teu autobús i sol·licitar parada al conductor.',
    attribution: "Dades: EMT València (GTFS i temps d'arribada) · Ajuntament de València",
  },
} as const;

type Lang = keyof typeof TEXTS;

async function capture(page: Page, testInfo: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: `${CAPTURES_DIR}${testInfo.project.name}/${name}.png`,
    fullPage: true,
    animations: 'disabled',
    caret: 'hide',
  });
}

async function expectHomeIn(page: Page, lang: Lang) {
  const texts = TEXTS[lang];
  await expect(page.locator('html')).toHaveAttribute('lang', texts.htmlLang);
  await expect(page).toHaveTitle(texts.title);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('AvisaBus');
  await expect(page.getByRole('main').getByText(texts.scanQr)).toBeVisible();
  await expect(page.getByRole('contentinfo').getByText(texts.attribution)).toBeVisible();
  await expect(
    page.getByRole('banner').getByRole('combobox', { name: texts.languageLabel }),
  ).toBeVisible();
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze();
  expect(results.violations).toEqual([]);
}

for (const [lang, locale] of [
  ['es', 'es-ES'],
  ['ca', 'ca-ES'],
] as const) {
  test.describe(`home page in ${lang} (browser locale ${locale})`, () => {
    test.use({ locale });

    test(`[frontend_i18n.AC-15] [frontend_i18n.AC-04] shows the translated home page with no WCAG 2.1 A/AA violations (${lang})`, async ({
      page,
    }, testInfo) => {
      await page.goto('/');

      await expectHomeIn(page, lang);
      const options = page.getByRole('option');
      await expect(options).toHaveText(['Castellano', 'Valencià']);
      await expect(options.nth(0)).toHaveAttribute('lang', 'es');
      await expect(options.nth(1)).toHaveAttribute('lang', 'ca-ES-valencia');
      await expectNoAxeViolations(page);
      await capture(page, testInfo, `home-${lang}`);
    });

    test(`[frontend_i18n.AC-10] has the landmarks, one h1 and the skip link first (${lang})`, async ({
      page,
    }, testInfo) => {
      await page.goto('/');

      await expect(page.getByRole('banner')).toHaveCount(1);
      await expect(page.getByRole('main')).toHaveCount(1);
      await expect(page.getByRole('contentinfo')).toHaveCount(1);
      await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);

      const firstFocusable = await page.evaluate(() => {
        const el = document.querySelector<HTMLElement>(
          'a[href], button, select, input, textarea, [tabindex]:not([tabindex="-1"])',
        );
        return el?.textContent ?? null;
      });
      expect(firstFocusable).toBe(TEXTS[lang].skip);

      const skip = page.getByRole('link', { name: TEXTS[lang].skip });
      await skip.focus();
      await expect(skip).toBeVisible();
      await capture(page, testInfo, `home-${lang}-skip-link-focused`);
      await page.keyboard.press('Enter');
      await expect(page.getByRole('main')).toBeFocused();
    });
  });
}

test.describe('focus and touch targets', () => {
  test.use({ locale: 'es-ES' });

  test('[frontend_i18n.AC-13] interactive elements show a 3 px accent focus outline and are at least 44 × 44 px', async ({
    page,
  }, testInfo) => {
    await page.goto('/');

    const skip = page.getByRole('link', { name: TEXTS.es.skip });
    const select = page.getByRole('combobox', { name: TEXTS.es.languageLabel });
    for (const control of [skip, select]) {
      await control.focus();
      const outline = await control.evaluate((el) => {
        const style = getComputedStyle(el);
        return {
          width: style.outlineWidth,
          style: style.outlineStyle,
          color: style.outlineColor,
          offset: style.outlineOffset,
        };
      });
      // accent #0B3D91: 10:1 on white, well above the 3:1 required for focus indicators.
      expect(outline).toEqual({
        width: '3px',
        style: 'solid',
        color: 'rgb(11, 61, 145)',
        offset: '2px',
      });
      const box = await control.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(44);
      expect(box?.width).toBeGreaterThanOrEqual(44);
    }
    await capture(page, testInfo, 'home-es-language-selector-focused');
    await expectNoAxeViolations(page);
  });
});

test.describe('language choice', () => {
  test.use({ locale: 'es-ES' });

  test('[frontend_i18n.AC-02] changes every text without reloading and keeps the choice after reloading', async ({
    page,
  }, testInfo) => {
    await page.goto('/');
    await expectHomeIn(page, 'es');
    await page.evaluate(() => {
      (window as unknown as { notReloaded: boolean }).notReloaded = true;
    });

    await page.getByRole('combobox', { name: TEXTS.es.languageLabel }).selectOption('ca');

    await expectHomeIn(page, 'ca');
    await expect(page.getByRole('link', { name: TEXTS.ca.skip })).toHaveCount(1);
    expect(
      await page.evaluate(() => (window as unknown as { notReloaded?: boolean }).notReloaded),
    ).toBe(true);

    // The browser still prefers Spanish (locale es-ES), but the stored choice prevails.
    await page.reload();
    await expectHomeIn(page, 'ca');
    await expect(page.getByRole('combobox', { name: TEXTS.ca.languageLabel })).toHaveValue('ca');
    await expectNoAxeViolations(page);
    await capture(page, testInfo, 'home-ca-after-reload');
  });
});

test.describe('self-hosted resources', () => {
  test.use({ locale: 'es-ES' });

  test('[frontend_i18n.AC-16] loads Atkinson Hyperlegible from its own origin and makes no third-party requests', async ({
    page,
    baseURL,
  }) => {
    const requests: string[] = [];
    page.on('request', (request) => requests.push(request.url()));

    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);

    const origin = new URL(baseURL ?? '').origin;
    const foreign = requests.filter(
      (url) => !url.startsWith('data:') && new URL(url).origin !== origin,
    );
    expect(foreign).toEqual([]);
    expect(
      requests.some((url) => /atkinson-hyperlegible-latin-400-normal-.*\.woff2$/.test(url)),
    ).toBe(true);
    expect(
      requests.some((url) => /atkinson-hyperlegible-latin-700-normal-.*\.woff2$/.test(url)),
    ).toBe(true);

    const fonts = await page.evaluate(() => ({
      check: document.fonts.check('16px "Atkinson Hyperlegible"'),
      loadedWeights: [...document.fonts]
        .filter(
          (face) =>
            face.family.replace(/"/g, '') === 'Atkinson Hyperlegible' && face.status === 'loaded',
        )
        .map((face) => face.weight),
      bodyFamily: getComputedStyle(document.body).fontFamily,
    }));
    expect(fonts.check).toBe(true);
    expect(new Set(fonts.loadedWeights)).toEqual(new Set(['400', '700']));
    expect(fonts.bodyFamily).toMatch(/^"?Atkinson Hyperlegible"?, system-ui, sans-serif$/);
  });
});
