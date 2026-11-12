<script setup>
import { computed } from 'vue'
import { LEVEL } from '../api.js'

const props = defineProps({ analysis: { type: Object, required: true } })
const a = computed(() => props.analysis)
const level = computed(() => LEVEL[a.value.risk_level])
const CHECK_TONE = { danger: 'danger', warn: 'warn', ok: 'ok', unknown: 'unknown' }
const CHECK_LABEL = { danger: '위험', warn: '주의', ok: '정상', unknown: '확인 불가' }
const flagged = computed(() => new Set(a.value.checks.flatMap((c) => (c.status === 'danger' && c.matched) || [])))
const dangerCount = computed(() => a.value.checks.filter((c) => c.status === 'danger').length)
const TYPE_NAME = { url: '링크', biz: '사업자', account: '계좌', ingredient: '성분' }
</script>

<template>
  <section class="hero" :class="level.tone">
    <span class="small" style="font-weight: 700">{{ a.type_label }}</span>
    <span class="big">{{ level.label }}</span>
    <span class="small">위험 점수 {{ a.score }} / 100 · {{ a.signals.length ? `신호 ${a.signals.length}개` : `위험 확인 ${dangerCount}건` }}{{ a.ai_used ? ' · AI 분석 포함' : '' }}</span>
  </section>

  <section v-if="a.seller" class="card">
    <div class="between">
      <h3>쇼핑몰에서 찾은 판매자 정보</h3>
      <span v-if="a.demo_page" class="pill tone-muted">시연용 페이지</span>
    </div>
    <p v-if="!a.page_read" class="muted small">쇼핑몰 페이지를 열지 못해서 링크 검사만 했어요.</p>
    <dl v-else class="kv">
      <dt>상호</dt><dd>{{ a.seller.business_name || '표시 없음' }}</dd>
      <dt>대표자</dt><dd>{{ a.seller.ceo || '표시 없음' }}</dd>
      <dt>사업자번호</dt><dd :style="!a.seller.biz_number && 'color: var(--danger)'">{{ a.seller.biz_number || '찾지 못함' }}</dd>
      <dt>통신판매 신고</dt><dd :style="!a.seller.telecom_number && 'color: var(--warn)'">{{ a.seller.telecom_number || '표시 없음' }}</dd>
      <dt>연락처</dt><dd>{{ a.seller.phone || '표시 없음' }}</dd>
    </dl>
  </section>

  <section v-if="a.entities && a.entities.ingredients" class="card">
    <h3>읽어 낸 성분 {{ a.entities.ingredients.length }}개</h3>
    <div class="chips">
      <span v-for="i in a.entities.ingredients" :key="i" class="pill" :class="flagged.has(i) ? 'tone-danger' : 'tone-muted'">{{ i }}</span>
    </div>
  </section>

  <section v-if="a.signals.length" class="card">
    <h3>이런 점이 눈에 띄어요</h3>
    <ul class="list">
      <li v-for="s in a.signals" :key="s.label">
        <span class="dot" :style="{ background: s.weight >= 30 ? '#dc2626' : s.weight >= 15 ? '#ea580c' : '#2563eb' }"></span>
        <span>
          <b>{{ s.label }}</b>
          <span v-if="s.source === 'ai'" class="pill tone-info" style="margin-left: 6px">AI</span>
          <br /><span class="muted small">"…{{ s.evidence }}…"</span>
        </span>
      </li>
    </ul>
  </section>

  <section v-if="a.checks.length" class="card">
    <h3>공식 데이터로 확인했어요</h3>
    <ul class="list">
      <li v-for="(c, i) in a.checks" :key="i" style="justify-content: space-between">
        <span>
          <b>{{ c.source }}</b>
          <span v-if="c.demo" class="pill tone-muted" style="margin-left: 6px">시연용</span>
          <br /><span class="muted small">{{ TYPE_NAME[c.type] || c.type }} {{ c.target }}</span>
          <br /><span class="small">{{ c.detail }}</span>
          <template v-if="c.link"><br /><a :href="c.link" target="_blank" rel="noopener" class="small">{{ c.link }}</a></template>
        </span>
        <span class="pill" :class="`tone-${CHECK_TONE[c.status]}`">{{ CHECK_LABEL[c.status] }}</span>
      </li>
    </ul>
  </section>

  <section class="card soft">
    <h3>지금 이렇게 하세요</h3>
    <ul class="list">
      <li v-for="g in a.guide" :key="g"><span class="dot"></span><span>{{ g }}</span></li>
    </ul>
  </section>

  <p class="notice">{{ a.notice }}</p>
</template>
