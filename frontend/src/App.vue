<script setup>
const base = import.meta.env.BASE_URL
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { store } from './store.js'
import { api, IS_MOCK } from './api.js'

const route = useRoute()
const pending = ref(0)
let timer = null

async function pollInbox() {
  if (!store.user) return
  try {
    const items = await api.inbox(store.user.id)
    pending.value = items.filter((r) => r.status === 'sent').length
  } catch {
    /* 네트워크가 잠깐 끊겨도 다음 주기에 다시 시도 */
  }
}

onMounted(() => {
  pollInbox()
  timer = setInterval(pollInbox, 3000)
})
onUnmounted(() => clearInterval(timer))
watch(() => store.user, pollInbox)
</script>

<template>
  <div class="shell">
    <header v-if="store.user && route.path !== '/start'" class="topbar">
      <RouterLink to="/" class="brand">
        <img :src="base + 'icon.svg'" alt="" width="28" height="28" />
        <span>콜가드</span>
        <span v-if="IS_MOCK" class="pill tone-warn" style="font-size: 11px">목업</span>
      </RouterLink>
      <span class="me">{{ store.user.name }}님</span>
    </header>

    <main class="page">
      <RouterView />
    </main>

    <nav v-if="store.user && route.path !== '/start'" class="tabbar" aria-label="메뉴">
      <RouterLink to="/" class="tab">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>
        <span>홈</span>
      </RouterLink>
      <RouterLink to="/analyze" class="tab">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>
        <span>확인하기</span>
      </RouterLink>
      <RouterLink to="/inbox" class="tab">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></svg>
        <span>받은 요청</span>
        <b v-if="pending" class="badge">{{ pending }}</b>
      </RouterLink>
      <RouterLink to="/contacts" class="tab">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-6 7-6s7 2 7 6"/><path d="M17 11h6M20 8v6"/></svg>
        <span>가족 등록</span>
      </RouterLink>
    </nav>
  </div>
</template>
