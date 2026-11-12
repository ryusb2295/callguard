<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api, STATUS, fmtTime } from '../api.js'
import AnalysisResult from '../components/AnalysisResult.vue'

const props = defineProps({ id: { type: String, required: true } })
const c = ref(null)
const error = ref('')
let timer = null

async function load() {
  try {
    c.value = await api.getCase(props.id)
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 2000)
})
onUnmounted(() => clearInterval(timer))

const REQ = {
  sent: { label: '답을 기다리는 중', tone: 'info' },
  yes: { label: '"맞아요 / 괜찮아요"', tone: 'ok' },
  no: { label: '"아니에요 / 사지 마요"', tone: 'danger' },
  unknown: { label: '"잘 모르겠어요"', tone: 'warn' },
  expired: { label: '응답 없음', tone: 'muted' }
}

const outcome = computed(() => {
  if (!c.value) return null
  const s = c.value.status
  const who = c.value.claimed_sender || '상대방'
  const m = c.value.analysis.mode
  if (m === 'shop' || m === 'ingredients') {
    if (s === 'confirmed_fake') return { tone: 'danger', title: '가족이 사지 말래요', body: '결제를 멈추세요. 이미 결제했다면 카드사에 문의하고 1372 소비자상담센터에 연락하세요.' }
    if (s === 'confirmed_real') return { tone: 'ok', title: '가족이 괜찮아 보인대요', body: '그래도 카드 결제를 쓰고 주문 화면을 캡처해 두세요.' }
    if (s === 'unverified') return { tone: 'warn', title: '아직 아무도 확인해 주지 못했어요', body: '위험 신호가 있다면 결제를 미루는 게 안전해요.' }
    if (s === 'waiting') return { tone: 'info', title: '가족에게 같이 봐 달라고 했어요', body: '답이 오면 이 화면이 바로 바뀌어요.' }
    return null
  }
  if (s === 'confirmed_fake') return { tone: 'danger', title: '사칭일 가능성이 높아요', body: `등록된 가족이 직접 보낸 연락이 아니라고 답했어요. 송금하지 말고, 이미 보냈다면 바로 1394·1332에 연락하세요.` }
  if (s === 'confirmed_real') return { tone: 'ok', title: '본인이 보낸 연락이래요', body: `그래도 큰돈이라면 ${who}에게 원래 번호로 한 번 더 전화해서 직접 들어 보세요.` }
  if (s === 'unverified') return { tone: 'warn', title: '아직 아무도 확인해 주지 못했어요', body: `확인되기 전에는 송금하지 마세요. ${who}의 원래 번호로 직접 전화하거나, 아래 공식 기관에 물어보세요.` }
  if (s === 'waiting') return { tone: 'info', title: '가족에게 확인 중이에요', body: '답이 오면 이 화면이 바로 바뀌어요. 그동안 송금은 잠시 멈춰 주세요.' }
  return null
})

const active = computed(() => c.value?.requests.find((r) => r.status === 'sent'))
const pct = computed(() => c.value && c.value.seconds_left != null ? (c.value.seconds_left / c.value.escalate_seconds) * 100 : 0)
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="c">
    <section v-if="outcome" class="hero" :class="outcome.tone">
      <span class="big">{{ outcome.title }}</span>
      <span>{{ outcome.body }}</span>
      <template v-if="active">
        <span class="small" style="margin-top: 6px">{{ active.contact_relation }} {{ active.contact_name }}님 응답 대기 · {{ c.seconds_left }}초 뒤 다음 사람에게</span>
        <div class="progress"><i :style="{ width: pct + '%' }"></i></div>
      </template>
    </section>

    <section v-if="c.requests.length" class="card">
      <h3>확인 요청 진행</h3>
      <ul class="timeline">
        <li v-for="r in c.requests" :key="r.id">
          <span>
            <b>{{ r.contact_relation }} {{ r.contact_name }}</b><br />
            <span class="muted small">{{ fmtTime(r.sent_at) }} 보냄{{ r.note ? ` · "${r.note}"` : '' }}</span>
          </span>
          <span class="pill" :class="`tone-${REQ[r.status].tone}`">{{ REQ[r.status].label }}</span>
        </li>
      </ul>
    </section>

    <section v-if="c.status === 'unverified' || c.status === 'confirmed_fake'" class="card">
      <h3>공식 기관에 바로 연락하기</h3>
      <a v-for="o in c.analysis.official" :key="o.phone" :href="`tel:${o.phone}`" class="btn ghost block" style="justify-content: space-between">
        <span style="font-weight: 500; font-size: 15px">{{ o.name }}</span><span>{{ o.phone }}</span>
      </a>
    </section>

    <section class="card">
      <div class="between">
        <h3>받은 내용</h3>
        <span class="pill" :class="`tone-${STATUS[c.status].tone}`">{{ STATUS[c.status].label }}</span>
      </div>
      <span v-if="(c.analysis.mode || 'message') === 'message'" class="muted small">자칭 발신자: {{ c.claimed_sender || '알 수 없음' }}</span>
      <div class="quote">{{ c.message }}</div>
    </section>

    <AnalysisResult :analysis="c.analysis" />
  </template>
</template>
