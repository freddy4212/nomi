import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { quasar, transformAssetUrls } from '@quasar/vite-plugin'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue({
      template: { transformAssetUrls }
    }),

    // @quasar/vite-plugin configuration
    quasar({
      sassVariables: path.resolve(__dirname, './src/quasar-variables.sass')
    })
  ],
  server: {
    host: '0.0.0.0',
    // port defaults to 5173, but Vite will auto-find next free port
  }
})
