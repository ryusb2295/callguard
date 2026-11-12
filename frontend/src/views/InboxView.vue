<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { api, LEVEL, fmtTime } from '../api.js'
import { store } from '../store.js'

const items = ref([])
const notes = ref({})
const error = ref('')
let timer = null

async function load() {
  try {
    items.value = await api.inbox(store.user.id)
  } catch (e) {
    error.value = e.message
  }
}
onMounted(() => {
  load()
  timer = setInterval(load, 3000)
})
onUnmounted(() => clearInterval(timer))

async function answer(r, a) {
  try {
    await api.respond(r.id, a, notes.value[r.id] || '')
    await load()
  } catch (e) {
    error.value = e.message
  }
}

const DONE_SHOP = { yes: '"괜찮아 보여요"라고 답했어요', no: '"사지 마세요"라고 답했어요', unknown: '"잘 모르겠어요"라고 답했어요', expired: '시간이 지나 다른 가족에게 넘어갔어요' }
const DONE = { yes: '"제가 보낸 거 맞아요"라고 답했어요', no: '"저 아니에요"라고 답했어요', unknown: '"잘 모르겠어요"라고 답했어요', expired: '시간이 지나 다른 가족에게 넘어갔어요' }
</script>

<template>
  <h1>받은 확인 요청</h1>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-if="!items.length" class="muted">아직 받은 요청이 없어요. 가족이 나를 등록해 두면 여기로 와요.</p>

  <section v-for="r in items" :key="r.id" class="card" :style="r.status === 'sent' ? 'border-color: #93c5fd; border-width: 2px' : ''">
    <div class="between">
      <b>{{ r.from_name }}님의 확인 요청</b>
      <span class="muted small">{{ fmtTime(r.sent_at) }}</span>
    </div>
    <p v-if="r.mode === 'shop'" style="font-size: 17px; font-weight: 700">이 쇼핑몰에서 사려고 한대요. 같이 봐 주세요.</p>
    <p v-else-if="r.mode === 'ingredients'" style="font-size: 17px; font-weight: 700">이 직구 제품을 사려고 한대요. 같이 봐 주세요.</p>
    <p v-else style="font-size: 17px; font-weight: 700">"{{ r.claimed_sender || '누군가' }}"라는 사람에게서 이런 연락을 받았대요. 혹시 직접 보내셨나요?</p>
    <div class="quote">{{ r.message }}</div>
    <div class="row">
      <span class="pill" :class="`tone-${LEVEL[r.risk_level].tone}`">{{ r.type_label }}</span>
    </div>
    <div class="quote small" style="background: var(--blue-soft)">요약: {{ r.summary }}</div>

    <template v-if="r.status === 'sent'">
      <input v-model="notes[r.id]" :placeholder="r.mode === 'message' ? '한마디 남기기 (선택) 예: 나 폰 멀쩡해!' : '한마디 남기기 (선택) 예: 국내 정품으로 사자'" />
      <div v-if="r.mode === 'shop' || r.mode === 'ingredients'" class="stack" style="gap: 8px">
        <button class="btn danger block" @click="answer(r, 'no')">사지 마세요</button>
        <button class="btn ok block" @click="answer(r, 'yes')">괜찮아 보여요</button>
        <button class="btn ghost block" @click="answer(r, 'unknown')">잘 모르겠어요 (다른 가족에게 넘기기)</button>
      </div>
      <div v-else class="stack" style="gap: 8px">
        <button class="btn danger block" @click="answer(r, 'no')">아니요, 제가 보낸 거 아니에요</button>
        <button class="btn ok block" @click="answer(r, 'yes')">네, 제가 보낸 거 맞아요</button>
        <button class="btn ghost block" @click="answer(r, 'unknown')">잘 모르겠어요 (다른 가족에게 넘기기)</button>
      </div>
    </template>
    <p v-else class="muted">{{ (r.mode === 'shop' || r.mode === 'ingredients' ? DONE_SHOP : DONE)[r.status] }}</p>
  </section>
</template>
