@echo off
echo ==============================================
echo PINEAL-HERETIC v2.0 - COMMAND CENTER INITIATION
echo ==============================================
echo.
echo Cekirdek motor ve arayuz baslatiliyor...
echo Lutfen tarayicidan http://localhost:8501 adresine gidin.
echo.
call venv\Scripts\activate.bat
uvicorn backend.api:app --host 0.0.0.0 --port 8501
pause
