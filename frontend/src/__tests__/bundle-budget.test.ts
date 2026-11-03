// @vitest-environment node
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { afterEach, describe, expect, it } from 'vitest';

/** Initial JavaScript budget (RNF-01): 200 KB gzip, without lazily loaded chunks. */
const BUDGET_BYTES = 200 * 1024;
const DIST = fileURLToPath(new URL('../../dist/', import.meta.url));

/**
 * Initial JavaScript of a build: the `<script type="module">` of index.html and its
 * `modulepreload` links (chunks loaded on demand are not referenced there).
 */
function initialScripts(html: string): string[] {
  const scripts = [...html.matchAll(/<script\b[^>]*\btype="module"[^>]*\bsrc="([^"]+)"/g)];
  const preloads = [...html.matchAll(/<link\b[^>]*\brel="modulepreload"[^>]*\bhref="([^"]+)"/g)];
  return [...new Set([...scripts, ...preloads].map((match) => match[1] ?? ''))];
}

function initialJsGzipBytes(dist: string): { files: string[]; bytes: number } {
  const files = initialScripts(readFileSync(join(dist, 'index.html'), 'utf8'));
  const bytes = files.reduce(
    (total, file) => total + gzipSync(readFileSync(join(dist, file.replace(/^\//, '')))).length,
    0,
  );
  return { files, bytes };
}

describe('initial JavaScript budget', () => {
  const temporary: string[] = [];

  afterEach(() => {
    temporary.splice(0).forEach((dir) => rmSync(dir, { recursive: true, force: true }));
  });

  it('[passenger_stop_view.AC-21] counts the module entry and its modulepreloads, gzipped, and nothing else', () => {
    const dist = mkdtempSync(join(tmpdir(), 'avisabus-dist-'));
    temporary.push(dist);
    mkdirSync(join(dist, 'assets'));
    const entry = 'console.log("entry");'.repeat(50);
    const vendor = 'export const v = 1;'.repeat(80);
    writeFileSync(join(dist, 'assets/index.js'), entry);
    writeFileSync(join(dist, 'assets/vendor.js'), vendor);
    writeFileSync(join(dist, 'assets/lazy.js'), 'x'.repeat(10_000));
    writeFileSync(join(dist, 'registerSW.js'), 'x'.repeat(10_000));
    writeFileSync(
      join(dist, 'index.html'),
      '<script type="module" crossorigin src="/assets/index.js"></script>' +
        '<link rel="modulepreload" crossorigin href="/assets/vendor.js">' +
        '<script id="sw" src="/registerSW.js"></script>',
    );

    const { files, bytes } = initialJsGzipBytes(dist);

    expect(files).toEqual(['/assets/index.js', '/assets/vendor.js']);
    expect(bytes).toBe(gzipSync(entry).length + gzipSync(vendor).length);
  });

  it.skipIf(!existsSync(join(DIST, 'index.html')))(
    '[passenger_stop_view.AC-21] the built app loads at most 200 KB of gzipped JavaScript at start',
    () => {
      const { files, bytes } = initialJsGzipBytes(DIST);

      expect(files.length).toBeGreaterThan(0);
      expect(bytes).toBeLessThanOrEqual(BUDGET_BYTES);
    },
  );

  if (!existsSync(join(DIST, 'index.html'))) {
    console.warn('[bundle-budget] dist/ not found: run `npm run test:bundle` (builds first).');
  }
});
