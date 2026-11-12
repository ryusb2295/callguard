"""해외직구 성분표 검사 (사기전에 기능).

실제 데이터: 식품안전나라 '해외직구 위해식품 차단정보'(서비스 I2715). 차단된 제품의 검출성분 목록에
성분표의 성분이 몇 번 나오는지 센다. 키(FOODSAFETY_API_KEY)가 없으면 시연 모드에서만 아래 시연용 목록을 쓴다.
"""
import re

import httpx

from . import config

# 시연용 목록: 직구 차단 목록 검출성분으로 자주 보이는 성분 (실제 판정은 API 데이터로 해야 함)
DEMO_LIST = {
    "yohimbine": ("요힘빈", ["yohimbine", "yohimbe", "요힘빈", "요힘베"]),
    "sibutramine": ("시부트라민", ["sibutramine", "시부트라민"]),
    "phenolphthalein": ("페놀프탈레인", ["phenolphthalein", "페놀프탈레인"]),
    "dmaa": ("DMAA(디메틸아밀아민)", ["dmaa", "1,3-dimethylamylamine", "dimethylamylamine", "디메틸아밀아민"]),
    "sildenafil": ("실데나필", ["sildenafil", "실데나필"]),
    "tadalafil": ("타다라필", ["tadalafil", "타다라필"]),
    "ephedra": ("에페드라(마황)", ["ephedra", "ephedrine", "ma huang", "에페드린", "마황"]),
    "melatonin": ("멜라토닌", ["melatonin", "멜라토닌"]),
    "5htp": ("5-HTP", ["5-htp", "5-hydroxytryptophan", "5-하이드록시트립토판"]),
}

_api_cache: list[str] | None = None


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_·.,()]+", "", (s or "").lower())


async def _load_api_rows() -> list[str] | None:
    """차단 제품마다 검출성분 문자열을 모은다. 필드 이름이 바뀌어도 동작하도록 모든 문자열 값을 합친다."""
    global _api_cache
    if _api_cache is not None:
        return _api_cache
    if not config.FOODSAFETY_API_KEY:
        return None
    rows: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            for start in range(1, 6001, 1000):
                url = f"http://openapi.foodsafetykorea.go.kr/api/{config.FOODSAFETY_API_KEY}/I2715/json/{start}/{start + 999}"
                r = await client.get(url)
                r.raise_for_status()
                block = (r.json().get("I2715") or {}).get("row") or []
                if not block:
                    break
                rows += [" ".join(str(v) for v in row.values() if isinstance(v, str)) for row in block]
    except Exception:  # noqa: BLE001
        return None
    _api_cache = rows
    return rows


def split_ingredients(text: str) -> list[str]:
    parts = re.split(r"[,\n;/·•]|\s{2,}", text or "")
    out = []
    for p in parts:
        p = re.sub(r"\(?\d+(\.\d+)?\s*(mg|mcg|μg|g|iu|%)\)?", "", p, flags=re.I).strip(" :-")
        if re.fullmatch(r"(supplement|nutrition)\s*facts?|serving size.*|servings? per.*|amount per serving|ingredients?|other ingredients?|영양\s*정보|원재료(명)?", p, re.I):
            continue
        if 2 <= len(p) <= 60:
            out.append(p)
    return list(dict.fromkeys(out))


async def check_ingredients(text: str) -> tuple[list[dict], list[str]]:
    """(checks, 인식한 성분 목록)."""
    items = split_ingredients(text)
    joined = _norm(text)
    checks: list[dict] = []
    rows = await _load_api_rows()
    if rows is not None:
        src = "식품안전나라 직구 위해식품 차단정보"
        norm_rows = [_norm(r) for r in rows]
        for item in items:
            key = _norm(item)
            if len(key) < 4:
                continue
            hits = sum(1 for r in norm_rows if key in r)
            if hits:
                checks.append({"type": "ingredient", "target": item, "source": src, "status": "danger",
                               "detail": f"차단된 직구 제품 {hits}건에서 검출된 성분이에요", "demo": False, "matched": [item]})
        if not checks:
            checks.append({"type": "ingredient", "target": f"성분 {len(items)}개", "source": src, "status": "ok",
                           "detail": "차단 제품 검출성분과 겹치는 성분이 없어요", "demo": False})
        return checks, items
    if config.DEMO_MODE:
        for _, (ko, aliases) in DEMO_LIST.items():
            if any(_norm(a) in joined for a in aliases):
                matched = [it for it in items if any(_norm(a) in _norm(it) for a in aliases)]
                checks.append({"type": "ingredient", "target": ko, "source": "직구 차단 성분 (시연용 목록)", "status": "danger",
                               "detail": "직구 차단 제품에서 자주 검출되는 성분이에요. 통관 단계에서 폐기될 수 있어요", "demo": True,
                               "matched": matched})
        if not checks:
            checks.append({"type": "ingredient", "target": f"성분 {len(items)}개", "source": "직구 차단 성분 (시연용 목록)",
                           "status": "ok", "detail": "시연용 목록과 겹치는 성분이 없어요", "demo": True})
        return checks, items
    checks.append({"type": "ingredient", "target": f"성분 {len(items)}개", "source": "식품안전나라 직구 위해식품 차단정보",
                   "status": "unknown", "detail": "API 키가 설정되지 않았어요", "demo": False})
    return checks, items
