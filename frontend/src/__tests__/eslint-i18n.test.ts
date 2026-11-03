// @vitest-environment node
import { ESLint } from 'eslint';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const projectRoot = fileURLToPath(new URL('../..', import.meta.url));
const FIXTURE = 'tests/lint/literal-string.tsx';
// The rule is configured for components under src/; the invalid fixture lives in tests/lint (so
// that `npm run lint` ignores it) and is linted as if it were a component.
const VIRTUAL_COMPONENT_PATH = 'src/features/LiteralStrings.tsx';
const I18N_RULES = new Set(['i18next/no-literal-string', 'no-restricted-syntax']);

function eslint(): ESLint {
  return new ESLint({ cwd: projectRoot });
}

async function literalErrorLines(code: string, filePath: string): Promise<number[]> {
  const [result] = await eslint().lintText(code, { filePath });
  return (result?.messages ?? [])
    .filter((m) => m.ruleId !== null && I18N_RULES.has(m.ruleId) && m.severity === 2)
    .filter((m) => m.message.startsWith('disallow literal string'))
    .map((m) => m.line)
    .sort((a, b) => a - b);
}

function component(jsx: string): string {
  return `export function Sample() {\n  return ${jsx};\n}\n`;
}

describe('ESLint i18n rule', () => {
  it('[frontend_i18n.AC-07] fails on literal JSX text and on literal aria-label, alt, title, placeholder and aria-description', async () => {
    const code = readFileSync(`${projectRoot}/${FIXTURE}`, 'utf8');

    // Exactly one error per element of the fixture (lines 6–14).
    expect(await literalErrorLines(code, VIRTUAL_COMPONENT_PATH)).toEqual([
      6, 7, 8, 9, 10, 11, 12, 13, 14,
    ]);
  }, 30_000);

  it.each([
    ['JSX text', '<p>Hola</p>'],
    ['aria-label', '<button type="button" aria-label="Cerrar" />'],
    ['aria-label on a link', '<a href="/" aria-label="Inicio" />'],
    ['aria-label on an svg', '<svg aria-label="Autobús" />'],
    ['aria-label as an expression', `<button type="button" aria-label={'Cerrar'} />`],
    ['alt', '<img src="/x.png" alt="Bus" />'],
    ['title', '<span title="Hola" />'],
    ['title on a link', '<a href="/" title="Hola" />'],
    ['placeholder', '<input placeholder="Hola" />'],
    ['aria-description', '<div aria-description="Hola" />'],
    ['aria-description as a template', '<div aria-description={`Hola`} />'],
    ['aria-description on a component', '<Sample aria-description="Hola" />'],
  ])(
    '[frontend_i18n.AC-07] rejects a literal in %s exactly once',
    async (_name, jsx) => {
      expect(await literalErrorLines(component(jsx), 'src/features/Bad.tsx')).toEqual([2]);
    },
    30_000,
  );

  it('[frontend_i18n.AC-07] accepts translated texts and non-text attributes', async () => {
    const code = [
      "import { useTranslation } from 'react-i18next';",
      'export function Ok() {',
      '  const { t } = useTranslation();',
      '  return (',
      '    <p className="text-sm" id="intro" aria-label={t(\'home.title\')}>',
      "      <a href=\"/\" title={t('home.title')} aria-description={t('home.scanQr')}>",
      "        {t('home.scanQr')}",
      '      </a>',
      '      <svg aria-hidden="true" viewBox="0 0 24 24" />',
      '    </p>',
      '  );',
      '}',
      '',
    ].join('\n');

    expect(await literalErrorLines(code, 'src/features/Ok.tsx')).toEqual([]);
  }, 30_000);

  it.each(['src/features/Bad.test.tsx', 'src/features/__tests__/Bad.tsx'])(
    '[frontend_i18n.AC-07] excludes test files such as %s',
    async (filePath) => {
      expect(await literalErrorLines(component('<p>Hola</p>'), filePath)).toEqual([]);
    },
    30_000,
  );

  it('[frontend_i18n.AC-07] keeps the invalid fixture out of the normal lint run', async () => {
    expect(await eslint().isPathIgnored(FIXTURE)).toBe(true);
  }, 30_000);
});
