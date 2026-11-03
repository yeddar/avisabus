import { describe, expect, it } from 'vitest';

import ca from '../locales/ca-valencia/translation.json';
import es from '../locales/es/translation.json';

type Tree = { [key: string]: unknown };

/** Flattens nested translation objects into `a.b.c → value`. */
function flatten(tree: Tree, prefix = ''): Map<string, unknown> {
  const out = new Map<string, unknown>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix === '' ? key : `${prefix}.${key}`;
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      for (const [k, v] of flatten(value as Tree, path)) out.set(k, v);
    } else {
      out.set(path, value);
    }
  }
  return out;
}

/** Human-readable parity problems between two locales (empty list = OK). */
function parityProblems(locales: Record<string, Tree>): string[] {
  const flat = Object.entries(locales).map(([name, tree]) => [name, flatten(tree)] as const);
  const problems: string[] = [];
  for (const [name, keys] of flat) {
    for (const [otherName, otherKeys] of flat) {
      if (name === otherName) continue;
      const missing = [...otherKeys.keys()].filter((k) => !keys.has(k));
      if (missing.length > 0) problems.push(`${name}: missing keys ${missing.join(', ')}`);
    }
    const empty = [...keys].filter(([, v]) => typeof v !== 'string' || v.trim() === '');
    if (empty.length > 0)
      problems.push(`${name}: empty values ${empty.map(([k]) => k).join(', ')}`);
  }
  return problems;
}

describe('Translation files', () => {
  it('[frontend_i18n.AC-08] es and ca-valencia have the same keys and no empty values', () => {
    expect(parityProblems({ es, 'ca-valencia': ca })).toEqual([]);
  });

  it('[frontend_i18n.AC-08] reports missing and extra keys by name', () => {
    const problems = parityProblems({
      es: { a: { b: 'B', c: 'C' } },
      'ca-valencia': { a: { b: 'B', d: 'D' } },
    });

    expect(problems).toEqual(['es: missing keys a.d', 'ca-valencia: missing keys a.c']);
  });

  it('[frontend_i18n.AC-08] reports empty values', () => {
    const problems = parityProblems({
      es: { a: 'A', b: '' },
      'ca-valencia': { a: '  ', b: 'B' },
    });

    expect(problems).toEqual(['es: empty values b', 'ca-valencia: empty values a']);
  });
});
