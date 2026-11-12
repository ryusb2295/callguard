@echo off
chcp 65001 >nul
cd /d %~dp0frontend
if not exist node_modules (
  echo [콜가드] 패키지를 설치하는 중...
  call npm install
)
echo [콜가드] 프론트엔드 실행: http://localhost:5173
call npm run dev
