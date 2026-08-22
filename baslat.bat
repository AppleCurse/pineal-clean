@echo off
chcp 65001 >nul
echo ==============================================
echo PINEAL-HERETIC v2.0 - COMMAND CENTER INITIATION
echo ==============================================
echo.

REM --- 1) Python ortami ---
if not exist venv (
    echo [1/3] venv olusturuluyor...
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt

REM --- 2) Frontend derlemesi (dist yoksa) ---
if not exist frontend\dist (
    echo [2/3] Frontend derleniyor...
    cd frontend
    if not exist node_modules call npm ci
    call npm run build
    cd ..
)

REM --- 3) Sunucu: http://localhost:8000 ---
echo [3/3] Sunucu baslatiliyor: http://localhost:8000
echo.
uvicorn backend.api:app --host 0.0.0.0 --port 8000
pause
