async function request(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = typeof data.detail === 'string' ? data.detail : '요청을 처리하지 못했어요'
    throw new Error(msg)
  }
  return data
}

import { mockApi } from './mock/api.js'

// VITE_MOCK=1로 빌드하면 서버 없이 브라우저 안에서 동작하는 목업(GitHub Pages용)이 된다
export const IS_MOCK = import.meta.env.VITE_MOCK === '1'

const realApi = {
  login: (name, phone) => request('POST', '/users', { name, phone }),
  contacts: (uid) => request('GET', `/users/${uid}/contacts`),
  addContact: (uid, c) => request('POST', `/users/${uid}/contacts`, c),
  deleteContact: (uid, cid) => request('DELETE', `/users/${uid}/contacts/${cid}`),
  analyze: (message, claimed_sender) => request('POST', '/analyze', { message, claimed_sender }),
  createCase: (user_id, message, claimed_sender, mode = 'auto') => request('POST', '/cases', { user_id, message, claimed_sender, mode }),
  sendCase: (id, contact_id) => request('POST', `/cases/${id}/send`, { contact_id }),
  getCase: (id) => request('GET', `/cases/${id}`),
  cases: (uid) => request('GET', `/users/${uid}/cases`),
  inbox: (uid) => request('GET', `/users/${uid}/inbox`),
  respond: (rid, answer, note) => request('POST', `/requests/${rid}/respond`, { answer, note }),
  samples: () => request('GET', '/samples'),
  health: () => request('GET', '/health')
}

export const api = IS_MOCK ? mockApi : realApi

export const STATUS = {
  draft: { label: '분석 완료', tone: 'muted' },
  waiting: { label: '가족 확인 기다리는 중', tone: 'info' },
  confirmed_real: { label: '본인 확인됨', tone: 'ok' },
  confirmed_fake: { label: '본인이 아니래요', tone: 'danger' },
  unverified: { label: '확인되지 않음', tone: 'warn' }
}

export const LEVEL = {
  high: { label: '위험 신호 많음', tone: 'danger' },
  medium: { label: '주의 필요', tone: 'warn' },
  low: { label: '뚜렷한 신호 없음', tone: 'ok' }
}

export function fmtTime(ts) {
  const d = new Date(ts * 1000)
  return d.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
