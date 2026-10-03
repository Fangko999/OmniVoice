@echo off
setlocal EnableExtensions
chcp 65001 >nul
title OmniVoice Launcher

rem ============================================================
rem  OmniVoice v3 - Khoi dong Backend (FastAPI :8000) + Frontend (Vite :5173)
rem ============================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "BACKEND_URL=http://127.0.0.1:8000/"
set "FRONTEND_URL=http://localhost:5173"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo.
echo  ==========================================
echo       OMNIVOICE v3 - Audio truyen AI
echo  ==========================================
echo.

rem ---------- 1. Kiem tra cong cu ----------
where python >nul 2>&1 || (
    echo [LOI] Khong tim thay Python trong PATH. Hay cai Python 3.10+.
    goto :fail
)
where npm >nul 2>&1 || (
    echo [LOI] Khong tim thay Node.js/npm trong PATH. Hay cai Node.js 18+.
    goto :fail
)
if not exist "%ROOT%Kokoro-Vietnamese\src\kokoro_vietnamese" (
    echo [LOI] Thieu thu muc Kokoro-Vietnamese.
    echo       git clone https://github.com/iamdinhthuan/Kokoro-Vietnamese "%ROOT%Kokoro-Vietnamese"
    goto :fail
)
where ffmpeg >nul 2>&1 || echo [CANH BAO] Khong thay ffmpeg trong PATH - xuat MP3 co the loi ^(WAV van chay^).

rem ---------- 2. Thu vien Python ----------
python -c "import fastapi, uvicorn, multipart, ebooklib, bs4, lxml, pydub, soundfile, gemini_webapi" >nul 2>&1
if errorlevel 1 (
    echo [*] Dang cai thu vien Python cho backend...
    python -m pip install -r "%BACKEND%\requirements.txt" || (
        echo [LOI] Cai thu vien Python that bai.
        goto :fail
    )
)
python -c "import torch" >nul 2>&1 || (
    echo [LOI] Chua cai PyTorch / thu vien cua Kokoro-Vietnamese.
    echo       python -m pip install -e "%ROOT%Kokoro-Vietnamese"
    goto :fail
)

rem ---------- 3. Thu vien Node ----------
if not exist "%FRONTEND%\node_modules" (
    echo [*] Dang cai thu vien frontend ^(npm install^)...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        popd
        echo [LOI] npm install that bai.
        goto :fail
    )
    popd
)

rem ---------- 4. Tai khoan Gemini ----------
if not exist "%BACKEND%\accounts.json" (
    if exist "%BACKEND%\accounts.example.json" (
        copy /y "%BACKEND%\accounts.example.json" "%BACKEND%\accounts.json" >nul
    )
    echo [CANH BAO] Chua co backend\accounts.json - da tao tu file mau.
    echo            Tab "AI Dao dien" can cookie that ^(__Secure-1PSID, __Secure-1PSIDTS^).
    echo            Tab "Doc nhanh" va "Thu am kich ban" van dung binh thuong.
    echo.
)

rem ---------- 5. Backend ----------
call :port_in_use 8000
if not errorlevel 1 (
    echo [i] Cong 8000 dang duoc dung - coi nhu backend da chay, bo qua.
) else (
    echo [*] Khoi dong Backend tai %BACKEND_URL% ...
    start "OmniVoice Backend" /D "%BACKEND%" cmd /k python -m uvicorn main:app --host 127.0.0.1 --port 8000
)

echo [*] Doi backend san sang ^(nap model co the mat vai chuc giay^)...
call :wait_url "%BACKEND_URL%" 120
if errorlevel 1 (
    echo [LOI] Backend khong phan hoi sau 120 giay. Xem loi trong cua so "OmniVoice Backend".
    goto :fail
)
echo [OK] Backend da san sang.

rem ---------- 6. Frontend ----------
call :port_in_use 5173
if not errorlevel 1 (
    echo [i] Cong 5173 dang duoc dung - coi nhu frontend da chay, bo qua.
) else (
    echo [*] Khoi dong Frontend tai %FRONTEND_URL% ...
    start "OmniVoice Frontend" /D "%FRONTEND%" cmd /k npm run dev -- --port 5173 --strictPort
)

call :wait_url "%FRONTEND_URL%" 60
if errorlevel 1 (
    echo [LOI] Frontend khong phan hoi sau 60 giay. Xem loi trong cua so "OmniVoice Frontend".
    goto :fail
)
echo [OK] Frontend da san sang.

rem ---------- 7. Mo trinh duyet ----------
start "" "%FRONTEND_URL%"
echo.
echo  OmniVoice dang chay: %FRONTEND_URL%
echo  Dong 2 cua so "OmniVoice Backend" / "OmniVoice Frontend" de tat.
echo.
ping -n 4 127.0.0.1 >nul 2>&1
endlocal
exit /b 0

rem ============================================================
rem  Ham phu
rem ============================================================

:port_in_use
rem errorlevel 0 neu cong %1 dang LISTENING
netstat -ano | findstr /r /c:":%~1 .*LISTENING" >nul
exit /b %errorlevel%

:wait_url
rem %1 = URL, %2 = so giay toi da. errorlevel 0 neu URL phan hoi.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; for($i=0; $i -lt %~2; $i++){ try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%~1' | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
exit /b %errorlevel%

:fail
echo.
echo Khoi dong that bai. Nhan phim bat ky de thoat.
pause >nul
endlocal
exit /b 1
