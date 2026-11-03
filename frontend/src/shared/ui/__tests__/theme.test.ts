// @vitest-environment node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const css = readFileSync(fileURLToPath(new URL('../../../index.css', import.meta.url)), 'utf8');

/** Colour tokens of docs/design.md §4 (name → value). */
const DESIGN_TOKENS: Record<string, string> = {
  text: '#14171F',
  'text-muted': '#4B5563',
  surface: '#FFFFFF',
  accent: '#0B3D91',
  'accent-hover': '#072A66',
  'accent-surface': '#F4F7FD',
  border: '#D5DAE2',
  divider: '#E3E6EC',
  'control-border': '#8A93A3',
  'occ-free-bg': '#E6F4EA',
  'occ-free-fg': '#1E5E2E',
  'occ-medium-bg': '#FFF4D6',
  'occ-medium-fg': '#7A4A00',
  'occ-full-bg': '#FDE7E5',
  'occ-full-fg': '#9B1C14',
  'occ-none-bg': '#F1F3F6',
  'occ-none-fg': '#4B5563',
};

function themeBlock(): string {
  const match = /@theme\s*\{([^}]*)\}/.exec(css);
  if (match?.[1] === undefined) throw new Error('No @theme block in src/index.css');
  return match[1];
}

function token(name: string): string | undefined {
  const match = new RegExp(`--color-${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`).exec(themeBlock());
  return match?.[1]?.toUpperCase();
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r = 0, g = 0, b = 0] = channels.map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

describe('Theme (src/index.css)', () => {
  it.each(Object.entries(DESIGN_TOKENS))(
    '[frontend_i18n.AC-17] defines --color-%s: %s',
    (name, value) => {
      expect(token(name)).toBe(value);
    },
  );

  it('[frontend_i18n.AC-16] uses the self-hosted Atkinson Hyperlegible 400 and 700 with a system fallback', () => {
    expect(css).toContain("@import '@fontsource/atkinson-hyperlegible/400.css'");
    expect(css).toContain("@import '@fontsource/atkinson-hyperlegible/700.css'");
    expect(themeBlock()).toMatch(
      /--font-sans:\s*'Atkinson Hyperlegible',\s*system-ui,\s*sans-serif;/,
    );
  });

  it('[frontend_i18n.AC-13] draws a 3 px accent outline with a 2 px offset on :focus-visible', () => {
    expect(css).toMatch(
      /:focus-visible\s*\{\s*outline:\s*3px solid var\(--color-accent\);\s*outline-offset:\s*2px;/,
    );
  });

  it('[frontend_i18n.AC-13] focus outline colours reach 3:1 against their backgrounds', () => {
    const accent = token('accent') ?? '';
    const white = token('surface') ?? '';
    expect(contrast(accent, white)).toBeGreaterThanOrEqual(3);
    expect(contrast(accent, token('accent-surface') ?? '')).toBeGreaterThanOrEqual(3);
    // Light variant on dark backgrounds (`.focus-light`): white outline on `text`.
    expect(css).toMatch(/\.focus-light[^{]*:focus-visible[^{]*\{\s*outline-color:\s*#fff/);
    expect(contrast(white, token('text') ?? '')).toBeGreaterThanOrEqual(3);
    expect(contrast(white, accent)).toBeGreaterThanOrEqual(3);
  });

  it('[frontend_i18n.AC-17] control borders reach 3:1 against white', () => {
    expect(contrast(token('control-border') ?? '', token('surface') ?? '')).toBeGreaterThanOrEqual(
      3,
    );
  });
});
