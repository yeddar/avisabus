import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import i18next from 'eslint-plugin-i18next';
import i18nextConstants from 'eslint-plugin-i18next/lib/constants.js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

/** Attributes whose text is read or shown to people, so it must come from t() (frontend_i18n.AC-07). */
const TEXT_ATTRIBUTES = ['aria-label', 'alt', 'title', 'placeholder', 'aria-description'];

/**
 * `i18next/no-literal-string` skips every attribute on the tags it classifies as SVG (which
 * include `a` and `title`) and, on native HTML tags, only checks placeholder/alt/aria-label/
 * value/title. These selectors cover exactly those gaps, so each literal is reported once.
 */
const literalValue = (attribute) => [
  `${attribute}[value.type='Literal']`,
  `${attribute} > JSXExpressionContainer > Literal[raw=/^['"]/]`,
  `${attribute} > JSXExpressionContainer > TemplateLiteral[expressions.length=0]`,
];
const svgTags = `JSXOpeningElement[name.name=/^(${i18nextConstants.SVG_TAGS.join('|')})$/]`;
const literalTextAttributeGaps = [
  ...literalValue(`${svgTags} > JSXAttribute[name.name=/^(${TEXT_ATTRIBUTES.join('|')})$/]`),
  ...literalValue(
    `JSXOpeningElement[name.name=/^[a-z]/] > JSXAttribute[name.name='aria-description']`,
  ),
].map((selector) => ({
  selector,
  message: 'disallow literal string: translate accessible and visible texts with t()',
}));

export default defineConfig(
  {
    // tests/lint holds deliberately invalid fixtures (see src/__tests__/eslint-a11y.test.ts).
    ignores: ['dist', 'dev-dist', 'coverage', 'playwright-report', 'test-results', 'tests/lint'],
  },
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    extends: [jsxA11y.flatConfigs.recommended, reactHooks.configs.flat.recommended],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    // No untranslated texts in components (frontend_i18n.AC-07, see src/__tests__/eslint-i18n.test.ts).
    files: ['src/**/*.tsx'],
    ignores: ['src/**/*.test.tsx', 'src/**/__tests__/**'],
    plugins: { i18next },
    rules: {
      'i18next/no-literal-string': [
        'error',
        {
          mode: 'jsx-only',
          'jsx-attributes': {
            include: TEXT_ATTRIBUTES,
          },
        },
      ],
      'no-restricted-syntax': ['error', ...literalTextAttributeGaps],
    },
  },
  {
    files: ['*.config.{js,ts}', 'e2e/**/*.ts'],
    languageOptions: {
      globals: globals.node,
    },
  },
);
