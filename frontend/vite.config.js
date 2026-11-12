import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  const MOCK = loadEnv(mode, process.cwd(), '').VITE_MOCK === '1'
  return {
    // 목업은 https://ryusb2295.github.io/callguard/ 아래에서 열린다
    base: MOCK ? '/callguard/' : '/',
    plugins: [
      vue(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['icon.svg'],
        manifest: {
          name: '콜가드 - 보내기 전에 한 번 더',
          short_name: '콜가드',
          description: '의심 문자를 AI로 분석하고 등록한 가족에게 확인을 요청하는 보이스피싱 예방 앱',
          lang: 'ko',
          start_url: '.',
          scope: '.',
          display: 'standalone',
          background_color: '#ffffff',
          theme_color: '#1d4ed8',
          icons: [
            { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
            { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
          ],
          // 안드로이드에서 문자·카톡·인스타의 '공유하기' 목록에 콜가드가 뜨게 한다
          share_target: {
            action: '.',
            method: 'GET',
            params: { title: 'title', text: 'text', url: 'url' }
          }
        },
        workbox: {
          navigateFallbackDenylist: [/^\/api\//]
        }
      })
    ],
    server: {
      proxy: {
        '/api': 'http://localhost:8000'
      }
    }
  }
})
