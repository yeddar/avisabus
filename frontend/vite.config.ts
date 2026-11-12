import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { VitePWA, type VitePWAOptions } from 'vite-plugin-pwa';
import { defineConfig } from 'vitest/config';

const BACKEND_URL = 'http://localhost:8000';
const THEME_COLOR = '#0b3d91';

/** PWA manifest and service worker settings (exported for src/__tests__/pwa-manifest.test.ts). */
export const pwaOptions: Partial<VitePWAOptions> = {
  strategies: 'generateSW',
  registerType: 'autoUpdate',
  injectRegister: 'auto',
  includeAssets: ['icons/apple-touch-icon-180.png'],
  manifest: {
    name: 'AvisaBus',
    short_name: 'AvisaBus',
    description: 'Avisos de espera accesibles para EMT València',
    lang: 'es',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    theme_color: THEME_COLOR,
    background_color: '#ffffff',
    icons: [
      { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  },
  workbox: {
    // App shell plus the woff2 files of the self-hosted typeface, so the PWA keeps its font
    // offline (deployment_rpi AC-15). The woff fallbacks are not needed by supported browsers.
    globPatterns: ['**/*.{js,css,html,woff2}'],
    // The API and WebSocket are always live data: never served from the service worker cache.
    // There is no runtime caching: OpenStreetMap tiles always come from their servers.
    navigateFallbackDenylist: [/^\/api\//, /^\/ws/],
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss(), VitePWA(pwaOptions)],
  server: {
    proxy: {
      '/api': BACKEND_URL,
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
  },
});
