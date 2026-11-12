// @vitest-environment node
import { existsSync } from 'node:fs';
import { matchesGlob } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ManifestOptions } from 'vite-plugin-pwa';
import { describe, expect, it } from 'vitest';

import viteConfig, { pwaOptions } from '../../vite.config';

const publicDir = fileURLToPath(new URL('../../public', import.meta.url));
const manifest = pwaOptions.manifest as Partial<ManifestOptions>;

describe('PWA configuration', () => {
  it('[project_scaffold.AC-18] declares the required manifest fields', () => {
    expect(manifest).toMatchObject({
      name: 'AvisaBus',
      short_name: 'AvisaBus',
      lang: 'es',
      start_url: '/',
      display: 'standalone',
    });
  });

  it('[project_scaffold.AC-18] provides 192 px, 512 px and maskable icons that exist', () => {
    const icons = manifest.icons ?? [];
    const sizes = icons.map((icon) => icon.sizes);
    expect(sizes).toEqual(expect.arrayContaining(['192x192', '512x512']));
    expect(icons.some((icon) => icon.purpose === 'maskable')).toBe(true);
    for (const icon of icons) {
      expect(icon.type).toBe('image/png');
      expect(existsSync(`${publicDir}/${icon.src}`), icon.src).toBe(true);
    }
  });

  it('[project_scaffold.AC-18] generates and registers a service worker', () => {
    expect(pwaOptions.strategies ?? 'generateSW').toBe('generateSW');
    expect(pwaOptions.registerType).toBe('autoUpdate');
    expect(pwaOptions.injectRegister).toBe('auto');

    const pluginNames = (viteConfig.plugins ?? [])
      .flat()
      .map((plugin) => (plugin && 'name' in plugin ? plugin.name : undefined));
    expect(pluginNames).toContain('vite-plugin-pwa');
  });

  const precached = (file: string) =>
    (pwaOptions.workbox?.globPatterns ?? []).some((pattern) => matchesGlob(file, pattern));

  it('[deployment_rpi.AC-15] precaches the woff2 files of the typeface with the app shell', () => {
    for (const file of [
      'assets/atkinson-hyperlegible-latin-400-normal-BrHNak5F.woff2',
      'assets/atkinson-hyperlegible-latin-ext-700-normal-GZI4o3u0.woff2',
      'index.html',
      'assets/index-Ba79gKQW.js',
      'assets/index-caiUVFBI.css',
    ]) {
      expect(precached(file), file).toBe(true);
    }
    // The woff fallback is never used by the browsers we support: not worth precaching.
    expect(precached('assets/atkinson-hyperlegible-latin-400-normal-BbWidj28.woff')).toBe(false);
  });

  it('[deployment_rpi.AC-15] never caches OpenStreetMap tiles, /api nor /ws', () => {
    // No runtime caching at all: tiles (another origin) and live data always go to the network.
    expect(pwaOptions.workbox?.runtimeCaching).toBeUndefined();
    for (const path of ['api/v1/stops/508', 'ws/passenger', 'tile.openstreetmap.org/1/0/0.png']) {
      expect(precached(path), path).toBe(false);
    }
    const denylist = pwaOptions.workbox?.navigateFallbackDenylist ?? [];
    expect(denylist.some((pattern) => pattern.test('/api/v1/health'))).toBe(true);
    expect(denylist.some((pattern) => pattern.test('/ws/passenger'))).toBe(true);
  });
});
