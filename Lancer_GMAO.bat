@echo off
cd /d "%~dp0"
echo Demarrage de l'appli GMAO...
echo Le navigateur va s'ouvrir automatiquement dans quelques secondes.
echo (Fermez cette fenetre pour arreter l'appli)
echo.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:5000'"
"%~dp0venv\Scripts\python.exe" "%~dp0run.py"
pause
