#!/usr/bin/env bash
# Simple packaging script using pyinstaller (example)
set -euo pipefail
echo "Packaging GUI with PyInstaller..."
pyinstaller --noconfirm --onefile -n sell_manager_gui src/sellmanagement/gui/run_gui.py
echo "Done. Dist contains the executable."





