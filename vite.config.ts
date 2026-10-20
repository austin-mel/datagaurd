import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { parseEnv } from 'node:util'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

const envFile = fileURLToPath(new URL('./environment/.front-end.env', import.meta.url))

export default defineConfig(() => {
  // Shell variables take precedence; only VITE_ values are exposed to the browser.
  const env = {
    ...(existsSync(envFile) ? parseEnv(readFileSync(envFile, 'utf8')) : {}),
    ...process.env,
  }

  return {
    base: "/dataguard/",
    envDir: './environment/',
    define: Object.fromEntries(
      Object.entries(env)
        .filter(([key, value]) => key.startsWith('VITE_') && value !== undefined)
        .map(([key, value]) => [`import.meta.env.${key}`, JSON.stringify(value)]),
    ),
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': { target: env.BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      },
    },
    plugins: [
      vue(),
      vueDevTools(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
  }
})
