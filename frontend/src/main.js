import { createApp } from 'vue'
import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import { store } from './store.js'

import StartView from './views/StartView.vue'
import HomeView from './views/HomeView.vue'
import AnalyzeView from './views/AnalyzeView.vue'
import CaseView from './views/CaseView.vue'
import ContactsView from './views/ContactsView.vue'
import InboxView from './views/InboxView.vue'

const router = createRouter({
  // 목업은 GitHub Pages라 새로고침해도 깨지지 않게 #/ 주소를 쓴다
  history: import.meta.env.VITE_MOCK === '1' ? createWebHashHistory() : createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/start', component: StartView, meta: { public: true } },
    { path: '/', component: HomeView },
    { path: '/analyze', component: AnalyzeView },
    // 안드로이드 공유하기로 들어온 내용은 분석 화면으로 넘긴다
    {
      path: '/share',
      redirect: (to) => {
        const parts = [to.query.title, to.query.text, to.query.url].filter(Boolean)
        return { path: '/analyze', query: { text: parts.join('\n') } }
      }
    },
    { path: '/case/:id', component: CaseView, props: true },
    { path: '/contacts', component: ContactsView },
    { path: '/inbox', component: InboxView }
  ]
})

router.beforeEach((to) => {
  if (!to.meta.public && !store.user) {
    return { path: '/start', query: { next: to.fullPath } }
  }
})

// 안드로이드 공유하기로 들어오면 (?title=&text=&url=) 확인 화면으로 넘긴다
const sp = new URLSearchParams(location.search)
if (sp.has('text') || sp.has('url') || sp.has('title')) {
  const shared = [sp.get('title'), sp.get('text'), sp.get('url')].filter(Boolean).join('\n')
  history.replaceState(null, '', location.pathname + location.hash)
  router.replace({ path: '/analyze', query: { text: shared } })
}

createApp(App).use(router).mount('#app')
