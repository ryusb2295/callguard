"""외부 API로 링크·사업자를 확인한다.

각 함수는 같은 모양의 dict를 돌려준다:
  {type, target, source, status: danger|warn|ok|unknown, detail, demo}
키가 없거나 호출이 실패하면 status="unknown"으로 정직하게 표시한다.
DEMO_MODE에서는 시연용 샘플 대상(DEMO_*)에 한해 고정 결과를 돌려주고 demo=True로 표시한다.
"""
import base64
import csv
import datetime as dt
from urllib.parse import urlparse

import httpx

from . import config

TIMEOUT = httpx.Timeout(6.0)

# 시연용 고정 데이터 (실제 존재하지 않는 도메인·번호만 사용)
DEMO_URLS = {
    "kakao-safe-login.xyz": ("danger", "피싱 사이트로 신고된 주소예요 (시연용 데이터)"),
    "post-delivery-check.top": ("danger", "택배 사칭 피싱으로 신고된 주소예요 (시연용 데이터)"),
    "dailymood-shop.kr": ("warn", "생성된 지 9일 된 도메인이에요 (시연용 데이터)"),
    "bareunshoes.kr": ("ok", "2019년에 생성된 도메인, 악성 신고 없음 (시연용 데이터)"),
    "todayonly-deal.shop": ("warn", "생성된 지 3일 된 도메인이에요 (시연용 데이터)"),
}
DEMO_BIZ = {
    "1234567890": {"nts": ("ok", "계속사업자 (정상 영업 중)"), "ftc": ("warn", "통신판매업 신고 기록이 없어요")},
    "9876543210": {"nts": ("danger", "폐업자 (2026-09 폐업)"), "ftc": ("ok", "신고 기록 있음")},
    "1112233333": {"nts": ("ok", "계속사업자 (정상 영업 중)"), "ftc": ("ok", "신고 기록 있음")},
}


def _check(type_, target, source, status, detail, demo=False):
    return {"type": type_, "target": target, "source": source, "status": status, "detail": detail, "demo": demo}


def _domain(url: str) -> str:
    u = url if "://" in url else "http://" + url
    host = (urlparse(u).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _full_url(url: str) -> str:
    return url if "://" in url else "http://" + url


# ---------- 링크 ----------

async def safe_browsing(client: httpx.AsyncClient, url: str) -> dict:
    src = "Google Safe Browsing"
    if not config.GOOGLE_SAFE_BROWSING_KEY:
        return _check("url", url, src, "unknown", "API 키가 설정되지 않았어요")
    body = {
        "client": {"clientId": "callguard", "clientVersion": "0.1"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": _full_url(url)}],
        },
    }
    try:
        r = await client.post(
            "https://safebrowsing.googleapis.com/v4/threatMatches:find",
            params={"key": config.GOOGLE_SAFE_BROWSING_KEY}, json=body)
        r.raise_for_status()
        matches = r.json().get("matches") or []
        if matches:
            kinds = ", ".join(sorted({m.get("threatType", "") for m in matches}))
            return _check("url", url, src, "danger", f"위험 사이트 목록에 있어요 ({kinds})")
        return _check("url", url, src, "ok", "위험 사이트 목록에 없어요")
    except Exception as e:  # noqa: BLE001
        return _check("url", url, src, "unknown", f"조회 실패: {type(e).__name__}")


async def virustotal(client: httpx.AsyncClient, url: str) -> dict:
    src = "VirusTotal"
    if not config.VIRUSTOTAL_API_KEY:
        return _check("url", url, src, "unknown", "API 키가 설정되지 않았어요")
    uid = base64.urlsafe_b64encode(_full_url(url).encode()).decode().strip("=")
    try:
        r = await client.get(f"https://www.virustotal.com/api/v3/urls/{uid}",
                             headers={"x-apikey": config.VIRUSTOTAL_API_KEY})
        if r.status_code == 404:
            return _check("url", url, src, "unknown", "검사 기록이 없는 새 주소예요")
        r.raise_for_status()
        stats = r.json()["data"]["attributes"]["last_analysis_stats"]
        bad, sus = stats.get("malicious", 0), stats.get("suspicious", 0)
        if bad >= 2:
            return _check("url", url, src, "danger", f"보안 엔진 {bad}곳이 악성으로 판정했어요")
        if bad or sus:
            return _check("url", url, src, "warn", f"악성 {bad}곳, 의심 {sus}곳")
        return _check("url", url, src, "ok", "악성 판정 없음")
    except Exception as e:  # noqa: BLE001
        return _check("url", url, src, "unknown", f"조회 실패: {type(e).__name__}")


async def domain_age(client: httpx.AsyncClient, url: str) -> dict:
    """RDAP(공개 도메인 등록 정보)로 도메인이 만들어진 날짜를 본다. 키가 필요 없다."""
    src = "RDAP 도메인 등록정보"
    domain = _domain(url)
    if not domain:
        return _check("url", url, src, "unknown", "도메인을 읽지 못했어요")
    try:
        r = await client.get(f"https://rdap.org/domain/{domain}", follow_redirects=True)
        if r.status_code == 404:
            return _check("url", url, src, "unknown", "등록 정보를 찾지 못했어요")
        r.raise_for_status()
        events = r.json().get("events") or []
        reg = next((e.get("eventDate") for e in events if e.get("eventAction") == "registration"), None)
        if not reg:
            return _check("url", url, src, "unknown", "생성일 정보가 없어요")
        created = dt.datetime.fromisoformat(reg.replace("Z", "+00:00"))
        days = (dt.datetime.now(dt.timezone.utc) - created).days
        if days < 30:
            return _check("url", url, src, "warn", f"만든 지 {days}일 된 도메인이에요")
        return _check("url", url, src, "ok", f"{created.date()} 생성 ({days // 365}년 이상 운영)" if days >= 365 else f"{created.date()} 생성")
    except Exception as e:  # noqa: BLE001
        return _check("url", url, src, "unknown", f"조회 실패: {type(e).__name__}")


async def check_url(client: httpx.AsyncClient, url: str) -> list[dict]:
    domain = _domain(url)
    if config.DEMO_MODE and domain in DEMO_URLS:
        status, detail = DEMO_URLS[domain]
        return [_check("url", url, "링크 평판·도메인 생성일", status, detail, demo=True)]
    return [await safe_browsing(client, url), await virustotal(client, url), await domain_age(client, url)]


# ---------- 사업자 ----------

async def nts_status(client: httpx.AsyncClient, biz: str) -> dict:
    src = "국세청 사업자 상태조회"
    b_no = biz.replace("-", "")
    if config.DEMO_MODE and b_no in DEMO_BIZ:
        status, detail = DEMO_BIZ[b_no]["nts"]
        return _check("biz", biz, src, status, detail + " (시연용 데이터)", demo=True)
    if not config.NTS_SERVICE_KEY:
        return _check("biz", biz, src, "unknown", "API 키가 설정되지 않았어요")
    try:
        r = await client.post(
            "https://api.odcloud.kr/api/nts-businessman/v1/status",
            params={"serviceKey": config.NTS_SERVICE_KEY}, json={"b_no": [b_no]})
        r.raise_for_status()
        d = (r.json().get("data") or [{}])[0]
        stt = d.get("b_stt") or ""
        if not stt:
            return _check("biz", biz, src, "danger", d.get("tax_type") or "국세청에 등록되지 않은 번호예요")
        if "폐업" in stt:
            day = d.get("end_dt") or ""
            return _check("biz", biz, src, "danger", f"{stt} {day}".strip())
        if "휴업" in stt:
            return _check("biz", biz, src, "warn", stt)
        return _check("biz", biz, src, "ok", f"{stt} (정상 영업 중)")
    except Exception as e:  # noqa: BLE001
        return _check("biz", biz, src, "unknown", f"조회 실패: {type(e).__name__}")


_ftc_cache: set[str] | None = None


def _load_ftc() -> set[str] | None:
    """data.go.kr '공정거래위원회_통신판매사업자정보파일' CSV에서 사업자등록번호만 읽어 둔다."""
    global _ftc_cache
    if _ftc_cache is not None:
        return _ftc_cache
    path = config.FTC_CSV_PATH
    if not path.exists():
        return None
    nums: set[str] = set()
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                col = next((c for c in (reader.fieldnames or []) if "사업자등록번호" in c), None)
                if not col:
                    return None
                for row in reader:
                    v = "".join(ch for ch in (row.get(col) or "") if ch.isdigit())
                    if v:
                        nums.add(v)
            _ftc_cache = nums
            return nums
        except UnicodeDecodeError:
            continue
    return None


def ftc_registered(biz: str) -> dict:
    src = "공정위 통신판매업 신고"
    b_no = biz.replace("-", "")
    if config.DEMO_MODE and b_no in DEMO_BIZ:
        status, detail = DEMO_BIZ[b_no]["ftc"]
        return _check("biz", biz, src, status, detail + " (시연용 데이터)", demo=True)
    nums = _load_ftc()
    if nums is None:
        return _check("biz", biz, src, "unknown", "통신판매사업자 파일이 아직 없어요 (README 참고)")
    if b_no in nums:
        return _check("biz", biz, src, "ok", "신고 기록 있음")
    return _check("biz", biz, src, "warn", "신고 기록이 없어요 (소규모 판매자는 면제일 수 있음)")


async def check_biz(client: httpx.AsyncClient, biz: str) -> list[dict]:
    return [await nts_status(client, biz), ftc_registered(biz)]


# ---------- 계좌·전화번호 ----------

def police_lookup(target: str, kind: str) -> dict:
    """경찰청 사기 의심 계좌·번호 조회는 공개 API가 없어 바로 가는 링크만 준다."""
    c = _check(kind, target, "경찰청 사기 의심 계좌·번호 조회", "unknown",
               "공개 API가 없어 아래 링크에서 직접 조회해 주세요")
    c["link"] = "https://ecrm.police.go.kr"
    return c


async def run_checks(entities: dict) -> list[dict]:
    checks: list[dict] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for u in entities.get("urls", [])[:3]:
            checks += await check_url(client, u)
        for b in entities.get("biz_numbers", [])[:2]:
            checks += await check_biz(client, b)
    for a in entities.get("accounts", [])[:2]:
        checks.append(police_lookup(a, "account"))
    return checks


def configured() -> dict:
    return {
        "demo_mode": config.DEMO_MODE,
        "nts": bool(config.NTS_SERVICE_KEY),
        "safe_browsing": bool(config.GOOGLE_SAFE_BROWSING_KEY),
        "virustotal": bool(config.VIRUSTOTAL_API_KEY),
        "foodsafety": bool(config.FOODSAFETY_API_KEY),
        "ftc_csv": config.FTC_CSV_PATH.exists(),
        "rdap": True,
        "llm": bool(config.LLM_BASE_URL and config.LLM_MODEL),
    }
