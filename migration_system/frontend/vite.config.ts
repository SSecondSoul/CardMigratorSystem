import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Flask serves dist and the API on one origin. No permissive CORS/proxy and no
// model/write credentials are compiled into the browser bundle.
export default defineConfig({
  plugins: [vue()],
  base: '/',
  build: { sourcemap: false, target: 'es2022', outDir: 'dist', emptyOutDir: true },
})
