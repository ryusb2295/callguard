import json
import re

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


from . import config, external, ingredients, llm, shop, signals
from .db import execute, load_case, normalize_phone, now, query

app = FastAPI(title="콜가드 API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------- 모델 ----------

class UserIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    phone: str = Field(min_length=9, max_length=20)


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    relation: str = Field(default="", max_length=20)
    phone: str = Field(min_length=9, max_length=20)


class AnalyzeIn(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    claimed_sender: str = Field(default="", max_length=30)
    mode: str = Field(default="auto", pattern="^(auto|message|shop|ingredients)$")


class CaseIn(AnalyzeIn):
    user_id: int


class SendIn(BaseModel):
    contact_id: int | None = None


class RespondIn(BaseModel):
    answer: str  # yes | no | unknown
    note: str = Field(default="", max_length=200)


# ---------- 공통 ----------

def _user_or_404(user_id: int) -> dict:
    u = query("SELECT * FROM users WHERE id=?", (user_id,), one=True)
    if not u:
        raise HTTPException(404, "사용자를 찾을 수 없어요")
    return u


DEMO_SHOP_DOMAINS = {"dailymood-shop.kr": "dailymood", "bareunshoes.kr": "goodshop", "todayonly-deal.shop": "nosellerinfo"}


def _finish(req_type: str, sigs: list, ents: dict, checks: list, summary: str, extra: dict | None = None, ai: bool = False) -> dict:
    score = signals.score_of(sigs, checks)
    out = {
        "risk_level": signals.level_of(score),
        "score": score,
        "type": req_type,
        "type_label": signals.TYPE_LABEL[req_type],
        "signals": sigs,
        "entities": ents,
        "checks": checks,
        "summary": summary,
        "guide": signals.GUIDES[req_type],
        "official": signals.OFFICIAL_CONTACTS,
        "ai_used": ai,
        "notice": "분석 결과는 참고용이에요. 발신자의 실제 신원이나 사기 여부를 확정하지 않아요.",
    }
    out.update(extra or {})
    return out


async def build_shop_analysis(message: str) -> dict:
    ents = signals.extract_entities(message)
    url = (ents["urls"] or [message.strip().split()[0]])[0]
    domain = external._domain(url)
    if config.DEMO_MODE and domain in DEMO_SHOP_DOMAINS:
        text, err, demo_page = shop.html_to_text(shop.DEMO_PAGES[DEMO_SHOP_DOMAINS[domain]]), "", True
    else:
        (text, err), demo_page = await shop.fetch_page(url), False
    seller = shop.extract_seller(text or "")
    sigs = shop.shop_signals(text, seller) if text else []
    checks = []
    async with httpx.AsyncClient(timeout=external.TIMEOUT) as client:
        checks += await external.check_url(client, url)
        if seller["biz_number"]:
            checks += await external.check_biz(client, seller["biz_number"])
    if not text:
        checks.append({"type": "url", "target": url, "source": "쇼핑몰 페이지 읽기", "status": "unknown", "detail": err, "demo": False})
    labels = ", ".join(x["label"] for x in sigs[:3]) or "특별히 눈에 띄는 문구 없음"
    who = seller["business_name"] or domain
    summary = f"이 쇼핑몰에서 사려고 하는데 괜찮을지 봐 줄래요? ({who}, {url}) 눈에 띄는 점: {labels}."
    ents["urls"], ents["biz_numbers"] = [url], [seller["biz_number"]] if seller["biz_number"] else []
    return _finish("shopping", sigs, ents, checks, summary, {"seller": seller, "page_read": bool(text), "demo_page": demo_page})


async def build_ingredient_analysis(message: str) -> dict:
    checks, items = await ingredients.check_ingredients(message)
    bad = [c["target"] for c in checks if c["status"] == "danger"]
    summary = (f"직구로 사려는 제품 성분표에 {', '.join(bad)}이(가) 있어요. 사도 될지 같이 봐 줄래요?"
               if bad else "직구로 사려는 제품 성분표를 확인했어요. 같이 한 번 봐 줄래요?")
    out = _finish("ingredients", [], {"ingredients": items}, checks, summary, {"ingredient_count": len(items)})
    # 차단 성분은 하나만 있어도 통관 폐기 위험이 커서 점수를 높게 준다
    out["score"] = min(100, 65 * len(bad)) if bad else 0
    out["risk_level"] = signals.level_of(out["score"])
    return out


URL_ONLY_RE = re.compile(r"^\s*(https?://)?[\w.-]+\.[a-z]{2,}(/\S*)?\s*$", re.I)


def resolve_mode(message: str, mode: str) -> str:
    """입력창은 하나. 링크만 들어오면 쇼핑몰·사이트 확인, 나머지는 메시지 분석."""
    if mode != "auto":
        return mode
    return "shop" if URL_ONLY_RE.match(message) else "message"


async def build_analysis(message: str, claimed_sender: str, mode: str = "auto") -> dict:
    mode = resolve_mode(message, mode)
    if mode == "shop":
        return {**await build_shop_analysis(message), "mode": mode}
    if mode == "ingredients":
        return {**await build_ingredient_analysis(message), "mode": mode}
    return {**await build_message_analysis(message, claimed_sender), "mode": mode}


async def build_message_analysis(message: str, claimed_sender: str) -> dict:
    ents = signals.extract_entities(message)
    sigs = signals.find_signals(message)
    ai = await llm.analyze(message, claimed_sender)
    if ai:
        known = {s["label"] for s in sigs}
        for s in (ai.get("signals") or [])[:3]:
            label = str(s.get("label") or "").strip()
            if label and label not in known:
                sigs.append({"code": "ai", "label": label, "weight": 10,
                             "evidence": str(s.get("evidence") or "")[:80], "source": "ai"})
    req_type = signals.classify(sigs, ents)
    if ai and ai.get("type") in signals.TYPE_LABEL:
        req_type = ai["type"]
    checks = await external.run_checks(ents)
    summary = (ai or {}).get("summary") or signals.family_summary(message, sigs, ents, claimed_sender, req_type)
    return _finish(req_type, sigs, ents, checks, summary, ai=bool(ai))


def _contacts_of(user_id: int) -> list[dict]:
    return query("SELECT * FROM contacts WHERE owner_id=? ORDER BY priority, id", (user_id,))


def _send_request(case_id: int, contact: dict) -> int:
    rid = execute(
        "INSERT INTO requests(case_id, contact_id, to_phone, status, sent_at) VALUES (?,?,?,?,?)",
        (case_id, contact["id"], normalize_phone(contact["phone"]), "sent", now()))
    execute("UPDATE cases SET status='waiting', updated_at=? WHERE id=?", (now(), case_id))
    return rid


def _next_contact(case: dict) -> dict | None:
    asked = {r["contact_id"] for r in query("SELECT contact_id FROM requests WHERE case_id=?", (case["id"],))}
    for c in _contacts_of(case["owner_id"]):
        if c["id"] not in asked:
            return c
    return None


def _advance(case: dict) -> None:
    """응답이 없거나 '모르겠어요'면 다음 연락처로 넘긴다. 다 돌았으면 '확인 안 됨'."""
    nxt = _next_contact(case)
    if nxt:
        _send_request(case["id"], nxt)
    else:
        execute("UPDATE cases SET status='unverified', updated_at=? WHERE id=?", (now(), case["id"]))


def process_case(case_id: int) -> None:
    case = load_case(case_id)
    if not case or case["status"] != "waiting":
        return
    active = query("SELECT * FROM requests WHERE case_id=? AND status='sent' ORDER BY id DESC", (case_id,), one=True)
    if active and now() - active["sent_at"] > config.ESCALATE_SECONDS:
        execute("UPDATE requests SET status='expired' WHERE id=?", (active["id"],))
        _advance(case)


def case_view(case_id: int) -> dict:
    process_case(case_id)
    case = load_case(case_id)
    if not case:
        raise HTTPException(404, "사례를 찾을 수 없어요")
    reqs = query(
        """SELECT r.*, c.name AS contact_name, c.relation AS contact_relation
           FROM requests r JOIN contacts c ON c.id=r.contact_id WHERE r.case_id=? ORDER BY r.id""",
        (case_id,))
    active = next((r for r in reqs if r["status"] == "sent"), None)
    case["requests"] = reqs
    case["seconds_left"] = max(0, int(config.ESCALATE_SECONDS - (now() - active["sent_at"]))) if active else None
    case["escalate_seconds"] = config.ESCALATE_SECONDS
    case["owner"] = _user_or_404(case["owner_id"])
    return case


# ---------- 사용자·연락처 ----------

@app.post("/api/users")
def login(body: UserIn):
    phone = normalize_phone(body.phone)
    u = query("SELECT * FROM users WHERE phone=?", (phone,), one=True)
    if u:
        if u["name"] != body.name.strip():
            execute("UPDATE users SET name=? WHERE id=?", (body.name.strip(), u["id"]))
            u["name"] = body.name.strip()
        return u
    uid = execute("INSERT INTO users(name, phone, created_at) VALUES (?,?,?)", (body.name.strip(), phone, now()))
    return query("SELECT * FROM users WHERE id=?", (uid,), one=True)


@app.get("/api/users/{user_id}")
def get_user(user_id: int):
    return _user_or_404(user_id)


@app.get("/api/users/{user_id}/contacts")
def list_contacts(user_id: int):
    _user_or_404(user_id)
    out = []
    for c in _contacts_of(user_id):
        joined = query("SELECT id FROM users WHERE phone=?", (normalize_phone(c["phone"]),), one=True)
        out.append({**c, "joined": bool(joined)})
    return out


@app.post("/api/users/{user_id}/contacts")
def add_contact(user_id: int, body: ContactIn):
    _user_or_404(user_id)
    phone = normalize_phone(body.phone)
    if query("SELECT id FROM contacts WHERE owner_id=? AND phone=?", (user_id, phone), one=True):
        raise HTTPException(409, "이미 등록된 번호예요")
    prio = len(_contacts_of(user_id))
    cid = execute("INSERT INTO contacts(owner_id, name, relation, phone, priority, created_at) VALUES (?,?,?,?,?,?)",
                  (user_id, body.name.strip(), body.relation.strip(), phone, prio, now()))
    return query("SELECT * FROM contacts WHERE id=?", (cid,), one=True)


@app.delete("/api/users/{user_id}/contacts/{contact_id}")
def delete_contact(user_id: int, contact_id: int):
    execute("DELETE FROM contacts WHERE id=? AND owner_id=?", (contact_id, user_id))
    return {"ok": True}


# ---------- 분석·사례 ----------

@app.post("/api/analyze")
async def analyze(body: AnalyzeIn):
    return await build_analysis(body.message, body.claimed_sender, body.mode)


@app.post("/api/cases")
async def create_case(body: CaseIn):
    _user_or_404(body.user_id)
    analysis = await build_analysis(body.message, body.claimed_sender, body.mode)
    cid = execute(
        "INSERT INTO cases(owner_id, message, claimed_sender, analysis, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (body.user_id, body.message, body.claimed_sender, json.dumps(analysis, ensure_ascii=False), "draft", now(), now()))
    return case_view(cid)


@app.post("/api/cases/{case_id}/send")
def send_case(case_id: int, body: SendIn):
    case = load_case(case_id)
    if not case:
        raise HTTPException(404, "사례를 찾을 수 없어요")
    contacts = _contacts_of(case["owner_id"])
    if not contacts:
        raise HTTPException(400, "먼저 확인해 줄 가족·친구를 등록해 주세요")
    if query("SELECT id FROM requests WHERE case_id=? AND status='sent'", (case_id,), one=True):
        return case_view(case_id)
    target = next((c for c in contacts if c["id"] == body.contact_id), None) or _next_contact(case)
    if not target:
        raise HTTPException(400, "더 보낼 연락처가 없어요")
    _send_request(case_id, target)
    return case_view(case_id)


@app.get("/api/cases/{case_id}")
def get_case(case_id: int):
    return case_view(case_id)


@app.get("/api/users/{user_id}/cases")
def list_cases(user_id: int):
    rows = query("SELECT id FROM cases WHERE owner_id=? ORDER BY id DESC LIMIT 20", (user_id,))
    out = []
    for r in rows:
        c = case_view(r["id"])
        out.append({k: c[k] for k in ("id", "message", "claimed_sender", "status", "created_at")} |
                   {"risk_level": c["analysis"]["risk_level"], "type_label": c["analysis"]["type_label"]})
    return out


# ---------- 받은 확인 요청 ----------

@app.get("/api/users/{user_id}/inbox")
def inbox(user_id: int):
    u = _user_or_404(user_id)
    for c in query("SELECT DISTINCT case_id FROM requests WHERE to_phone=? AND status='sent'", (u["phone"],)):
        process_case(c["case_id"])
    rows = query("SELECT * FROM requests WHERE to_phone=? ORDER BY id DESC LIMIT 20", (u["phone"],))
    out = []
    for r in rows:
        case = load_case(r["case_id"])
        owner = _user_or_404(case["owner_id"])
        out.append({
            **r,
            "from_name": owner["name"],
            "message": case["message"],
            "claimed_sender": case["claimed_sender"],
            "summary": case["analysis"]["summary"],
            "signals": case["analysis"]["signals"],
            "risk_level": case["analysis"]["risk_level"],
            "type_label": case["analysis"]["type_label"],
            "mode": case["analysis"].get("mode", "message"),
        })
    return out


@app.post("/api/requests/{req_id}/respond")
def respond(req_id: int, body: RespondIn):
    if body.answer not in ("yes", "no", "unknown"):
        raise HTTPException(400, "answer는 yes, no, unknown 중 하나예요")
    r = query("SELECT * FROM requests WHERE id=?", (req_id,), one=True)
    if not r:
        raise HTTPException(404, "요청을 찾을 수 없어요")
    if r["status"] != "sent":
        raise HTTPException(409, "이미 처리된 요청이에요")
    execute("UPDATE requests SET status=?, note=?, responded_at=? WHERE id=?", (body.answer, body.note, now(), req_id))
    case = load_case(r["case_id"])
    if body.answer == "yes":
        execute("UPDATE cases SET status='confirmed_real', updated_at=? WHERE id=?", (now(), case["id"]))
    elif body.answer == "no":
        execute("UPDATE cases SET status='confirmed_fake', updated_at=? WHERE id=?", (now(), case["id"]))
    else:
        _advance(case)
    return {"ok": True}


# ---------- 기타 ----------

SAMPLES_SHOP = [
    {"title": "링크만 받음: 수상한 쇼핑몰", "mode": "shop", "claimed_sender": "", "message": "https://dailymood-shop.kr/product/sandal"},
    {"title": "링크만 받음: 판매자 정보 없음", "mode": "shop", "claimed_sender": "", "message": "https://todayonly-deal.shop"},
    {"title": "링크만 받음: 정상 쇼핑몰", "mode": "shop", "claimed_sender": "", "message": "https://bareunshoes.kr"},
]
SAMPLES_INGREDIENTS = [
    {"title": "다이어트 보조제 (차단 성분)", "mode": "ingredients", "claimed_sender": "",
     "message": "Supplement Facts\nGreen Tea Extract 500mg, Caffeine Anhydrous 200mg, Yohimbine HCl 3mg, Cayenne Pepper 50mg, Black Pepper Extract 5mg"},
    {"title": "멀티비타민 (정상)", "mode": "ingredients", "claimed_sender": "",
     "message": "Vitamin C 500mg, Vitamin D3 25mcg, Zinc 10mg, Magnesium 100mg, Biotin 300mcg"},
]

SAMPLES = [
    {"title": "딸 사칭 메신저피싱", "claimed_sender": "딸",
     "message": "엄마 나 폰 액정 깨져서 수리 맡겼어ㅠㅠ 이 번호로 연락해. 급하게 결제할 게 있는데 지금 통화가 안 돼서 그래. 250만원만 국민 123456-01-234567로 먼저 보내줘. 오늘 안에 꼭!"},
    {"title": "택배 사칭 스미싱", "claimed_sender": "우체국",
     "message": "[Web발신] 우체국택배 주소지 불명으로 반송 예정입니다. 주소 확인: http://post-delivery-check.top/kr"},
    {"title": "검찰 사칭 + 앱 설치 유도", "claimed_sender": "검찰 수사관",
     "message": "서울중앙지검 수사관입니다. 고객님 명의 계좌가 범죄에 연루되어 확인이 필요합니다. 아래 보안 앱을 설치하고 아무에게도 알리지 마세요. kakao-safe-login.xyz/app"},
    {"title": "SNS 쇼핑몰 광고", "claimed_sender": "쇼핑몰 광고",
     "message": "[데일리무드샵] 쿠션 샌들 오늘만 70%! 계좌 입금 시 할인, 주문 후 취소·환불 불가. 사업자번호 123-45-67890 dailymood-shop.kr"},
]


@app.get("/api/samples")
def samples():
    # 직구 성분 검사(SAMPLES_INGREDIENTS)는 주제 집중을 위해 화면에서 뺐다. 코드는 mode="ingredients"로 남아 있음
    return [dict(x, mode=x.get("mode", "message")) for x in SAMPLES] + SAMPLES_SHOP


@app.get("/demo/shop/{name}", response_class=HTMLResponse)
def demo_shop(name: str):
    """시연용 가짜 쇼핑몰 페이지 (실존 업체 아님)."""
    page = shop.DEMO_PAGES.get(name)
    if not page:
        raise HTTPException(404, "없는 시연 페이지예요")
    return page


@app.get("/api/health")
def health():
    return {"ok": True, "apis": external.configured(), "escalate_seconds": config.ESCALATE_SECONDS}


# 빌드된 프론트엔드가 있으면 같은 서버에서 제공 (배포를 한 곳에서 끝내기 위함)
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = config.FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
