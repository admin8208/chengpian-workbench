import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import ElementPlus from 'unplugin-element-plus/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Keep the dev proxy aligned with the repo-level API env file.
  const env = loadEnv(mode, '../../', '')
  const apiHost = env.CHENGPIAN_API_HOST || process.env.CHENGPIAN_API_HOST || '127.0.0.1'
  const apiPort = env.CHENGPIAN_API_PORT || process.env.CHENGPIAN_API_PORT || '8010'
  const apiTarget = `http://${apiHost}:${apiPort}`

  return {
    plugins: [vue(), ElementPlus({})],
    // Important: don't use the default "assets" folder name.
    // Backend already serves user files under /assets, which would conflict
    // with the built UI asset URLs (/assets/*.js, /assets/*.css).
    build: {
      assetsDir: 'ui',
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return

            if (id.includes('/node_modules/vue/') || id.includes('/node_modules/@vue/')) {
              return 'framework-vue'
            }
            if (id.includes('/node_modules/vue-router/')) {
              return 'framework-router'
            }
            if (id.includes('/node_modules/@element-plus/icons-vue/')) {
              return 'ui-element-plus-icons'
            }
            if (id.includes('/node_modules/element-plus/') || id.includes('/node_modules/@ctrl/tinycolor/')) {
              return 'ui-element-plus'
            }
            if (id.includes('/node_modules/@vueuse/')) {
              return 'utils-vueuse'
            }
            if (id.includes('/node_modules/@iconify/')) {
              return 'utils-iconify'
            }
            if (id.includes('/node_modules/animate.css/')) {
              return 'utils-animate'
            }
            return 'vendor'
          },
        },
      },
    },
    server: {
      port: 5173,
      strictPort: true,
      host: '127.0.0.1',
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/assets': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/exports': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/docs': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/openapi.json': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/redoc': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
