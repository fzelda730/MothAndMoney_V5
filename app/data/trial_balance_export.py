"""
Write trial balance confirm snapshots and chart of accounts to CSV under app/exports/.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import Any

import pandas as pd

_APP_DIR = Path(__file__).resolve().parent.parent
EXPORT_ROOT = _APP_DIR / "exports"


def _slug_reference(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", (name or "").strip(), flags=re.UNICODE)
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return (s or "trial-balance")[:80]


def _cell(x: Any) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except TypeError:
        pass
    if isinstance(x, Real) and not isinstance(x, bool):
        xf = float(x)
        return f"{xf:.2f}"
    return str(x)


def export_trial_balance_grid_csv(
    rows: list[dict[str, Any]],
    reference_name: str,
) -> Path:
    """Rows as from Streamlit df.to_dict('records')."""
    out_dir = EXPORT_ROOT / "trial_balance"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{_slug_reference(reference_name)}_{ts}.csv"
    fields = ["Full name", "COA", "Type", "Match", "Debits", "Credits"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(r.get(k)) for k in fields})
    return path


def export_chart_of_accounts_csv(coa_rows: list[dict[str, Any]]) -> Path:
    """coa_rows: number, name, type, subtype (as from chart_of_accounts())."""
    out_dir = EXPORT_ROOT / "chart_of_accounts"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"chart_of_accounts_{ts}.csv"
    fields = ["account_number", "account_name", "type", "subtype"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in coa_rows:
            w.writerow(
                [
                    _cell(r.get("number")),
                    _cell(r.get("name")),
                    _cell(r.get("type")),
                    _cell(r.get("subtype")),
                ]
            )
    return path
