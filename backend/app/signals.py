"""문자·메신저 내용에서 위험 신호와 확인할 대상(링크, 사업자번호, 계좌, 전화번호)을 뽑는다.

규칙 기반이라 키 없이도 항상 동작한다. LLM이 설정돼 있으면 llm.py가 결과를 보강한다.
"""
import re

# (코드, 화면에 보일 이름, 가중치, 정규식들)
RULES = [
    ("money", "송금·입금 요구", 30, [
        r"송금", r"이체", r"입금", r"보내\s*(줘|주|줄|달)", r"계좌", r"돈\s*(좀|이|을)", r"\d+\s*만\s*원", r"결제\s*(해|좀)",
        r"상품권", r"기프트\s*카드",
    ]),
    ("urgency", "급하게 재촉", 15, [
        r"급(해|하|히)", r"빨리", r"당장", r"오늘\s*(안|까지)", r"지금\s*바로", r"긴급", r"시간\s*(이\s*)?없", r"서둘",
    ]),
    ("number_changed", "번호 변경·폰 고장 주장", 30, [
        r"(폰|핸드폰|휴대폰|액정)\s*(이\s*)?(고장|깨|박살|분실|잃어|수리|맡)", r"번호\s*(가\s*)?(바뀌|바꿨|새로)", r"(새|임시|다른)\s*번호",
        r"이\s*번호로\s*(연락|저장)",
    ]),
    ("family", "가족·지인을 자처", 10, [
        r"엄마", r"아빠", r"아들", r"딸", r"나야", r"언니", r"오빠", r"누나", r"형", r"할머니", r"할아버지",
    ]),
    ("no_call", "통화를 피함", 20, [
        r"통화\s*(가\s*)?(안|못)", r"전화\s*(는\s*)?(안|못)", r"문자로\s*(만|해)", r"카톡으로\s*만",
    ]),
    ("secrecy", "비밀 유지 요구", 20, [
        r"아무(한테|에게)도", r"비밀로", r"말하지\s*마", r"알리지\s*마",
    ]),
    ("personal_info", "개인정보·인증 요구", 30, [
        r"신분증", r"주민(등록)?\s*번호", r"비밀\s*번호", r"OTP", r"인증\s*번호", r"카드\s*(번호|사진)", r"보안\s*카드",
    ]),
    ("app_install", "앱 설치·링크 접속 유도", 30, [
        r"앱\s*(을\s*)?(설치|깔)", r"어플", r"원격", r"팀뷰어", r"\.apk", r"설치\s*(해|하)", r"링크\s*(를\s*)?(눌|클릭|접속)",
    ]),
    ("institution", "기관·회사 사칭 가능성", 20, [
        r"검찰", r"경찰", r"수사관", r"금융\s*감독원", r"금감원", r"국세청", r"법원", r"우체국", r"택배", r"건강\s*보험",
        r"과태료", r"카드사", r"은행\s*(상담|직원)",
    ]),
    ("loan", "대출·지원금 미끼", 20, [
        r"대출", r"저금리", r"정부\s*지원", r"한도", r"지원금", r"환급",
    ]),
    ("shopping", "환불 거부·직거래 유도", 15, [
        r"환불\s*불가", r"취소\s*불가", r"교환\s*불가", r"계좌\s*입금\s*시\s*할인", r"직거래",
    ]),
]

URL_RE = re.compile(r"(https?://[^\s<>\"')]+|(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|kr|co\.kr|xyz|top|shop|site|online|info|me|ly|io|cc|link)(?:/[^\s<>\"')]*)?)", re.I)
BIZ_RE = re.compile(r"(?<!\d)(\d{3})-?(\d{2})-?(\d{5})(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(01[016789])-?(\d{3,4})-?(\d{4})(?!\d)")
ACCOUNT_RE = re.compile(r"(?<![\d-])(\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,4})?)(?![\d-])")
AMOUNT_RE = re.compile(r"(\d[\d,]*\s*만?\s*원)")
BANK_RE = re.compile(r"(국민|신한|우리|하나|농협|기업|카카오\s*뱅크|토스\s*뱅크|케이\s*뱅크|새마을|우체국|수협|SC제일|씨티|부산|대구|경남|광주|전북|제주)\s*(은행)?")


def extract_entities(text: str) -> dict:
    t = text or ""
    biz = []
    for m in BIZ_RE.finditer(t):
        biz.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    phones = [f"{m.group(1)}-{m.group(2)}-{m.group(3)}" for m in PHONE_RE.finditer(t)]
    accounts = []
    for m in ACCOUNT_RE.finditer(t):
        val = m.group(1)
        digits = val.replace("-", "")
        if val in biz or any(digits == p.replace("-", "") for p in phones):
            continue
        if re.fullmatch(r"\d{3}-\d{2}-\d{5}", val):
            continue
        accounts.append(val)
    urls = []
    for m in URL_RE.finditer(t):
        u = m.group(1).rstrip(".,")
        if "@" in u:
            continue
        urls.append(u)
    return {
        "urls": list(dict.fromkeys(urls)),
        "biz_numbers": list(dict.fromkeys(biz)),
        "phones": list(dict.fromkeys(phones)),
        "accounts": list(dict.fromkeys(accounts)),
        "banks": list(dict.fromkeys(m.group(0).strip() for m in BANK_RE.finditer(t))),
        "amounts": list(dict.fromkeys(a.strip() for a in AMOUNT_RE.findall(t))),
    }


def find_signals(text: str) -> list[dict]:
    t = text or ""
    found = []
    for code, label, weight, patterns in RULES:
        for p in patterns:
            m = re.search(p, t, re.I)
            if m:
                s, e = max(0, m.start() - 12), min(len(t), m.end() + 12)
                found.append({
                    "code": code,
                    "label": label,
                    "weight": weight,
                    "evidence": t[s:e].replace("\n", " ").strip(),
                    "source": "rule",
                })
                break
    return found


def classify(signals: list[dict], entities: dict) -> str:
    codes = {s["code"] for s in signals}
    if "number_changed" in codes or ("family" in codes and "money" in codes):
        return "family_impersonation"
    if "institution" in codes or "personal_info" in codes:
        return "institution"
    if "loan" in codes:
        return "loan"
    if "shopping" in codes or entities.get("biz_numbers"):
        return "shopping"
    if entities.get("urls") or "app_install" in codes:
        return "link"
    return "other"


TYPE_LABEL = {
    "family_impersonation": "가족·지인 사칭 의심",
    "institution": "기관·회사 사칭 의심",
    "loan": "대출·지원금 미끼 의심",
    "shopping": "쇼핑몰·판매자 확인 필요",
    "link": "링크 확인 필요",
    "other": "추가 확인 필요",
    "ingredients": "해외직구 성분 확인",
}

GUIDES = {
    "family_impersonation": [
        "송금은 잠시 멈추세요. 확인이 끝난 뒤에 보내도 늦지 않아요.",
        "새 번호 말고, 원래 저장된 번호로 직접 전화해 보세요.",
        "가족만 아는 질문을 해 보세요. (예: 지난 명절에 어디 갔지?)",
        "등록한 가족에게 확인 요청을 보내 보세요.",
    ],
    "institution": [
        "검찰·경찰·금감원은 문자로 송금이나 앱 설치를 요구하지 않아요.",
        "문자 속 번호 말고, 기관 대표번호를 직접 검색해서 전화하세요.",
        "이미 정보를 알려줬다면 금융감독원 1332, 경찰 1394로 바로 연락하세요.",
    ],
    "loan": [
        "정부·은행은 문자 링크로 대출이나 지원금을 신청받지 않아요.",
        "먼저 돈을 내라고 하면(수수료, 보증금) 사기일 가능성이 높아요.",
    ],
    "shopping": [
        "결제 전에 사업자 정보가 공식 기록과 맞는지 확인하세요.",
        "개인 계좌 입금보다 카드 결제를 쓰세요.",
        "피해가 생기면 소비자상담센터 1372로 연락하세요.",
    ],
    "link": [
        "링크를 누르기 전에 아래 링크 검사 결과를 먼저 보세요.",
        "이미 눌렀거나 앱을 깔았다면 KISA 118로 상담하세요.",
    ],
    "other": [
        "돈이나 개인정보를 요구하면 일단 멈추고 다른 경로로 확인하세요.",
    ],
    "ingredients": [
        "차단 성분이 있으면 통관 단계에서 폐기될 수 있어요. 결제 전에 다시 생각해 보세요.",
        "같은 효과를 내세우는 국내 정식 수입 제품(건강기능식품 인증 마크)을 찾아보세요.",
        "이미 받았다면 먹기 전에 약사나 의사와 상의하세요.",
    ],
}

OFFICIAL_CONTACTS = [
    {"name": "경찰 전기통신금융사기 통합대응단", "phone": "1394"},
    {"name": "금융감독원 (피해 상담·지급정지)", "phone": "1332"},
    {"name": "KISA 불법스팸·악성앱 상담", "phone": "118"},
    {"name": "소비자상담센터 (쇼핑 피해)", "phone": "1372"},
    {"name": "긴급 신고", "phone": "112"},
]


def score_of(signals: list[dict], checks: list[dict]) -> int:
    score = sum(s["weight"] for s in signals)
    for c in checks:
        if c["status"] == "danger":
            score += 35
        elif c["status"] == "warn":
            score += 15
    return min(100, score)


def level_of(score: int) -> str:
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def family_summary(text: str, signals: list[dict], entities: dict, claimed_sender: str, req_type: str) -> str:
    who = claimed_sender or "누군가"
    parts = [f"{who}(이)라고 하는 사람에게서 연락이 왔어요."]
    if entities.get("amounts"):
        parts.append(f"요청 금액: {', '.join(entities['amounts'][:2])}.")
    labels = [s["label"] for s in signals[:4]]
    if labels:
        parts.append("눈에 띄는 점: " + ", ".join(labels) + ".")
    if req_type == "family_impersonation":
        parts.append("혹시 직접 보낸 연락이 맞는지 알려 주세요.")
    else:
        parts.append("같이 확인해 줄 수 있을까요?")
    return " ".join(parts)
