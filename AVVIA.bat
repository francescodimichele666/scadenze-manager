@echo off
title ScadenzeManager
color 5F
cls

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║         SCADENZE MANAGER  - Avvio            ║
echo  ╚══════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Usa Python portatile se presente, altrimenti quello di sistema
if exist "python_env\python.exe" (
    set PYTHON="%~dp0python_env\python.exe"
    echo  Uso Python portatile incluso.
) else (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo  Python non trovato!
        echo.
        echo  Opzione 1: esegui SETUP.bat per installare Python portatile
        echo  Opzione 2: scarica Python da https://python.org
        echo.
        pause
        exit /b 1
    )
    set PYTHON=python
    echo  Uso Python di sistema.
)

:: Controlla se la porta 5000 e' gia' in uso
netstat -ano | findstr ":5000 " >nul 2>&1
if not errorlevel 1 (
    echo  App gia' in esecuzione - apro il browser...
    timeout /t 1 /nobreak >nul
    start http://127.0.0.1:5000
    exit /b 0
)

echo.
echo  ┌─────────────────────────────────────────────┐
echo  │  Indirizzo locale:  http://127.0.0.1:5000   │
echo  │  Dal cellulare:     cerca il tuo IP locale  │
echo  │                                             │
echo  │  Premi CTRL+C per fermare l'app             │
echo  └─────────────────────────────────────────────┘
echo.

:: Apre il browser dopo 2 secondi
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

:: Avvia Flask
%PYTHON% app.py

echo.
echo  App fermata. Premi un tasto per chiudere.
pause >nul
