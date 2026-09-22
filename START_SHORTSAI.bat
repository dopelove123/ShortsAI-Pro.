@echo off
setlocal EnableExtensions
title ShortsAI PRO - Local Server
cd /d "%~dp0"

echo.
echo ==========================================
echo       ShortsAI PRO - Local Server
echo ==========================================
echo.

if not exist tools mkdir tools

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo Python was not found.
        echo Install Python 3.10+ and run this file again.
        pause
        exit /b 1
    )
)

echo [1/3] Installing/updating downloader packages...
%PY% -m pip install -U -r requirements.txt
if errorlevel 1 (
    echo.
    echo Package installation failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Checking Deno JavaScript runtime...
if exist "tools\deno.exe" goto deno_ready

where deno >nul 2>nul
if %errorlevel%==0 goto deno_ready

echo Deno not found. Downloading the current Windows x64 Deno runtime...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip'; $z=Join-Path $env:TEMP 'deno_shortsai.zip'; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $z; Expand-Archive -Force $z -DestinationPath '%~dp0tools'; Remove-Item $z -Force"
if not exist "tools\deno.exe" (
    echo.
    echo Could not install Deno automatically.
    echo Install Deno 2.3+ manually, then run this file again.
    echo Official: https://deno.com/
    pause
    exit /b 1
)

:deno_ready
echo Deno ready.

echo.
echo [3/3] FFmpeg is supplied through the Python package imageio-ffmpeg.
echo     No separate FFmpeg install is required.
echo.
echo [4/4] Starting ShortsAI PRO...
echo.
echo Open this in Chrome/Edge:
echo http://127.0.0.1:5000/
echo.
echo Keep this window OPEN while using the website.
echo.

%PY% server.py
pause
