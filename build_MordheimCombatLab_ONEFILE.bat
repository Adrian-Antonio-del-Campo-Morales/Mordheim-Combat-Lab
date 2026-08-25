@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD=python"
py -3.10 --version >nul 2>&1 && set "PYTHON_CMD=py -3.10"

set "NO_PAUSE="
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

echo ================================================
echo  MORDHEIM COMBAT LAB - BUILD ONE FILE EXE
echo ================================================

echo.
echo [1/5] Checking Python...
%PYTHON_CMD% --version
if errorlevel 1 goto :python_error

echo.
echo [2/5] Checking dependencies...
%PYTHON_CMD% -c "import numpy, openpyxl, yaml; print('NumPy:', numpy.__version__, '| openpyxl:', openpyxl.__version__)"
if errorlevel 1 goto :dependency_error

echo.
echo [3/5] Checking PyInstaller and Tkinter...
%PYTHON_CMD% -m PyInstaller --version >nul 2>&1
if errorlevel 1 goto :pyinstaller_error

rem Create a real window: tkinter.Tcl() can work even when Tk scripts required
rem by the application and PyInstaller are missing.
%PYTHON_CMD% -c "import tkinter; root=tkinter.Tk(); root.withdraw(); root.destroy()" >nul 2>&1
if errorlevel 1 (
    rem This Python installation has a broken Tcl. Inkscape often includes a working copy.
    if exist "C:\Program Files\Inkscape\lib\tcl8.6\init.tcl" (
        set "TCL_LIBRARY=C:\Program Files\Inkscape\lib\tcl8.6"
        set "TK_LIBRARY=C:\Program Files\Inkscape\lib\tk8.6"
        %PYTHON_CMD% -c "import tkinter; root=tkinter.Tk(); root.withdraw(); root.destroy()" >nul 2>&1
        if errorlevel 1 goto :tkinter_error
    ) else (
        goto :tkinter_error
    )
)

echo.
echo [4/5] Building native combat kernel...
call build_NATIVE_KERNEL.bat
if errorlevel 1 goto :cython_error

echo.
echo [5/5] Building single EXE...
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name MordheimCombatLab --paths src --hidden-import mordheim_combat_lab._combat_fast --add-data "sources\knowledge;sources\knowledge" src\mordheim_combat_lab\__main__.py
if errorlevel 1 goto :build_error

echo.
echo ================================================
echo  BUILD COMPLETE
echo ================================================
echo.
echo EXE generated at:
echo %CD%\dist\MordheimCombatLab.exe
echo.
call :pause_if_needed
exit /b 0

:python_error
echo ERROR: Python is not available in PATH.
goto :failed

:dependency_error
echo ERROR: A runtime dependency is missing.
echo Run: python -m pip install -r requirements.txt
goto :failed

:pyinstaller_error
echo ERROR: PyInstaller is not installed.
echo Run: python -m pip install pyinstaller
goto :failed

:tkinter_error
echo ERROR: The Tkinter/Tcl installation is not working.
echo Repair the Python installation with Tcl/Tk support and try again.
goto :failed

:cython_error
echo ERROR while compiling the native combat kernel.
echo Install Visual C++ Build Tools and the requirements-dev.txt dependencies.
goto :failed

:build_error
echo ERROR while building MordheimCombatLab.exe.

:failed
call :pause_if_needed
exit /b 1

:pause_if_needed
if not defined NO_PAUSE pause
exit /b 0
