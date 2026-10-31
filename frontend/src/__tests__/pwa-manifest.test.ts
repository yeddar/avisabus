// @vitest-environment node
import { existsSync } from 'node:fs';
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
});
