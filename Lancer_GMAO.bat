@echo off
cd /d "%~dp0"
echo Demarrage de l'appli GMAO...
echo Ouvrez http://localhost:5000 dans votre navigateur une fois le serveur demarre.
echo (Fermez cette fenetre pour arreter l'appli)
echo.
"%~dp0venv\Scripts\python.exe" "%~dp0run.py"
pause
