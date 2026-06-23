@echo off
setlocal enableextensions
cd /d "%~dp0\.."

set "VENV=.build-venv"
set "WHEELS=packaging\wheels"
set "GLM_DIR=packaging\.glm"
set "GLM_VER=1.0.1"
set "GLM_URL=https://github.com/g-truc/glm/releases/download/%GLM_VER%/glm-%GLM_VER%-light.zip"

REM Python 3.12 venv: created once, reused after.
if exist "%VENV%\Scripts\activate.bat" (
    echo === Reusing build venv ===
) else (
    echo === Creating build venv ^(Python 3.12^) ===
    py -3.12 -m venv "%VENV%" || goto :err
)
call "%VENV%\Scripts\activate.bat" || goto :err
python -m pip install --upgrade pip wheel || goto :err

REM pydelatin has no Windows wheel. Build once against glm, then cache.
if not exist "%WHEELS%" mkdir "%WHEELS%"
dir /b "%WHEELS%\pydelatin-*.whl" >nul 2>nul
if errorlevel 1 (
    echo === Building pydelatin wheel ^(one time^) ===
    call :build_pydelatin || goto :err
) else (
    echo === Reusing cached pydelatin wheel ===
)

echo === Installing dependencies ===
pip install --find-links "%WHEELS%" -r requirements-windowsbundle.txt || goto :err
pip install pyinstaller==6.20.0 pytest || goto :err

echo === Check if Imports resolve ===
python -c "import build123d, shapely, pyvista, pyvistaqt, pydelatin; from PySide6 import QtWidgets, QtSvg, QtOpenGLWidgets; print('deps OK')" || goto :err

echo === Refreshing Windows version resource ===
python packaging\make_version_info.py || goto :err

echo === Building one-folder bundle ===
pyinstaller --clean --noconfirm PartsPack.spec || goto :err

echo.
echo === DONE ===
echo Bundle:      dist\PartsPack.exe
echo.
deactivate
echo Press any key to close...
pause >nul
endlocal
exit /b 0

REM Build pydelatin wheel using glm headers; download glm if absent.
:build_pydelatin
if not exist "%GLM_DIR%\glm\glm.hpp" (
    echo --- downloading glm %GLM_VER% ---
    if not exist "%GLM_DIR%" mkdir "%GLM_DIR%"
    curl -L -o "%GLM_DIR%\glm.zip" "%GLM_URL%" || (echo *** glm download failed & exit /b 1)
    tar -xf "%GLM_DIR%\glm.zip" -C "%GLM_DIR%" || (echo *** glm extract failed & exit /b 1)
)
set "GLM_INC=%CD%\%GLM_DIR%"
if not exist "%GLM_INC%\glm\glm.hpp" (echo *** glm headers missing at %GLM_INC%\glm\glm.hpp & exit /b 1)
set "INCLUDE=%GLM_INC%;%INCLUDE%"
pip wheel pydelatin --no-deps --no-binary pydelatin --wheel-dir "%WHEELS%" || exit /b 1
exit /b 0

:err
echo.
echo *** BUILD FAILED -- see the error above ***
echo If "py -3.12" was not found, install python.org 3.12 with the py launcher. https://www.python.org/downloads/windows/
echo.
echo Press any key to close...
pause >nul
endlocal
exit /b 1