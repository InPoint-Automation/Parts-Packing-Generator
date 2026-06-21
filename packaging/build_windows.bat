@echo off
setlocal

cd /d "%~dp0\.."

if exist ".build-venv\Scripts\activate.bat" (
    echo === Reusing existing build virtual environment ===
) else (
    echo === Creating build virtual environment (Python 3.12) ===
    py -3.12 -m venv .build-venv || goto :err
)
call .build-venv\Scripts\activate.bat || goto :err

echo === Installing dependencies ===
python -m pip install --upgrade pip || goto :err
pip install -r requirements-windowsbundle.txt || goto :err
pip install pyinstaller==6.20.0 || goto :err

echo === Sanity check: imports resolve ===
python -c "import build123d, shapely, pyvista, pyvistaqt; from PySide6 import QtWidgets, QtSvg, QtOpenGLWidgets; print('deps OK')" || goto :err

echo === Refreshing Windows version resource ===
python packaging\make_version_info.py || goto :err

echo === Running test suite (build aborts on failure) ===
pip install pytest || goto :err
python -m pytest -q || goto :err

echo === Building one-folder bundle ===
pyinstaller --clean --noconfirm PartsPack.spec || goto :err

echo.
echo === DONE ===
echo Bundle:      dist\PartsPack\PartsPack.exe
echo Smoke-test:  dist\PartsPack\PartsPack.exe  (window should open)
echo Distribute:  zip the whole dist\PartsPack\ folder
echo.
deactivate
endlocal
exit /b 0

:err
echo.
echo *** BUILD FAILED -- see the error above ***
echo If "py -3.12" was not found, install it with:  pymanager install 3.12
endlocal
exit /b 1
