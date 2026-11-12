<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'
import { store } from '../store.js'

const list = ref([])
const name = ref('')
const relation = ref('')
const phone = ref('')
const error = ref('')
const RELATIONS = ['딸', '아들', '엄마', '아빠', '배우자', '형제자매', '친구']

async function load() {
  list.value = await api.contacts(store.user.id)
}
onMounted(load)

async function add() {
  error.value = ''
  if (!name.value.trim()) return (error.value = '이름을 입력해 주세요')
  if (phone.value.replace(/\D/g, '').length < 10) return (error.value = '휴대폰 번호를 정확히 입력해 주세요')
  try {
    await api.addContact(store.user.id, { name: name.value, relation: relation.value, phone: phone.value })
    name.value = relation.value = phone.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function remove(c) {
  await api.deleteContact(store.user.id, c.id)
  await load()
}

function fmt(p) {
  return p.replace(/^(\d{3})(\d{3,4})(\d{4})$/, '$1-$2-$3')
}
</script>

<template>
  <h1>확인해 줄 가족·친구</h1>
  <p class="muted">의심 연락이 오면 위에서부터 차례로 확인 요청이 가요. 사기범이 "새 번호"를 대도, 여기 등록된 <b>원래 번호</b>로 물어보기 때문에 속지 않아요.</p>

  <section class="stack">
    <div v-for="(c, i) in list" :key="c.id" class="card">
      <div class="between">
        <span>
          <span class="pill tone-info">{{ i + 1 }}순위</span>
          <b style="margin-left: 6px">{{ c.relation || '지인' }} {{ c.name }}</b><br />
          <span class="muted small">{{ fmt(c.phone) }}</span>
        </span>
        <span class="row">
          <span class="pill" :class="c.joined ? 'tone-ok' : 'tone-muted'">{{ c.joined ? '앱 사용 중' : '미가입' }}</span>
          <button class="btn ghost small" :aria-label="`${c.name} 삭제`" @click="remove(c)">삭제</button>
        </span>
      </div>
    </div>
    <p v-if="!list.length" class="muted">아직 등록한 사람이 없어요.</p>
  </section>

  <form class="card" @submit.prevent="add">
    <h3>새로 등록</h3>
    <div class="chips">
      <button v-for="r in RELATIONS" :key="r" type="button" class="chip" :class="{ on: relation === r }" @click="relation = r">{{ r }}</button>
    </div>
    <label>이름<input v-model="name" placeholder="김지은" /></label>
    <label>휴대폰 번호 (원래 쓰던 번호)<input v-model="phone" inputmode="tel" placeholder="010-0000-0000" /></label>
    <p v-if="error" class="error">{{ error }}</p>
    <button class="btn primary block">등록하기</button>
    <p class="notice">시연할 때는 등록한 번호로 다른 폰이나 다른 브라우저에서 가입하면, 그쪽에 확인 요청이 도착해요.</p>
  </form>
</template>
