import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

// GitHub Pages serves this from https://natesaindon.github.io/3Dentes/, so every
// asset URL needs that prefix. Code reads it back via import.meta.env.BASE_URL.
const BASE = '/3Dentes/';

export default defineConfig({
  base: BASE,
  build: { target: 'es2022', assetsDir: 'assets' },
  plugins: [
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['dentition.glb', 'teeth.json'],
      workbox: {
        globPatterns: ['**/*.{js,css,html,glb,json,svg,png}'],
        // The mesh is ~6MB and Workbox silently drops anything over 2MB from the
        // precache, which would break offline use without any error.
        maximumFileSizeToCacheInBytes: 12 * 1024 * 1024,
      },
      manifest: {
        name: '3Dentes — Interactive Oral Anatomy',
        short_name: '3Dentes',
        description: 'Interactive 3D atlas of human oral anatomy.',
        theme_color: '#14161a',
        background_color: '#14161a',
        display: 'standalone',
        orientation: 'any',
        start_url: BASE,
        scope: BASE,
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
});
