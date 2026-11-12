<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'
import { store } from '../store.js'
import AnalysisResult from '../components/AnalysisResult.vue'

const route = useRoute()
const router = useRouter()

// 입력창은 하나. 링크만 넣으면 서버가 알아서 쇼핑몰·사이트 확인으로 처리한다
const initialText = String(route.query.text || '')

const message = ref(initialText)
const sender = ref('')
const SENDERS = ['딸', '아들', '엄마', '아빠', '친구', '검찰·경찰', '은행·카드사', '택배']
const samples = ref([])
const contacts = ref([])
const result = ref(null)
const target = ref(null)
const busy = ref(false)
const ocrBusy = ref(false)
const ocrProgress = ref(0)
const error = ref('')

onMounted(async () => {
  const [s, c] = await Promise.allSettled([api.samples(), api.contacts(store.user.id)])
  if (s.status === 'fulfilled') samples.value = s.value
  if (c.status === 'fulfilled') contacts.value = c.value
})

function useSample(s) {
  message.value = s.message
  sender.value = s.claimed_sender
  result.value = null
}

async function onImage(e) {
  const file = e.target.files?.[0]
  if (!file) return
  error.value = ''
  ocrBusy.value = true
  ocrProgress.value = 0
  try {
    // 무거운 OCR 라이브러리는 사진을 올릴 때만 불러온다
    const { createWorker } = await import('tesseract.js')
    const langs = ['kor', 'eng']
    const worker = await createWorker(langs, 1, {
      logger: (m) => { if (m.status === 'recognizing text') ocrProgress.value = Math.round(m.progress * 100) }
    })
    const { data } = await worker.recognize(file)
    await worker.terminate()
    const text = data.text.replace(/[ \t]+\n/g, '\n').trim()
    message.value = message.value ? `${message.value}\n${text}` : text
    if (!text) error.value = '사진에서 글자를 찾지 못했어요. 내용을 직접 붙여넣어 주세요.'
  } catch {
    error.value = '사진을 읽지 못했어요. 내용을 직접 붙여넣어 주세요.'
  } finally {
    ocrBusy.value = false
    e.target.value = ''
  }
}

async function analyze() {
  error.value = ''
  if (!message.value.trim()) return (error.value = '확인할 내용을 입력해 주세요')
  busy.value = true
  try {
    result.value = await api.createCase(store.user.id, message.value.trim(), sender.value.trim())
    const match = contacts.value.find((c) => c.relation && sender.value && sender.value.includes(c.relation))
    target.value = (match || contacts.value[0])?.id ?? null
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

const targetContact = computed(() => contacts.value.find((c) => c.id === target.value))
const askTitle = computed(() => result.value?.analysis.mode === 'shop' ? '가족에게 같이 봐 달라고 할까요?' : '가족에게 진짜인지 물어볼까요?')

async function send() {
  busy.value = true
  error.value = ''
  try {
    await api.sendCase(result.value.id, target.value)
    router.push(`/case/${result.value.id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <h1>의심 연락 확인</h1>

  <template v-if="!result">
    <section class="card">
      <label>받은 내용
        <textarea v-model="message" placeholder="문자·카톡 내용이나 받은 링크를 그대로 붙여넣어 주세요"></textarea>
      </label>
      <label class="btn ghost block" style="flex-direction: row; font-size: 15px">
        <input type="file" accept="image/*" style="display: none" @change="onImage" :disabled="ocrBusy" />
        {{ ocrBusy ? `캡처에서 글자 읽는 중 ${ocrProgress}%` : '캡처 사진으로 넣기' }}
      </label>
      <p class="notice">문자 속 링크·계좌·사업자번호는 자동으로 공식 데이터와 대조해요. 링크만 넣으면 그 사이트의 판매자 정보를 확인해요.</p>
    </section>

    <section class="card">
      <label>누구라고 하면서 연락이 왔나요? (선택)
        <input v-model="sender" placeholder="예: 딸, 은행, 택배" />
      </label>
      <div class="chips">
        <button v-for="s in SENDERS" :key="s" type="button" class="chip" :class="{ on: sender === s }" @click="sender = s">{{ s }}</button>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <button class="btn primary block" :disabled="busy || ocrBusy" @click="analyze">{{ busy ? '확인 중…' : '위험 신호 확인하기' }}</button>

    <section v-if="samples.length" class="stack">
      <h3>시연용 예시</h3>
      <div class="chips">
        <button v-for="s in samples" :key="s.title" class="chip" @click="useSample(s)">{{ s.title }}</button>
      </div>
    </section>
  </template>

  <template v-else>
    <AnalysisResult :analysis="result.analysis" />

    <section class="card">
      <h3>{{ askTitle }}</h3>
      <template v-if="contacts.length">
        <p class="muted">아래 사람의 <b>원래 등록된 번호</b>로 요청이 가요. 답이 없으면 {{ result.escalate_seconds }}초 뒤 다음 사람에게 넘어가요.</p>
        <div class="chips">
          <button v-for="c in contacts" :key="c.id" class="chip" :class="{ on: target === c.id }" @click="target = c.id">
            {{ c.relation || '지인' }} {{ c.name }}
          </button>
        </div>
        <div class="quote small">{{ result.analysis.summary }}</div>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn primary block" :disabled="busy || !target" @click="send">
          {{ targetContact ? `${targetContact.name}님에게 확인 요청 보내기` : '확인 요청 보내기' }}
        </button>
      </template>
      <template v-else>
        <p class="muted">아직 등록한 가족이 없어요.</p>
        <RouterLink to="/contacts" class="btn ghost block">가족 등록하러 가기</RouterLink>
      </template>
      <button class="btn ghost block" @click="result = null">다른 내용 확인하기</button>
    </section>
  </template>
</template>
