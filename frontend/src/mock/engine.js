// 목업(GitHub Pages)용 분석 엔진. backend/app/signals.py, shop.py, external.py의 규칙을 브라우저로 옮긴 것.
// 외부 API(국세청·공정위·Safe Browsing 등)는 부를 수 없으므로 시연용 데이터만 결과를 주고, 나머지는 "서버 버전에서 조회"로 표시한다.

const RULES = [
  ['money', '송금·입금 요구', 30, [/송금/, /이체/, /입금/, /보내\s*(줘|주|줄|달)/, /계좌/, /돈\s*(좀|이|을)/, /\d+\s*만\s*원/, /결제\s*(해|좀)/, /상품권/, /기프트\s*카드/]],
  ['urgency', '급하게 재촉', 15, [/급(해|하|히)/, /빨리/, /당장/, /오늘\s*(안|까지)/, /지금\s*바로/, /긴급/, /시간\s*(이\s*)?없/, /서둘/]],
  ['number_changed', '번호 변경·폰 고장 주장', 30, [/(폰|핸드폰|휴대폰|액정)\s*(이\s*)?(고장|깨|박살|분실|잃어|수리|맡)/, /번호\s*(가\s*)?(바뀌|바꿨|새로)/, /(새|임시|다른)\s*번호/, /이\s*번호로\s*(연락|저장)/]],
  ['family', '가족·지인을 자처', 10, [/엄마/, /아빠/, /아들/, /딸/, /나야/, /언니/, /오빠/, /누나/, /할머니/, /할아버지/]],
  ['no_call', '통화를 피함', 20, [/통화\s*(가\s*)?(안|못)/, /전화\s*(는\s*)?(안|못)/, /문자로\s*(만|해)/, /카톡으로\s*만/]],
  ['secrecy', '비밀 유지 요구', 20, [/아무(한테|에게)도/, /비밀로/, /말하지\s*마/, /알리지\s*마/]],
  ['personal_info', '개인정보·인증 요구', 30, [/신분증/, /주민(등록)?\s*번호/, /비밀\s*번호/, /OTP/i, /인증\s*번호/, /카드\s*(번호|사진)/, /보안\s*카드/]],
  ['app_install', '앱 설치·링크 접속 유도', 30, [/앱\s*(을\s*)?(설치|깔)/, /어플/, /원격/, /팀뷰어/, /\.apk/i, /설치\s*(해|하)/, /링크\s*(를\s*)?(눌|클릭|접속)/]],
  ['institution', '기관·회사 사칭 가능성', 20, [/검찰/, /경찰/, /수사관/, /금융\s*감독원/, /금감원/, /국세청/, /법원/, /우체국/, /택배/, /건강\s*보험/, /과태료/, /카드사/, /은행\s*(상담|직원)/]],
  ['loan', '대출·지원금 미끼', 20, [/대출/, /저금리/, /정부\s*지원/, /한도/, /지원금/, /환급/]],
  ['shopping', '환불 거부·직거래 유도', 15, [/환불\s*불가/, /취소\s*불가/, /교환\s*불가/, /계좌\s*입금\s*시\s*할인/, /직거래/]]
]

const SHOP_RULES = [
  ['refund_block', '환불·취소를 막는 문구', 30, [/환불\s*(이\s*)?불가/, /취소\s*(가\s*)?불가/, /교환\s*(및\s*)?환불\s*(이\s*)?불가/, /반품\s*불가/]],
  ['bank_only', '계좌 입금 유도', 25, [/계좌\s*입금\s*시\s*(추가\s*)?할인/, /무통장\s*입금\s*만/, /현금\s*결제\s*만/, /개인\s*계좌/]],
  ['dm_order', '메신저 주문 유도', 20, [/(DM|디엠|카톡|오픈\s*채팅)\s*(으로|로)\s*(주문|문의\s*후\s*입금)/i]],
  ['too_cheap', '과도한 할인 강조', 10, [/(8|9)\d\s*%\s*(할인|세일|OFF)/i, /오늘\s*만\s*\d+\s*%/, /마감\s*임박/]]
]

const URL_RE = /(https?:\/\/[^\s<>"')]+|(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|kr|co\.kr|xyz|top|shop|site|online|info|me|ly|io|cc|link)(?:\/[^\s<>"')]*)?)/gi
const BIZ_RE = /(?<!\d)(\d{3})-?(\d{2})-?(\d{5})(?!\d)/g
const PHONE_RE = /(?<!\d)(01[016789])-?(\d{3,4})-?(\d{4})(?!\d)/g
const ACCOUNT_RE = /(?<![\d-])(\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,4})?)(?![\d-])/g
const AMOUNT_RE = /(\d[\d,]*\s*만?\s*원)/g
const URL_ONLY_RE = /^\s*(https?:\/\/)?[\w.-]+\.[a-z]{2,}(\/\S*)?\s*$/i

const TYPE_LABEL = {
  family_impersonation: '가족·지인 사칭 의심',
  institution: '기관·회사 사칭 의심',
  loan: '대출·지원금 미끼 의심',
  shopping: '쇼핑몰·판매자 확인 필요',
  link: '링크 확인 필요',
  other: '추가 확인 필요'
}

const GUIDES = {
  family_impersonation: ['송금은 잠시 멈추세요. 확인이 끝난 뒤에 보내도 늦지 않아요.', '새 번호 말고, 원래 저장된 번호로 직접 전화해 보세요.', '가족만 아는 질문을 해 보세요. (예: 지난 명절에 어디 갔지?)', '등록한 가족에게 확인 요청을 보내 보세요.'],
  institution: ['검찰·경찰·금감원은 문자로 송금이나 앱 설치를 요구하지 않아요.', '문자 속 번호 말고, 기관 대표번호를 직접 검색해서 전화하세요.', '이미 정보를 알려줬다면 금융감독원 1332, 경찰 1394로 바로 연락하세요.'],
  loan: ['정부·은행은 문자 링크로 대출이나 지원금을 신청받지 않아요.', '먼저 돈을 내라고 하면(수수료, 보증금) 사기일 가능성이 높아요.'],
  shopping: ['결제 전에 사업자 정보가 공식 기록과 맞는지 확인하세요.', '개인 계좌 입금보다 카드 결제를 쓰세요.', '피해가 생기면 소비자상담센터 1372로 연락하세요.'],
  link: ['링크를 누르기 전에 아래 링크 검사 결과를 먼저 보세요.', '이미 눌렀거나 앱을 깔았다면 KISA 118로 상담하세요.'],
  other: ['돈이나 개인정보를 요구하면 일단 멈추고 다른 경로로 확인하세요.']
}

const OFFICIAL = [
  { name: '경찰 전기통신금융사기 통합대응단', phone: '1394' },
  { name: '금융감독원 (피해 상담·지급정지)', phone: '1332' },
  { name: 'KISA 불법스팸·악성앱 상담', phone: '118' },
  { name: '소비자상담센터 (쇼핑 피해)', phone: '1372' },
  { name: '긴급 신고', phone: '112' }
]

// 시연용 데이터 (실존하지 않는 주소·번호만 사용)
const DEMO_URLS = {
  'kakao-safe-login.xyz': ['danger', '피싱 사이트로 신고된 주소예요 (시연용 데이터)'],
  'post-delivery-check.top': ['danger', '택배 사칭 피싱으로 신고된 주소예요 (시연용 데이터)'],
  'dailymood-shop.kr': ['warn', '생성된 지 9일 된 도메인이에요 (시연용 데이터)'],
  'bareunshoes.kr': ['ok', '2019년에 생성된 도메인, 악성 신고 없음 (시연용 데이터)'],
  'todayonly-deal.shop': ['warn', '생성된 지 3일 된 도메인이에요 (시연용 데이터)']
}
const DEMO_BIZ = {
  '1234567890': { nts: ['ok', '계속사업자 (정상 영업 중)'], ftc: ['warn', '통신판매업 신고 기록이 없어요'] },
  '9876543210': { nts: ['danger', '폐업자 (2026-09 폐업)'], ftc: ['ok', '신고 기록 있음'] },
  '1112233333': { nts: ['ok', '계속사업자 (정상 영업 중)'], ftc: ['ok', '신고 기록 있음'] }
}
const DEMO_PAGES = {
  'dailymood-shop.kr': '데일리무드샵 여름 끝 재고정리! 쿠션 샌들 오늘만 70% 할인 · 마감 임박 계좌 입금 시 추가 할인 · 주문 후 취소·환불 불가 상품입니다. 상호: 데일리무드 | 대표: 홍OO | 사업자등록번호: 123-45-67890 | 고객센터 010-0000-0000',
  'bareunshoes.kr': '바른신발 쿠션 샌들 정가 39,000원 · 카드 결제 가능 · 수령 후 7일 이내 교환·반품 가능 상호: 바른신발 | 대표: 김OO | 사업자등록번호: 111-22-33333 | 통신판매업신고: 제2026-경북경산-0123호 | 고객센터 053-000-0000',
  'todayonly-deal.shop': '오늘만특가 명품 스타일 가방 89% OFF 재고 소진 시 종료! 주문은 카톡으로 주문 후 입금해 주세요. 개인 계좌로 입금 확인 후 발송.'
}

const uniq = (a) => [...new Set(a)]
const all = (re, t) => [...t.matchAll(re)]

function domainOf(url) {
  try {
    const u = new URL(url.includes('://') ? url : 'http://' + url)
    return u.hostname.toLowerCase().replace(/^www\./, '')
  } catch {
    return ''
  }
}

function snippet(t, m) {
  const s = Math.max(0, m.index - 12)
  const e = Math.min(t.length, m.index + m[0].length + 12)
  return t.slice(s, e).replace(/\n/g, ' ').trim()
}

function findSignals(text, rules) {
  const out = []
  for (const [code, label, weight, pats] of rules) {
    for (const p of pats) {
      const m = text.match(p)
      if (m) {
        out.push({ code, label, weight, evidence: snippet(text, m), source: 'rule' })
        break
      }
    }
  }
  return out
}

export function extractEntities(t) {
  const biz = uniq(all(BIZ_RE, t).map((m) => `${m[1]}-${m[2]}-${m[3]}`))
  const phones = uniq(all(PHONE_RE, t).map((m) => `${m[1]}-${m[2]}-${m[3]}`))
  const accounts = uniq(all(ACCOUNT_RE, t).map((m) => m[1]).filter((v) => !biz.includes(v) && !/^\d{3}-\d{2}-\d{5}$/.test(v) && !phones.some((p) => p.replace(/-/g, '') === v.replace(/-/g, ''))))
  const urls = uniq(all(URL_RE, t).map((m) => m[1].replace(/[.,]+$/, '')).filter((u) => !u.includes('@')))
  const amounts = uniq(all(AMOUNT_RE, t).map((m) => m[1].trim()))
  return { urls, biz_numbers: biz, phones, accounts, amounts }
}

function classify(sigs, ents) {
  const c = new Set(sigs.map((s) => s.code))
  if (c.has('number_changed') || (c.has('family') && c.has('money'))) return 'family_impersonation'
  if (c.has('institution') || c.has('personal_info')) return 'institution'
  if (c.has('loan')) return 'loan'
  if (c.has('shopping') || ents.biz_numbers.length) return 'shopping'
  if (ents.urls.length || c.has('app_install')) return 'link'
  return 'other'
}

const check = (type, target, source, status, detail, demo = false, extra = {}) => ({ type, target, source, status, detail, demo, ...extra })

function checkUrl(url) {
  const d = domainOf(url)
  if (DEMO_URLS[d]) return [check('url', url, '링크 평판·도메인 생성일', DEMO_URLS[d][0], DEMO_URLS[d][1], true)]
  return [check('url', url, 'Safe Browsing·VirusTotal·도메인 생성일', 'unknown', '목업에서는 실제 조회를 하지 않아요 (서버 버전에서 조회)')]
}

function checkBiz(biz) {
  const n = biz.replace(/-/g, '')
  const d = DEMO_BIZ[n]
  if (d) {
    return [
      check('biz', biz, '국세청 사업자 상태조회', d.nts[0], d.nts[1] + ' (시연용 데이터)', true),
      check('biz', biz, '공정위 통신판매업 신고', d.ftc[0], d.ftc[1] + ' (시연용 데이터)', true)
    ]
  }
  return [check('biz', biz, '국세청·공정위', 'unknown', '목업에서는 실제 조회를 하지 않아요 (서버 버전에서 조회)')]
}

function score(sigs, checks) {
  let s = sigs.reduce((a, x) => a + x.weight, 0)
  for (const c of checks) s += c.status === 'danger' ? 35 : c.status === 'warn' ? 15 : 0
  return Math.min(100, s)
}
const level = (s) => (s >= 60 ? 'high' : s >= 30 ? 'medium' : 'low')

function finish(type, sigs, ents, checks, summary, extra = {}) {
  const sc = score(sigs, checks)
  return {
    risk_level: level(sc), score: sc, type, type_label: TYPE_LABEL[type], signals: sigs, entities: ents, checks, summary,
    guide: GUIDES[type], official: OFFICIAL, ai_used: false,
    notice: '분석 결과는 참고용이에요. 발신자의 실제 신원이나 사기 여부를 확정하지 않아요.', ...extra
  }
}

function extractSeller(text) {
  const bm = text.match(/사업자\s*(?:등록)?\s*번호\s*[:：]?\s*(\d{3})\s*-?\s*(\d{2})\s*-?\s*(\d{5})/) || text.match(/(?<!\d)(\d{3})-(\d{2})-(\d{5})(?!\d)/)
  const tm = text.match(/(제\s*\d{4}\s*-\s*[가-힣A-Za-z]+\s*-\s*\d+\s*호)/)
  const nm = text.match(/(?:상호|회사명|상호명)\s*[:：]?\s*([^\s|·,]{1,30})/)
  const cm = text.match(/대표(?:자|이사)?\s*[:：]?\s*([가-힣A-Za-z*○O]{2,10})/)
  const pm = text.match(/(?<!\d)(0\d{1,2})-(\d{3,4})-(\d{4})(?!\d)/)
  const phone = pm ? pm[0] : null
  return {
    business_name: nm ? nm[1] : null,
    ceo: cm ? cm[1] : null,
    biz_number: bm ? `${bm[1]}-${bm[2]}-${bm[3]}` : null,
    telecom_number: tm ? tm[1].replace(/\s+/g, '') : null,
    phone,
    mobile_only: !!(phone && phone.startsWith('01'))
  }
}

function analyzeShop(message) {
  const ents = extractEntities(message)
  const url = ents.urls[0] || message.trim().split(/\s+/)[0]
  const d = domainOf(url)
  const text = DEMO_PAGES[d] || null
  const seller = extractSeller(text || '')
  const sigs = []
  if (text) {
    sigs.push(...findSignals(text, SHOP_RULES))
    if (!seller.biz_number) sigs.push({ code: 'no_identity', label: '판매자 신원 정보가 없음', weight: 35, evidence: '페이지에서 사업자등록번호를 찾지 못했어요', source: 'rule' })
    else if (!seller.telecom_number) sigs.push({ code: 'no_telecom', label: '통신판매업 신고번호 미표시', weight: 15, evidence: '사업자번호는 있지만 신고번호 표시가 없어요', source: 'rule' })
    if (seller.mobile_only) sigs.push({ code: 'mobile_only', label: '연락처가 휴대폰 번호뿐', weight: 10, evidence: seller.phone, source: 'rule' })
  }
  const checks = [...checkUrl(url)]
  if (seller.biz_number) checks.push(...checkBiz(seller.biz_number))
  if (!text) checks.push(check('url', url, '쇼핑몰 페이지 읽기', 'unknown', '목업에서는 시연용 쇼핑몰 3곳만 읽을 수 있어요 (서버 버전은 실제 페이지를 읽음)'))
  const labels = sigs.slice(0, 3).map((s) => s.label).join(', ') || '특별히 눈에 띄는 문구 없음'
  const who = seller.business_name || d
  return finish('shopping', sigs, { ...ents, urls: [url], biz_numbers: seller.biz_number ? [seller.biz_number] : [] }, checks,
    `이 쇼핑몰에서 사려고 하는데 괜찮을지 봐 줄래요? (${who}, ${url}) 눈에 띄는 점: ${labels}.`,
    { seller, page_read: !!text, demo_page: !!text, mode: 'shop' })
}

function analyzeMessage(message, sender) {
  const ents = extractEntities(message)
  const sigs = findSignals(message, RULES)
  const type = classify(sigs, ents)
  const checks = []
  ents.urls.slice(0, 3).forEach((u) => checks.push(...checkUrl(u)))
  ents.biz_numbers.slice(0, 2).forEach((b) => checks.push(...checkBiz(b)))
  ents.accounts.slice(0, 2).forEach((a) => checks.push(check('account', a, '경찰청 사기 의심 계좌·번호 조회', 'unknown', '공개 API가 없어 아래 링크에서 직접 조회해 주세요', false, { link: 'https://ecrm.police.go.kr' })))
  const who = sender || '누군가'
  const parts = [`${who}(이)라고 하는 사람에게서 연락이 왔어요.`]
  if (ents.amounts.length) parts.push(`요청 금액: ${ents.amounts.slice(0, 2).join(', ')}.`)
  if (sigs.length) parts.push('눈에 띄는 점: ' + sigs.slice(0, 4).map((s) => s.label).join(', ') + '.')
  parts.push(type === 'family_impersonation' ? '혹시 직접 보낸 연락이 맞는지 알려 주세요.' : '같이 확인해 줄 수 있을까요?')
  return finish(type, sigs, ents, checks, parts.join(' '), { mode: 'message' })
}

export function analyze(message, sender = '') {
  return URL_ONLY_RE.test(message) ? analyzeShop(message) : analyzeMessage(message, sender)
}

export const SAMPLES = [
  { title: '딸 사칭 메신저피싱', claimed_sender: '딸', message: '엄마 나 폰 액정 깨져서 수리 맡겼어ㅠㅠ 이 번호로 연락해. 급하게 결제할 게 있는데 지금 통화가 안 돼서 그래. 250만원만 국민 123456-01-234567로 먼저 보내줘. 오늘 안에 꼭!' },
  { title: '택배 사칭 스미싱', claimed_sender: '우체국', message: '[Web발신] 우체국택배 주소지 불명으로 반송 예정입니다. 주소 확인: http://post-delivery-check.top/kr' },
  { title: '검찰 사칭 + 앱 설치 유도', claimed_sender: '검찰 수사관', message: '서울중앙지검 수사관입니다. 고객님 명의 계좌가 범죄에 연루되어 확인이 필요합니다. 아래 보안 앱을 설치하고 아무에게도 알리지 마세요. kakao-safe-login.xyz/app' },
  { title: 'SNS 쇼핑몰 광고', claimed_sender: '쇼핑몰 광고', message: '[데일리무드샵] 쿠션 샌들 오늘만 70%! 계좌 입금 시 할인, 주문 후 취소·환불 불가. 사업자번호 123-45-67890 dailymood-shop.kr' },
  { title: '링크만 받음: 수상한 쇼핑몰', claimed_sender: '', message: 'https://dailymood-shop.kr/product/sandal' },
  { title: '링크만 받음: 판매자 정보 없음', claimed_sender: '', message: 'https://todayonly-deal.shop' },
  { title: '링크만 받음: 정상 쇼핑몰', claimed_sender: '', message: 'https://bareunshoes.kr' }
].map((s) => ({ mode: 'message', ...s }))
