@echo off
REM Build Windows executable for the GUI using PyInstaller
REM Usage: open Developer PowerShell or CMD with virtualenv activated, then run this script.

SETLOCAL
echo Building sell_manager_gui with PyInstaller...

pyinstaller --noconfirm --clean --onedir --windowed ^
  --hidden-import=qtpy ^
  --hidden-import=PySide6 ^
  --name sell_manager_gui ^
  src\sellmanagement\gui\run_gui.py

if %ERRORLEVEL% EQU 0 (
  echo Build succeeded. Dist folder contains sell_manager_gui\sell_manager_gui.exe
) else (
  echo Build failed with exit code %ERRORLEVEL%.
  echo Try running pyinstaller manually for detailed errors.
)

ENDLOCAL





