import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { parseEnv } from 'node:util'
import path from "node:path";
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
    build: {
      rolldownOptions: {
        input: {
          main: fileURLToPath(new URL('./index.html', import.meta.url)),
          fallback: fileURLToPath(new URL('./404.html', import.meta.url)),
        },
      },
    },
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
        "@": path.resolve(__dirname, "src"),
        "@/assets": path.resolve(__dirname, "src/assets"),
        "@/components": path.resolve(__dirname, "src/components"),
        "@/composables": path.resolve(__dirname, "src/composables"),
        "@/data": path.resolve(__dirname, "src/data"),
        "@/router": path.resolve(__dirname, "src/router"),
        "@/services": path.resolve(__dirname, "src/services"),
        "@/stores": path.resolve(__dirname, "src/stores"),
        "@/types": path.resolve(__dirname, "src/types"),
        "@/utils": path.resolve(__dirname, "src/utils"),
        "@/views": path.resolve(__dirname, "src/views"),
      },
    },
  }
})
