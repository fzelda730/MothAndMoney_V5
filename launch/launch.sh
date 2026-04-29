#!/usr/bin/env bash
# Run from the project root: ./launch.sh
set -e
cd "$(dirname "$0")"

if [[ -f "app/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "app/.venv/bin/activate"
fi

if command -v streamlit >/dev/null 2>&1; then
  exec streamlit run app/app.py
else
  exec python3 -m streamlit run app/app.py
fi
