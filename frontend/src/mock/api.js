// 목업(GitHub Pages)용 API. 서버 대신 브라우저 localStorage에 저장한다.
// 같은 브라우저의 다른 탭과 데이터를 공유하므로, 탭 하나는 엄마·하나는 딸로 열면 확인 요청을 주고받을 수 있다.
import { analyze, SAMPLES } from './engine.js'

const KEY = 'callguard-mock-db-v1'
export const ESCALATE_SECONDS = 60

const now = () => Date.now() / 1000
const digits = (p) => String(p || '').replace(/\D/g, '')

function load() {
  try {
    const db = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (db && db.users) return db
  } catch {
    /* 깨진 데이터는 새로 만든다 */
  }
  return { seq: 1, users: [], contacts: [], cases: [], requests: [] }
}
function save(db) {
  try {
    localStorage.setItem(KEY, JSON.stringify(db))
  } catch {
    /* 저장 공간이 없어도 화면은 동작 */
  }
}
function tx(fn) {
  const db = load()
  const out = fn(db)
  save(db)
  return out
}
const nextId = (db) => db.seq++
const fail = (msg) => { throw new Error(msg) }
const delay = (ms) => new Promise((r) => setTimeout(r, ms))

function contactsOf(db, uid) {
  return db.contacts.filter((c) => c.owner_id === uid).sort((a, b) => a.priority - b.priority || a.id - b.id)
}

function sendRequest(db, caseRow, contact) {
  db.requests.push({ id: nextId(db), case_id: caseRow.id, contact_id: contact.id, to_phone: digits(contact.phone), status: 'sent', note: '', sent_at: now(), responded_at: null })
  caseRow.status = 'waiting'
  caseRow.updated_at = now()
}

function nextContact(db, caseRow) {
  const asked = new Set(db.requests.filter((r) => r.case_id === caseRow.id).map((r) => r.contact_id))
  return contactsOf(db, caseRow.owner_id).find((c) => !asked.has(c.id))
}

function advance(db, caseRow) {
  const nxt = nextContact(db, caseRow)
  if (nxt) sendRequest(db, caseRow, nxt)
  else {
    caseRow.status = 'unverified'
    caseRow.updated_at = now()
  }
}

function processCase(db, caseRow) {
  if (!caseRow || caseRow.status !== 'waiting') return
  const active = [...db.requests].reverse().find((r) => r.case_id === caseRow.id && r.status === 'sent')
  if (active && now() - active.sent_at > ESCALATE_SECONDS) {
    active.status = 'expired'
    advance(db, caseRow)
  }
}

function caseView(db, id) {
  const c = db.cases.find((x) => x.id === Number(id))
  if (!c) fail('사례를 찾을 수 없어요')
  processCase(db, c)
  const requests = db.requests.filter((r) => r.case_id === c.id).map((r) => {
    const ct = db.contacts.find((x) => x.id === r.contact_id) || {}
    return { ...r, contact_name: ct.name, contact_relation: ct.relation }
  })
  const active = requests.find((r) => r.status === 'sent')
  return {
    ...c,
    requests,
    seconds_left: active ? Math.max(0, Math.round(ESCALATE_SECONDS - (now() - active.sent_at))) : null,
    escalate_seconds: ESCALATE_SECONDS,
    owner: db.users.find((u) => u.id === c.owner_id)
  }
}

export const mockApi = {
  async login(name, phone) {
    return tx((db) => {
      const p = digits(phone)
      let u = db.users.find((x) => x.phone === p)
      if (u) u.name = name.trim()
      else {
        u = { id: nextId(db), name: name.trim(), phone: p, created_at: now() }
        db.users.push(u)
      }
      return { ...u }
    })
  },
  async contacts(uid) {
    const db = load()
    return contactsOf(db, uid).map((c) => ({ ...c, joined: db.users.some((u) => u.phone === digits(c.phone)) }))
  },
  async addContact(uid, c) {
    return tx((db) => {
      const p = digits(c.phone)
      if (db.contacts.some((x) => x.owner_id === uid && x.phone === p)) fail('이미 등록된 번호예요')
      const row = { id: nextId(db), owner_id: uid, name: c.name.trim(), relation: (c.relation || '').trim(), phone: p, priority: contactsOf(db, uid).length, created_at: now() }
      db.contacts.push(row)
      return row
    })
  },
  async deleteContact(uid, cid) {
    tx((db) => { db.contacts = db.contacts.filter((x) => !(x.id === cid && x.owner_id === uid)) })
    return { ok: true }
  },
  async analyze(message, sender) {
    await delay(500)
    return analyze(message, sender)
  },
  async createCase(uid, message, sender) {
    await delay(700) // 분석하는 느낌을 주기 위한 짧은 대기
    return tx((db) => {
      const c = { id: nextId(db), owner_id: uid, message, claimed_sender: sender || '', analysis: analyze(message, sender), status: 'draft', created_at: now(), updated_at: now() }
      db.cases.push(c)
      return caseView(db, c.id)
    })
  },
  async sendCase(id, contactId) {
    return tx((db) => {
      const c = db.cases.find((x) => x.id === Number(id))
      if (!c) fail('사례를 찾을 수 없어요')
      const list = contactsOf(db, c.owner_id)
      if (!list.length) fail('먼저 확인해 줄 가족·친구를 등록해 주세요')
      if (!db.requests.some((r) => r.case_id === c.id && r.status === 'sent')) {
        const target = list.find((x) => x.id === contactId) || nextContact(db, c)
        if (!target) fail('더 보낼 연락처가 없어요')
        sendRequest(db, c, target)
      }
      return caseView(db, c.id)
    })
  },
  async getCase(id) {
    return tx((db) => caseView(db, id))
  },
  async cases(uid) {
    return tx((db) => db.cases.filter((c) => c.owner_id === uid).sort((a, b) => b.id - a.id).slice(0, 20).map((c) => {
      const v = caseView(db, c.id)
      return { id: v.id, message: v.message, claimed_sender: v.claimed_sender, status: v.status, created_at: v.created_at, risk_level: v.analysis.risk_level, type_label: v.analysis.type_label }
    }))
  },
  async inbox(uid) {
    return tx((db) => {
      const u = db.users.find((x) => x.id === uid)
      if (!u) fail('사용자를 찾을 수 없어요')
      db.cases.forEach((c) => processCase(db, c))
      return db.requests.filter((r) => r.to_phone === u.phone).sort((a, b) => b.id - a.id).slice(0, 20).map((r) => {
        const c = db.cases.find((x) => x.id === r.case_id)
        const owner = db.users.find((x) => x.id === c.owner_id)
        return { ...r, from_name: owner?.name, message: c.message, claimed_sender: c.claimed_sender, summary: c.analysis.summary, signals: c.analysis.signals, risk_level: c.analysis.risk_level, type_label: c.analysis.type_label, mode: c.analysis.mode || 'message' }
      })
    })
  },
  async respond(rid, answer, note) {
    return tx((db) => {
      const r = db.requests.find((x) => x.id === rid)
      if (!r) fail('요청을 찾을 수 없어요')
      if (r.status !== 'sent') fail('이미 처리된 요청이에요')
      Object.assign(r, { status: answer, note: note || '', responded_at: now() })
      const c = db.cases.find((x) => x.id === r.case_id)
      if (answer === 'yes') c.status = 'confirmed_real'
      else if (answer === 'no') c.status = 'confirmed_fake'
      else advance(db, c)
      c.updated_at = now()
      return { ok: true }
    })
  },
  async samples() {
    return SAMPLES
  },
  async health() {
    return { ok: true, mock: true, escalate_seconds: ESCALATE_SECONDS, apis: { demo_mode: true, nts: false, ftc_csv: false, safe_browsing: false, virustotal: false, rdap: false, llm: false } }
  },
  reset() {
    localStorage.removeItem(KEY)
  }
}
