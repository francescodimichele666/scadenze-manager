@echo off
:: Crea un collegamento sul Desktop che avvia l'app senza finestra nera

set APP_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set VBS_FILE=%APP_DIR%AVVIA_SFONDO.vbs
set LNK_FILE=%DESKTOP%\ScadenzeManager.lnk
set ICON_FILE=%APP_DIR%static\favicon.png

:: Crea il collegamento tramite PowerShell
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%LNK_FILE%'); $s.TargetPath='wscript.exe'; $s.Arguments='\"%VBS_FILE%\"'; $s.WorkingDirectory='%APP_DIR%'; $s.Description='ScadenzeManager - Gestione Scadenze'; $s.Save()"

if exist "%LNK_FILE%" (
    echo.
    echo  Collegamento creato sul Desktop!
    echo  Doppio clic su "ScadenzeManager" per avviare l'app.
    echo.
) else (
    echo  Errore nella creazione del collegamento.
)
pause
