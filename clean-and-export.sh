#!/usr/bin/env bash
set -euo pipefail

# clean-and-export.sh
# Creates a cleaned copy of the repository suitable for publishing.
# Usage: ./clean-and-export.sh /path/to/output [--history]

OUT_DIR=${1:-./sell_manager_CLI_clean}
PRESERVE_HISTORY=false
if [ "${2:-}" = "--history" ]; then
  PRESERVE_HISTORY=true
fi

echo "Creating cleaned copy at: ${OUT_DIR}"
rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

# Copy working tree (excluding .git)
rsync -a --exclude='.git' ./ "${OUT_DIR}/"

# Remove sensitive or large directories
if [ -d "${OUT_DIR}/logs" ]; then
  echo "Removing logs/"
  rm -rf "${OUT_DIR}/logs"
fi
if [ -d "${OUT_DIR}/config/cache" ]; then
  echo "Removing config/cache/"
  rm -rf "${OUT_DIR}/config/cache"
fi

# Ensure .gitignore exists and contains recommended entries
cat > "${OUT_DIR}/.gitignore" <<'GITIGNORE'
logs/
config/cache/
__pycache__/
.venv/
.vscode/
.idea/
*.pyc
*.pyo
*.pyd
.DS_Store
GITIGNORE

# Create an example assigned_ma file if a real one exists; otherwise create placeholder
if [ -f "${OUT_DIR}/config/assigned_ma.csv" ]; then
  echo "Backing up and creating example assigned_ma file"
  mv "${OUT_DIR}/config/assigned_ma.csv" "${OUT_DIR}/config/assigned_ma.csv.bak"
fi
cat > "${OUT_DIR}/config/assigned_ma.example.csv" <<'CSV'
# ticker,ma_period,assigned_to
EXAMPLE,20,example_user
CSV

# Add a LICENSE if none exists (MIT placeholder)
if [ ! -f "${OUT_DIR}/LICENSE" ]; then
  cat > "${OUT_DIR}/LICENSE" <<'LICENSE'
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
LICENSE
fi

# Optionally preserve history using subtree split
if [ "$PRESERVE_HISTORY" = true ]; then
  echo "Creating subtree branch for sell_manager_CLI history"
  git subtree split -P sell_manager_CLI -b sell_manager-only || true
  echo "Subtree branch 'sell_manager-only' created (if git available)."
fi

echo "Clean export prepared at ${OUT_DIR}"
