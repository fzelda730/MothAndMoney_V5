#!/bin/bash
# Double-click this file in Finder (macOS) to start the Streamlit app.
# First run: chmod +x launch.command  (or right-click → Open once if Gatekeeper complains)

cd "$(dirname "$0")" || exit 1

if [ -f "app/.venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "app/.venv/bin/activate"
fi

if command -v streamlit >/dev/null 2>&1; then
  exec streamlit run app/app.py
else
  exec python3 -m streamlit run app/app.py
fi
