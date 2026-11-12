"""(선택) LLM으로 위험 신호와 가족에게 보낼 요약을 보강한다.

OpenAI 호환 /chat/completions 엔드포인트면 무엇이든 된다 (Ollama 포함).
설정이 없거나 실패하면 None을 돌려주고, 규칙 기반 결과만 쓴다.
"""
import json
import re

import httpx

from . import config

PROMPT = """너는 보이스피싱·메신저피싱 예방 도우미다. 아래 메시지를 읽고 JSON만 출력해라.
사기 여부나 발신자 신원을 단정하지 말고, 눈에 띄는 위험 신호만 정리해라.

형식:
{"signals":[{"label":"짧은 이름","evidence":"메시지 속 근거 문구"}],
 "type":"family_impersonation|institution|loan|shopping|link|other",
 "summary":"확인을 부탁받는 가족이 10초 안에 이해할 2문장 요약"}

메시지 (자칭 발신자: {sender}):
---
{message}
---"""


async def analyze(message: str, sender: str) -> dict | None:
    if not (config.LLM_BASE_URL and config.LLM_MODEL):
        return None
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    body = {
        "model": config.LLM_MODEL,
        "temperature": 0,
        "messages": [{"role": "user", "content": PROMPT.replace("{sender}", sender or "알 수 없음").replace("{message}", message[:3000])}],
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            r = await client.post(f"{config.LLM_BASE_URL}/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            return None
        return data
    except Exception:  # noqa: BLE001
        return None
