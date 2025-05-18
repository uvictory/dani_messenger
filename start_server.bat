@echo off
REM ✅ 현재 스크립트가 있는 폴더로 이동
cd /d %~dp0

REM ✅ 가상환경이 있는지 확인
IF NOT EXIST .venv\Scripts\activate.bat (
    echo ❌ 가상환경이 존재하지 않습니다. 먼저 생성해 주세요.
    pause
    exit /b
)

REM ✅ 가상환경 활성화
call .venv\Scripts\activate.bat

REM ✅ 서버 실행
uvicorn main:app --host 0.0.0.0 --port 30006 --ws websockets --ws-max-size 4194304

REM ✅ 창 닫힘 방지
pause
