// @vitest-environment node
import { ESLint } from 'eslint';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const projectRoot = fileURLToPath(new URL('../..', import.meta.url));

function eslint(): ESLint {
  // `ignore: false` because tests/lint is excluded from the normal `npm run lint`.
  return new ESLint({ cwd: projectRoot, ignore: false });
}

describe('ESLint accessibility rules', () => {
  it('[project_scaffold.AC-15] fails on an image without alt text', async () => {
    const [result] = await eslint().lintFiles(['tests/lint/img-without-alt.tsx']);

    const altErrors = (result?.messages ?? []).filter(
      (m) => m.ruleId === 'jsx-a11y/alt-text' && m.severity === 2,
    );
    expect(altErrors).toHaveLength(1);
  }, 30_000);

  it('[project_scaffold.AC-15] accepts an image with alt text', async () => {
    const code = 'export function Ok() {\n  return <img src="/x.png" alt="Bus" />;\n}\n';
    const [result] = await eslint().lintText(code, { filePath: 'src/Ok.tsx' });

    expect(result?.errorCount).toBe(0);
  }, 30_000);

  it('[project_scaffold.AC-15] enables the react-hooks rules', async () => {
    const config = (await eslint().calculateConfigForFile('src/app/App.tsx')) as {
      rules: Record<string, unknown>;
    };

    expect(config.rules).toHaveProperty('react-hooks/rules-of-hooks');
    expect(config.rules).toHaveProperty('react-hooks/exhaustive-deps');
  }, 30_000);
});
