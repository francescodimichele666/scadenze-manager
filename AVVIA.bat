@echo off
title ScadenzeManager
color 1F
cls
echo.
echo  ================================================
echo   ScadenzeManager - Avvio in corso...
echo  ================================================
echo.

cd /d "%~dp0"

REM Controlla se Python è installato
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERRORE: Python non trovato nel PATH.
    echo  Installa Python da https://python.org
    pause
    exit /b 1
)

REM Installa dipendenze se mancanti
echo  Verifico dipendenze...
pip install -r requirements.txt -q

echo.
echo  App avviata su http://127.0.0.1:5000
echo  Dal cellulare (stessa WiFi) cerca il tuo IP locale.
echo.
echo  Premi CTRL+C per fermare l'app.
echo  ================================================
echo.

REM Aspetta 2 secondi poi apre il browser
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

REM Avvia l'app Flask
python app.py
pause
