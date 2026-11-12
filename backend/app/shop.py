"""쇼핑몰 링크 검사 (사기전에 기능).

인스타그램 게시물은 로그인 없이 읽을 수 없으므로, 광고를 눌렀을 때 열리는 쇼핑몰 주소를 받는다.
서버에서 그 페이지를 받아 하단(푸터)의 사업자정보와 위험 문구를 찾는다.
"""
import html
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx

from . import config

BIZ_RE = re.compile(r"사업자\s*(?:등록)?\s*번호\s*[:：]?\s*(\d{3})\s*-?\s*(\d{2})\s*-?\s*(\d{5})")
BIZ_LOOSE_RE = re.compile(r"(?<!\d)(\d{3})-(\d{2})-(\d{5})(?!\d)")
TELECOM_RE = re.compile(r"(제\s*\d{4}\s*-\s*[가-힣A-Za-z]+\s*-\s*\d+\s*호)")
TELECOM_LABEL_RE = re.compile(r"통신\s*판매\s*(?:업)?\s*신고\s*(?:번호)?\s*[:：]?\s*([^\s|·,]{3,40})")
NAME_RE = re.compile(r"(?:상호|회사명|상호명)\s*[:：]?\s*([^\s|·,]{1,30})")
CEO_RE = re.compile(r"대표(?:자|이사)?\s*[:：]?\s*([가-힣A-Za-z*○]{2,10})")
PHONE_RE = re.compile(r"(?<!\d)(0\d{1,2})-(\d{3,4})-(\d{4})(?!\d)")

# 쇼핑몰 페이지에서만 쓰는 위험 문구 (일반 문자용 규칙보다 좁게)
SHOP_RULES = [
    ("refund_block", "환불·취소를 막는 문구", 30, [r"환불\s*(이\s*)?불가", r"취소\s*(가\s*)?불가", r"교환\s*(및\s*)?환불\s*(이\s*)?불가", r"반품\s*불가"]),
    ("bank_only", "계좌 입금 유도", 25, [r"계좌\s*입금\s*시\s*(추가\s*)?할인", r"무통장\s*입금\s*만", r"현금\s*결제\s*만", r"개인\s*계좌"]),
    ("dm_order", "메신저 주문 유도", 20, [r"(DM|디엠|카톡|오픈\s*채팅)\s*(으로|로)\s*(주문|문의\s*후\s*입금)"]),
    ("too_cheap", "과도한 할인 강조", 10, [r"(8|9)\d\s*%\s*(할인|세일|OFF)", r"오늘\s*만\s*\d+\s*%", r"마감\s*임박"]),
]


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(raw)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


def _is_blocked_host(host: str) -> bool:
    """서버가 내부망 주소를 대신 열어 주지 않도록 막는다. 시연 모드에서는 이 서버(localhost)만 허용."""
    if config.DEMO_MODE and host in ("localhost", "127.0.0.1"):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # 주소를 못 찾으면 요청 단계에서 실패로 처리
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


async def fetch_page(url: str) -> tuple[str | None, str]:
    """(본문 텍스트, 오류 메시지). 실패하면 텍스트가 None."""
    u = url if "://" in url else "https://" + url
    host = urlparse(u).hostname or ""
    if not host:
        return None, "주소를 읽지 못했어요"
    if _is_blocked_host(host):
        return None, "내부망 주소는 열 수 없어요"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14) CallGuard/0.1"}) as client:
            r = await client.get(u)
        if r.status_code >= 400:
            return None, f"페이지가 열리지 않아요 (HTTP {r.status_code})"
        return html_to_text(r.text[:800_000]), ""
    except Exception as e:  # noqa: BLE001
        return None, f"페이지를 불러오지 못했어요 ({type(e).__name__})"


def extract_seller(text: str) -> dict:
    biz = None
    m = BIZ_RE.search(text) or BIZ_LOOSE_RE.search(text)
    if m:
        biz = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    telecom = None
    m = TELECOM_RE.search(text)
    if m:
        telecom = re.sub(r"\s+", "", m.group(1))
    else:
        m = TELECOM_LABEL_RE.search(text)
        if m and re.search(r"\d", m.group(1)):
            telecom = m.group(1)
    name = (NAME_RE.search(text) or [None, None])[1]
    ceo = (CEO_RE.search(text) or [None, None])[1]
    phone = PHONE_RE.search(text)
    phone = phone.group(0) if phone else None
    return {
        "business_name": name,
        "ceo": ceo,
        "biz_number": biz,
        "telecom_number": telecom,
        "phone": phone,
        "mobile_only": bool(phone and phone.startswith("01")),
    }


def shop_signals(text: str, seller: dict) -> list[dict]:
    found = []
    for code, label, weight, pats in SHOP_RULES:
        for p in pats:
            m = re.search(p, text, re.I)
            if m:
                s, e = max(0, m.start() - 12), min(len(text), m.end() + 12)
                found.append({"code": code, "label": label, "weight": weight,
                              "evidence": text[s:e].replace("\n", " ").strip(), "source": "rule"})
                break
    if not seller["biz_number"]:
        found.append({"code": "no_identity", "label": "판매자 신원 정보가 없음", "weight": 35,
                      "evidence": "페이지에서 사업자등록번호를 찾지 못했어요", "source": "rule"})
    elif not seller["telecom_number"]:
        found.append({"code": "no_telecom", "label": "통신판매업 신고번호 미표시", "weight": 15,
                      "evidence": "사업자번호는 있지만 신고번호 표시가 없어요", "source": "rule"})
    if seller["mobile_only"]:
        found.append({"code": "mobile_only", "label": "연락처가 휴대폰 번호뿐", "weight": 10,
                      "evidence": seller["phone"], "source": "rule"})
    return found


# ---------- 시연용 가짜 쇼핑몰 페이지 (실존 업체 아님) ----------

DEMO_PAGES = {
    "dailymood": """<html><head><title>데일리무드샵</title></head><body>
<h1>데일리무드샵</h1><p>여름 끝 재고정리! 쿠션 샌들 오늘만 70% 할인 · 마감 임박</p>
<p>계좌 입금 시 추가 할인 · 주문 후 취소·환불 불가 상품입니다.</p>
<footer>상호: 데일리무드 | 대표: 홍OO | 사업자등록번호: 123-45-67890 | 고객센터 010-0000-0000</footer>
</body></html>""",
    "goodshop": """<html><head><title>바른신발</title></head><body>
<h1>바른신발</h1><p>쿠션 샌들 정가 39,000원 · 카드 결제 가능 · 수령 후 7일 이내 교환·반품 가능</p>
<footer>상호: 바른신발 | 대표: 김OO | 사업자등록번호: 111-22-33333 | 통신판매업신고: 제2026-경북경산-0123호 | 고객센터 053-000-0000</footer>
</body></html>""",
    "nosellerinfo": """<html><head><title>오늘만특가</title></head><body>
<h1>명품 스타일 가방 89% OFF</h1><p>재고 소진 시 종료! 주문은 카톡으로 주문 후 입금해 주세요. 개인 계좌로 입금 확인 후 발송.</p>
</body></html>""",
}
