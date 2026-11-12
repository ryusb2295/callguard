# 콜가드 (Call Guard)

> 돈 보내기 전에, 한 번 더.
> 의심스러운 문자·카톡·링크를 AI와 공식 데이터가 먼저 살펴보고, 미리 등록한 가족에게 "이거 진짜 너야?"를 대신 물어보는 사기 예방 앱.

## 입력은 하나, 판단은 자동

사용자는 받은 내용을 붙여넣기만 하면 됩니다. 앱이 알아서 판단합니다.

- 문자·카톡 내용 → 위험 신호 분석 + 속에 든 링크·계좌·사업자번호를 공식 데이터와 대조
- 링크만 넣으면 → 그 사이트를 열어 하단 사업자정보를 찾고 국세청·공정위 기록, 도메인 평판·생성일과 대조

어느 경우든 결과를 등록한 가족에게 보내 마지막 확인을 받습니다.
(직구 성분 검사 코드 `app/ingredients.py`는 남아 있지만, 주제 집중을 위해 화면에서는 뺐습니다.)

## 핵심 아이디어

사기범은 "폰이 고장 나서 새 번호야"라고 말합니다. 콜가드는 그 새 번호가 아니라 **미리 등록해 둔 원래 번호**로 확인 요청을 보냅니다. 사기범은 등록된 연락처를 바꿀 수 없습니다.

1. 의심 메시지를 붙여넣거나 캡처를 올리면 (안드로이드는 공유하기로 바로 전달)
2. 위험 신호(송금 요구, 번호 변경 주장, 통화 회피, 앱 설치 유도 등)를 찾고
3. 링크·사업자번호가 있으면 공식 데이터로 대조하고
4. 등록한 가족에게 확인 요청을 보냅니다. 답이 없으면 다음 가족에게, 모두 답이 없으면 공식 기관 안내로 넘어갑니다.

분석 결과는 참고용이며 발신자의 실제 신원이나 사기 여부를 확정하지 않습니다.

## 폴더 구조

```
callguard/
├─ backend/              FastAPI
│  ├─ app/main.py        API (사용자, 연락처, 분석, 확인 요청, 응답)
│  ├─ app/signals.py     위험 신호·링크·계좌·사업자번호 추출 (규칙 기반, 키 없이 동작)
│  ├─ app/external.py    외부 API 연동 (국세청, 공정위, Safe Browsing, VirusTotal, RDAP)
│  ├─ app/llm.py         (선택) LLM 분석 보강 - Ollama 등 OpenAI 호환 엔드포인트
│  └─ .env.example       설정 예시
├─ frontend/             Vue 3 + Vite PWA
│  └─ src/views/         시작, 홈, 확인하기, 사례 상태, 가족 등록, 받은 요청
├─ start-backend.bat     윈도우에서 백엔드 실행
└─ start-frontend.bat    윈도우에서 프론트엔드 실행
```

## 실행 (윈도우)

필요: Python 3.10 이상, Node.js 18 이상

1. `start-backend.bat` 더블클릭 → http://localhost:8000/docs 에서 API 확인
2. `start-frontend.bat` 더블클릭 → http://localhost:5173 접속

VS Code에서는 터미널 두 개를 열고 각각 실행해도 됩니다.

```bash
# 터미널 1
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# 터미널 2
cd frontend
npm install
npm run dev
```

## 시연 순서 (브라우저 두 개)

1. 크롬 일반 창: **엄마**로 가입 (예: 010-1111-2222) → 가족 등록에서 딸 `010-3333-4444`, 아들 `010-5555-6666` 등록
2. 크롬 시크릿 창: **딸**로 가입 (`010-3333-4444`)
3. 엄마 창: 확인하기 → 시연용 예시 "딸 사칭 메신저피싱" → 분석 → 딸에게 확인 요청 보내기
4. 딸 창: 받은 요청에 빨간 배지 → "아니요, 제가 보낸 거 아니에요"
5. 엄마 창: 화면이 바로 "사칭일 가능성이 높아요"로 바뀌고 공식 기관 번호가 뜸

무응답 시나리오: 딸이 답하지 않으면 `ESCALATE_SECONDS`(기본 60초) 뒤 아들에게 넘어가고, 모두 답이 없으면 "확인되지 않음" + 기관 안내로 바뀝니다.

## 외부 API 설정 (`backend/.env`)

| 항목 | 용도 | 받는 곳 |
|---|---|---|
| `NTS_SERVICE_KEY` | 사업자 휴·폐업 조회 | data.go.kr "국세청_사업자등록정보 진위확인 및 상태조회 서비스" (자동승인) |
| `FTC_CSV_PATH` | 통신판매업 신고 여부 | data.go.kr "공정거래위원회_통신판매사업자정보파일" CSV를 `backend/data/telecom_sellers.csv`로 저장 |
| `GOOGLE_SAFE_BROWSING_KEY` | 악성 링크 | Google Cloud 콘솔 → Safe Browsing API |
| `VIRUSTOTAL_API_KEY` | 링크 평판 | virustotal.com 무료 계정 |
| `FOODSAFETY_API_KEY` | (화면에서 뺀 기능) 직구 차단 성분 | foodsafetykorea.go.kr Open API 인증키 |
| (키 없음) | 도메인 생성일 | rdap.org 공개 조회 |
| `LLM_BASE_URL` 등 | AI 분석 보강 | 무료로 쓰려면 Ollama (`http://localhost:11434/v1`) |

키를 비워 두면 그 항목은 "확인 불가"로 정직하게 표시됩니다.
`DEMO_MODE=true`이면 시연용 가짜 주소·번호에만 고정 결과를 돌려주고 화면에 "시연용"이라고 표시합니다.
- 문자 속 링크: `kakao-safe-login.xyz`, `post-delivery-check.top`
- 쇼핑몰: `dailymood-shop.kr`(위험 신호), `todayonly-deal.shop`(판매자 정보 없음), `bareunshoes.kr`(정상). 실제 페이지 모양은 `http://localhost:8000/demo/shop/dailymood` 등에서 볼 수 있습니다.
- 직구 성분: 식품안전나라 키가 없으면 차단 목록에서 자주 보이는 성분 몇 개(요힘빈, 시부트라민 등)로 만든 시연용 목록을 씁니다. 실제 쇼핑몰이나 실존 번호를 "위험"으로 보여주는 시연은 피하세요.

## 목업 다시 빌드하기

```bash
cd frontend
npm run build:mock   # 결과가 ../docs 폴더에 생김 → GitHub Pages가 docs 폴더를 서비스
npm run dev:mock     # 서버 없이 목업으로 개발 화면 열기
```

목업 코드는 `frontend/src/mock/` (분석 규칙 `engine.js`, 저장소 역할 `api.js`)에 있습니다.

## 휴대폰에서 앱처럼 쓰기 (PWA)

PWA 설치와 안드로이드 공유하기는 **HTTPS**에서만 동작합니다. 노트북 localhost로는 폰에 설치되지 않습니다.

- 가장 간단한 방법: `cd frontend && npm run build` 후 백엔드만 실행하면 `backend`가 `frontend/dist`를 같이 제공합니다. 이 서버 하나를 Render·Railway 같은 곳에 배포하거나, 급하면 `ngrok http 8000`으로 HTTPS 주소를 만드세요.
- 안드로이드 크롬에서 접속 → 메뉴 → "앱 설치" → 문자·카톡의 공유하기 목록에 콜가드가 나타납니다.
- 아이폰 사파리는 공유 대상 등록을 지원하지 않아 내용 붙여넣기로 씁니다.
