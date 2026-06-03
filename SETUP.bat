@echo off
title ScadenzeManager - Setup
color 1F
cls

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║       SCADENZE MANAGER - Prima installazione ║
echo  ╚══════════════════════════════════════════════╝
echo.
echo  Questo script scarica Python portatile e installa
echo  tutto il necessario. Serve solo la prima volta.
echo.

cd /d "%~dp0"

:: Se Python portatile gia' esiste, salta il download
if exist "python_env\python.exe" (
    echo  Python portatile gia' presente. Aggiorno i pacchetti...
    goto install_packages
)

:: Controlla connessione internet
ping -n 1 google.com >nul 2>&1
if errorlevel 1 (
    echo  [ERRORE] Connessione internet non disponibile.
    echo  Connettiti a internet e riprova.
    pause & exit /b 1
)

echo  [1/3] Scarico Python portatile (circa 25 MB)...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python_embed.zip' -UseBasicParsing"
if not exist python_embed.zip (
    echo  [ERRORE] Download fallito. Controlla la connessione.
    pause & exit /b 1
)

echo  [2/3] Estraggo Python portatile...
powershell -Command "Expand-Archive -Path 'python_embed.zip' -DestinationPath 'python_env' -Force"
del python_embed.zip

:: Abilita l'importazione di pacchetti nel Python portatile
powershell -Command "(Get-Content 'python_env\python311._pth') -replace '#import site', 'import site' | Set-Content 'python_env\python311._pth'"

:: Installa pip
echo  [3/3] Installo pip...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python_env\get-pip.py' -UseBasicParsing"
python_env\python.exe python_env\get-pip.py --quiet
del python_env\get-pip.py

:install_packages
echo.
echo  Installo i pacchetti necessari...
python_env\python.exe -m pip install -r requirements.txt -q --no-warn-script-location
if errorlevel 1 (
    echo  [ERRORE] Installazione pacchetti fallita.
    pause & exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Installazione completata con successo!     ║
echo  ║   D'ora in poi usa AVVIA.bat per avviare     ║
echo  ╚══════════════════════════════════════════════╝
echo.
echo  Avvio l'app...
timeout /t 2 /nobreak >nul

goto start_app

:start_app
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"
python_env\python.exe app.py
pause
