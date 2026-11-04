// @vitest-environment node
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
  mkdirSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { afterEach, describe, expect, it } from 'vitest';

/** Initial JavaScript budget (RNF-01): 200 KB gzip, without lazily loaded chunks. */
const BUDGET_BYTES = 200 * 1024;
const DIST = fileURLToPath(new URL('../../dist/', import.meta.url));
const PACKAGE_JSON = fileURLToPath(new URL('../../package.json', import.meta.url));
const INIT_SH = fileURLToPath(new URL('../../../init.sh', import.meta.url));

/**
 * Set by `npm run test:bundle` right after `npm run build`: only then are the checks on the real
 * `dist/` run, so they never measure an old build. `npm run test` leaves them out.
 */
const BUNDLE_CHECK = process.env.AVISABUS_BUNDLE_CHECK === '1';

/** The freshly built `dist/` (`test:bundle` builds first, so it must exist). */
function builtDist(): string {
  expect(
    existsSync(join(DIST, 'index.html')),
    'dist/index.html is missing: run `npm run test:bundle` (it builds first)',
  ).toBe(true);
  return DIST;
}

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

/**
 * A CSS class that only Leaflet's code writes: present in every build that bundles the library
 * and in no other code of the app.
 */
const LEAFLET_MARKER = 'leaflet-pane';

/** Leaflet in the build: the JS files that contain it, and which of them are initial. */
function leafletChunks(dist: string): { all: string[]; initial: string[] } {
  const assets = readdirSync(join(dist, 'assets')).filter((file) => file.endsWith('.js'));
  const all = assets
    .map((file) => `/assets/${file}`)
    .filter((file) => readFileSync(join(dist, file), 'utf8').includes(LEAFLET_MARKER));
  const initial = initialScripts(readFileSync(join(dist, 'index.html'), 'utf8'));
  return { all, initial: all.filter((file) => initial.includes(file)) };
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

  it('[passenger_map_view.AC-02] finds Leaflet in a chunk and tells whether that chunk is initial', () => {
    const dist = mkdtempSync(join(tmpdir(), 'avisabus-dist-'));
    temporary.push(dist);
    mkdirSync(join(dist, 'assets'));
    writeFileSync(join(dist, 'assets/index.js'), 'import("./MapPage.js")');
    writeFileSync(join(dist, 'assets/MapPage.js'), `L.DomUtil.create("div","${LEAFLET_MARKER}")`);
    writeFileSync(join(dist, 'assets/eager.js'), `"${LEAFLET_MARKER}"`);
    writeFileSync(
      join(dist, 'index.html'),
      '<script type="module" crossorigin src="/assets/index.js"></script>' +
        '<link rel="modulepreload" crossorigin href="/assets/eager.js">',
    );

    expect(leafletChunks(dist)).toEqual({
      all: ['/assets/MapPage.js', '/assets/eager.js'],
      initial: ['/assets/eager.js'],
    });
  });

  it('[passenger_stop_view.AC-21] the budget is only checked on a fresh build: test:bundle builds first, test and e2e do not run it', () => {
    const { scripts } = JSON.parse(readFileSync(PACKAGE_JSON, 'utf8')) as {
      scripts: Record<string, string>;
    };
    const initSh = readFileSync(INIT_SH, 'utf8');

    expect(scripts['test:bundle']).toBe(
      'npm run build && AVISABUS_BUNDLE_CHECK=1 vitest run src/__tests__/bundle-budget.test.ts',
    );
    expect(scripts.test).not.toContain('AVISABUS_BUNDLE_CHECK');
    expect(scripts.e2e).not.toContain('test:bundle');
    expect(initSh).toMatch(
      /run_step "frontend: build \+ bundle"\s+"\$FRONTEND" npm run --silent test:bundle\n/,
    );
    expect(initSh).not.toMatch(/npm run --silent build\b/);
  });

  it.runIf(BUNDLE_CHECK)(
    '[passenger_map_view.AC-02] Leaflet and the map are in a chunk loaded on demand, not in the initial JavaScript',
    () => {
      const { all, initial } = leafletChunks(builtDist());

      expect(all).toHaveLength(1);
      expect(all[0]).toMatch(/^\/assets\/MapPage-[\w-]+\.js$/);
      expect(initial).toEqual([]);
    },
  );

  it.runIf(BUNDLE_CHECK)(
    '[passenger_stop_view.AC-21] [passenger_map_view.AC-02] the built app loads at most 200 KB of gzipped JavaScript at start',
    () => {
      const { files, bytes } = initialJsGzipBytes(builtDist());

      expect(files.length).toBeGreaterThan(0);
      expect(bytes).toBeLessThanOrEqual(BUDGET_BYTES);
    },
  );

  if (!BUNDLE_CHECK) {
    console.warn(
      '[bundle-budget] dist/ checks skipped: run `npm run test:bundle` (builds first, then measures).',
    );
  }
});
