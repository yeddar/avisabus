import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

test('[project_scaffold.AC-17] home page has no WCAG 2.1 A/AA violations', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('main')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);

  const results = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze();

  expect(results.violations).toEqual([]);
});
