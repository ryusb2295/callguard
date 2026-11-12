<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, STATUS, LEVEL, fmtTime, IS_MOCK } from '../api.js'
import { store } from '../store.js'

const router = useRouter()
const cases = ref([])
const contacts = ref([])
const inbox = ref([])
const apis = ref(null)

onMounted(async () => {
  const uid = store.user.id
  const [c, ct, ib, h] = await Promise.allSettled([api.cases(uid), api.contacts(uid), api.inbox(uid), api.health()])
  if (c.status === 'fulfilled') cases.value = c.value
  if (ct.status === 'fulfilled') contacts.value = ct.value
  if (ib.status === 'fulfilled') inbox.value = ib.value.filter((r) => r.status === 'sent')
  if (h.status === 'fulfilled') apis.value = h.value.apis
})

const base = import.meta.env.BASE_URL

function resetDemo() {
  api.reset()
  store.setUser(null)
  router.replace('/start')
}

function logout() {
  store.setUser(null)
  router.replace('/start')
}

const API_NAMES = {
  nts: '국세청 사업자',
  ftc_csv: '공정위 통신판매',
  safe_browsing: 'Safe Browsing',
  virustotal: 'VirusTotal',
  rdap: '도메인 생성일',
  llm: 'AI 분석(LLM)'
}
</script>

<template>
  <section v-if="IS_MOCK" class="card" style="border-color: #fdba74; background: #fff7ed">
    <div class="between">
      <b style="color: #9a3412">목업으로 시연 중</b>
      <span class="pill tone-warn">서버 없음</span>
    </div>
    <p class="small" style="color: #7c2d12">분석은 브라우저 안에서 규칙으로 하고, 공식 데이터 조회는 시연용 주소·번호에만 결과가 나와요. 가족 확인 요청은 같은 브라우저의 다른 탭과 주고받아요.</p>
    <div class="row" style="gap: 8px">
      <a :href="`${base}#/start?as=daughter`" target="_blank" rel="noopener" class="btn ghost small" style="flex: 1">딸 화면 새 탭으로</a>
      <a :href="`${base}#/start?as=son`" target="_blank" rel="noopener" class="btn ghost small" style="flex: 1">아들 화면 새 탭으로</a>
    </div>
  </section>

  <RouterLink v-if="inbox.length" to="/inbox" class="hero danger" style="text-decoration: none">
    <span class="big">확인 요청 {{ inbox.length }}건이 와 있어요</span>
    <span class="small">{{ inbox[0].from_name }}님이 "{{ inbox[0].claimed_sender || '누군가' }}"의 연락이 진짜인지 물어봤어요.</span>
  </RouterLink>

  <section class="card soft">
    <h2>돈 보내기 전에, 한 번 더</h2>
    <p class="muted">의심스러운 문자·카톡·링크를 붙여넣으면 AI와 공식 데이터가 먼저 보고, 등록한 가족이 마지막으로 확인해 줘요.</p>
    <RouterLink to="/analyze" class="btn primary block">의심 연락 확인하기</RouterLink>
  </section>

  <section v-if="!contacts.length" class="card">
    <h3>먼저 확인해 줄 가족을 등록하세요</h3>
    <p class="muted">사기범은 "폰이 고장 나서 새 번호야"라고 해요. 미리 등록한 원래 번호로 확인해야 속지 않아요.</p>
    <RouterLink to="/contacts" class="btn ghost block">가족·친구 등록하기</RouterLink>
  </section>
  <section v-else class="card">
    <div class="between">
      <h3>확인해 줄 사람 {{ contacts.length }}명</h3>
      <RouterLink to="/contacts" class="small">관리</RouterLink>
    </div>
    <div class="chips">
      <span v-for="c in contacts" :key="c.id" class="pill" :class="c.joined ? 'tone-ok' : 'tone-muted'">
        {{ c.relation || '지인' }} {{ c.name }}{{ c.joined ? '' : ' · 미가입' }}
      </span>
    </div>
  </section>

  <section class="stack">
    <h3>최근 확인 기록</h3>
    <p v-if="!cases.length" class="muted">아직 기록이 없어요.</p>
    <RouterLink v-for="c in cases" :key="c.id" :to="`/case/${c.id}`" class="card" style="text-decoration: none; color: inherit">
      <div class="between">
        <span class="pill" :class="`tone-${LEVEL[c.risk_level].tone}`">{{ c.type_label }}</span>
        <span class="pill" :class="`tone-${STATUS[c.status].tone}`">{{ STATUS[c.status].label }}</span>
      </div>
      <p style="overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical">{{ c.message }}</p>
      <span class="muted small">{{ fmtTime(c.created_at) }}</span>
    </RouterLink>
  </section>

  <section v-if="apis && !IS_MOCK" class="card">
    <h3>연결된 확인 데이터</h3>
    <div class="chips">
      <span v-for="(name, key) in API_NAMES" :key="key" class="pill" :class="apis[key] ? 'tone-ok' : 'tone-muted'">
        {{ name }} {{ apis[key] ? '연결됨' : '미설정' }}
      </span>
      <span v-if="apis.demo_mode" class="pill tone-info">시연 모드</span>
    </div>
  </section>

  <div class="row" style="justify-content: center; gap: 8px">
    <button class="btn ghost small" @click="logout">다른 번호로 시작하기</button>
    <button v-if="IS_MOCK" class="btn ghost small" @click="resetDemo">시연 기록 초기화</button>
  </div>
</template>
