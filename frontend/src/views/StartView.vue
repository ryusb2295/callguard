<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, IS_MOCK } from '../api.js'
import { store } from '../store.js'

const base = import.meta.env.BASE_URL
const route = useRoute()
const router = useRouter()
const name = ref('')
const phone = ref('')
const error = ref('')
const busy = ref(false)

// 목업 시연용 인물. 엄마로 시작하면 딸·아들이 확인 연락처로 미리 등록된다
const PERSONAS = {
  mom: { name: '엄마', phone: '010-1111-2222', label: '엄마로 시작', desc: '의심 문자를 받는 쪽' },
  daughter: { name: '지은', phone: '010-3333-4444', label: '딸로 시작', desc: '확인 요청을 받는 쪽' },
  son: { name: '민수', phone: '010-5555-6666', label: '아들로 시작', desc: '딸이 답이 없을 때 다음 순서' }
}

async function quickStart(key) {
  const p = PERSONAS[key]
  if (!p) return
  busy.value = true
  try {
    const u = await api.login(p.name, p.phone)
    if (key === 'mom') {
      const have = await api.contacts(u.id)
      if (!have.length) {
        await api.addContact(u.id, { name: '지은', relation: '딸', phone: PERSONAS.daughter.phone })
        await api.addContact(u.id, { name: '민수', relation: '아들', phone: PERSONAS.son.phone })
      }
    }
    store.setUser(u)
    router.replace(key === 'mom' ? '/' : '/inbox')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  if (IS_MOCK && route.query.as) quickStart(String(route.query.as))
})

async function submit() {
  error.value = ''
  if (!name.value.trim()) return (error.value = '이름을 입력해 주세요')
  if (phone.value.replace(/\D/g, '').length < 10) return (error.value = '휴대폰 번호를 정확히 입력해 주세요')
  busy.value = true
  try {
    store.setUser(await api.login(name.value.trim(), phone.value))
    router.replace(route.query.next || '/')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="stack" style="padding-top: 32px; gap: 22px">
    <img :src="base + 'icon.svg'" alt="" width="64" height="64" />
    <div class="stack" style="gap: 6px">
      <span v-if="IS_MOCK" class="pill tone-warn" style="align-self: flex-start">목업 · 서버 없이 이 브라우저 안에서만 동작</span>
      <h1>돈 보내기 전에, 한 번 더.</h1>
      <p class="muted">의심스러운 문자를 AI가 살펴보고, 미리 등록한 가족에게 "이거 진짜 너야?"를 대신 물어봐요.</p>
    </div>

    <section v-if="IS_MOCK" class="card soft">
      <h3>바로 시연해 보기</h3>
      <p class="muted small">탭 두 개를 열어 하나는 엄마, 하나는 딸로 시작하면 확인 요청을 실제로 주고받을 수 있어요.</p>
      <button v-for="(p, key) in PERSONAS" :key="key" class="btn block" :class="key === 'mom' ? 'primary' : 'ghost'" :disabled="busy" @click="quickStart(key)" style="justify-content: space-between">
        <span>{{ p.label }}</span><span style="font-weight: 500; font-size: 13px; opacity: 0.85">{{ p.desc }}</span>
      </button>
    </section>

    <form class="card" @submit.prevent="submit">
      <h3 v-if="IS_MOCK">직접 가입하기</h3>
      <label>이름<input v-model="name" autocomplete="name" placeholder="홍길동" /></label>
      <label>휴대폰 번호<input v-model="phone" inputmode="tel" autocomplete="tel" placeholder="010-0000-0000" /></label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn block" :class="IS_MOCK ? 'ghost' : 'primary'" :disabled="busy">{{ busy ? '잠시만요…' : '시작하기' }}</button>
      <p class="notice">가족이 내 번호를 등록해 두면, 이 번호로 가입했을 때 확인 요청을 받을 수 있어요.</p>
    </form>
  </section>
</template>
