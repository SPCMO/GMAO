@echo off
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~0,2%"=="\\" (
  echo Ce lanceur ne peut pas s'executer directement depuis un dossier reseau ^(chemin \\...^).
  echo.
  echo Copiez d'abord tout le dossier GMAO sur votre disque local ^(ex: D:\GMAO^),
  echo installez l'environnement Python local ^(voir Aide.html, section Parametrage^),
  echo puis relancez ce fichier depuis cette copie locale.
  echo.
  echo Le dossier reseau sert de copie du code et de stockage de la base partagee,
  echo pas a executer l'appli directement dessus.
  pause
  exit /b 1
)
cd /d "%SCRIPT_DIR%"
echo Demarrage de l'appli GMAO...
echo Le navigateur va s'ouvrir automatiquement dans quelques secondes.
echo (Fermez cette fenetre pour arreter l'appli)
echo.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:5000'"
"%~dp0venv\Scripts\python.exe" "%~dp0run.py"
pause
