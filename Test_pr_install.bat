@echo off
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~0,2%"=="\\" (
  echo Ce script ne peut pas s'executer directement depuis un dossier reseau ^(chemin \\...^).
  echo Copiez d'abord tout le dossier GMAO sur votre disque local, puis relancez-le depuis la.
  pause
  exit /b 1
)
cd /d "%SCRIPT_DIR%"
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   GMAO - Verification / installation de l'environnement
echo ============================================================

if exist venv\Scripts\python.exe (
    echo.
    echo   Environnement virtuel deja present : venv\Scripts\python.exe
    goto lancer_test
)

echo.
echo   Aucun environnement virtuel trouve ^(dossier venv\ absent^).
echo   Il va etre cree.
echo.

where py >nul 2>&1
if %errorlevel% neq 0 goto saisie_manuelle

echo   Versions Python installees sur ce poste :
echo   -------------------------------------------
py -0
echo   -------------------------------------------
echo.
echo   Entrez la version souhaitee ^(ex: 3.13^)
echo   ou le chemin complet vers python.exe
echo   [Entree = version par defaut du Python Launcher]
echo.
set /p CHOIX="   Votre choix : "

if "!CHOIX!"=="" (
    for /f "delims=" %%P in ('py -c "import sys; print(sys.executable)" 2^>nul') do set BASE_PYTHON=%%P
    goto valider
)

echo !CHOIX! | findstr /r "^[0-9][0-9]*\.[0-9]" >nul
if %errorlevel%==0 (
    for /f "delims=" %%P in ('py -!CHOIX! -c "import sys; print(sys.executable)" 2^>nul') do set BASE_PYTHON=%%P
    if "!BASE_PYTHON!"=="" (
        echo.
        echo   [ERR] Python !CHOIX! introuvable via le Python Launcher.
        goto saisie_manuelle
    )
) else (
    set BASE_PYTHON=!CHOIX!
)
goto valider

:saisie_manuelle
echo.
echo   Python Launcher ^(py.exe^) non disponible ou version introuvable.
echo   Entrez le chemin complet vers python.exe :
echo.
set /p BASE_PYTHON="   Chemin : "
if "!BASE_PYTHON!"=="" set BASE_PYTHON=python

:valider
"!BASE_PYTHON!" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   [ERR] Impossible d'executer : !BASE_PYTHON!
    pause
    exit /b 1
)
for /f "delims=" %%V in ('"!BASE_PYTHON!" --version 2^>&1') do echo.   Version validee : %%V

echo.
echo   Creation de l'environnement virtuel ^(venv\^)...
"!BASE_PYTHON!" -m venv venv
if not exist venv\Scripts\python.exe (
    echo.
    echo   [ERR] Echec de la creation de l'environnement virtuel.
    pause
    exit /b 1
)
echo   Environnement virtuel cree.

:lancer_test
echo.
echo   Lancement de la verification...
echo.
venv\Scripts\python.exe Test_pr_install.py
