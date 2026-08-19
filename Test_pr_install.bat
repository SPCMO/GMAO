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
echo   Recherche d'un interpreteur Python compatible ^(3.9 ou plus recent^)...

rem -- Detection automatique, sans demander de version : on interroge directement
rem    l'interpreteur par defaut (py, puis python) via -c, ce qui evite les soucis
rem    de syntaxe des drapeaux de version (py -3.14 / py -V:3.14 selon les versions
rem    du Python Launcher) et les erreurs de recopie manuelle d'un chemin.
set "BASE_PYTHON="

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY_OK="
    for /f "delims=" %%V in ('py -c "import sys; print(1 if sys.version_info[:2] >= (3,9) else 0)" 2^>nul') do set "PY_OK=%%V"
    if "!PY_OK!"=="1" (
        for /f "delims=" %%P in ('py -c "import sys; print(sys.executable)" 2^>nul') do set "BASE_PYTHON=%%P"
    )
)

if not "!BASE_PYTHON!"=="" goto trouve

where python >nul 2>&1
if %errorlevel%==0 (
    set "PY_OK="
    for /f "delims=" %%V in ('python -c "import sys; print(1 if sys.version_info[:2] >= (3,9) else 0)" 2^>nul') do set "PY_OK=%%V"
    if "!PY_OK!"=="1" (
        for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "BASE_PYTHON=%%P"
    )
)

if not "!BASE_PYTHON!"=="" goto trouve

:saisie_manuelle
echo.
echo   Aucune version de Python 3.9+ n'a ete detectee automatiquement.
where py >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo   Versions Python detectees par le Python Launcher :
    echo   -------------------------------------------
    py -0
    echo   -------------------------------------------
)
echo.
echo   Entrez le chemin complet vers python.exe ^(3.9 ou plus recent^) :
echo   Astuce : clic droit sur python.exe dans l'explorateur -^> "Copier en tant
echo   que chemin d'acces", puis collez ici (les guillemets copies avec sont
echo   retires automatiquement, inutile de les enlever a la main).
echo.
set /p BASE_PYTHON="   Chemin : "
set BASE_PYTHON=!BASE_PYTHON:"=!
goto valider

:trouve
for /f "delims=" %%V in ('"!BASE_PYTHON!" --version 2^>^&1') do set "PY_VERSION_STR=%%V"
echo.
echo   Python detecte automatiquement : !PY_VERSION_STR!
echo   ^(!BASE_PYTHON!^)

:valider
if "!BASE_PYTHON!"=="" goto saisie_manuelle
"!BASE_PYTHON!" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   [ERR] Impossible d'executer : !BASE_PYTHON!
    echo   Verifiez le chemin ^(python.exe doit exister a cet endroit precis^).
    goto saisie_manuelle
)

echo.
echo   Creation de l'environnement virtuel ^(venv\^)...
"!BASE_PYTHON!" -m venv venv
if not exist venv\Scripts\python.exe (
    echo.
    echo   [ERR] Echec de la creation de l'environnement virtuel.
    echo   Si une fenetre GMAO est deja ouverte ^(meme sur un autre dossier copie
    echo   depuis celui-ci^), fermez-la : Windows verrouille les fichiers d'un
    echo   environnement Python en cours d'utilisation. Puis relancez ce script.
    pause
    exit /b 1
)
echo   Environnement virtuel cree.

:lancer_test
echo.
echo   Lancement de la verification ^(dependances, fichiers du projet^)...
echo.
venv\Scripts\python.exe Test_pr_install.py
