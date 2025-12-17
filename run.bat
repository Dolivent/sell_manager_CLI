@echo off
rem change to project directory (location of this .bat)
cd /d "%~dp0"

rem start PowerShell, keep window open, and run the module
start "" powershell -NoExit -ExecutionPolicy Bypass -Command "python -m src.sellmanagement.gui.run_gui"