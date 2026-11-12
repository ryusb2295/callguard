@echo off
chcp 65001 >nul
cd /d %~dp0backend
if not exist .venv (
  echo [콜가드] 파이썬 가상환경을 만드는 중...
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env copy .env.example .env >nul
echo [콜가드] 백엔드 실행: http://localhost:8000/docs
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
