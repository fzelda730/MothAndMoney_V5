from __future__ import annotations

import hashlib
import html
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.coa_fuzzy_match import (
    TB_COLUMN_NOT_USED,
    TB_FIELD_ACCOUNT_TYPE,
    TB_FIELD_COA_NAME,
    TB_FIELD_COA_NUMBER,
    TB_FIELD_CREDITS,
    TB_FIELD_DEBITS,
    TB_MAP_FIELD_KEYS,
    build_tb_preview_from_csv,
    parse_trial_balance_csv_with_mapping,
    suggest_trial_balance_column_mapping,
    trial_balance_csv_headers_from_bytes,
)
from data.providers import (
    bank_accounts_for_tb_mapping,
    chart_of_accounts,
    db_ready,
    discard_pending_trial_balance,
    save_trial_balance_csv_to_db,
    trial_balance_import,
)
from data.trial_balance_export import (
    export_chart_of_accounts_csv,
    export_trial_balance_grid_csv,
)
from db.connection import use_sample_data

st.set_page_config(
    page_title="Trial Balance | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# (display label, session field key, allow "— Not used —")
TB_MAP_UI_SPECS: list[tuple[str, str, bool]] = [
    ("Chart of Account (number)", TB_FIELD_COA_NUMBER, True),
    ("Chart of Account (name)", TB_FIELD_COA_NAME, True),
    ("Account type in file (optional)", TB_FIELD_ACCOUNT_TYPE, True),
    ("Debits", TB_FIELD_DEBITS, False),
    ("Credits", TB_FIELD_CREDITS, False),
]


def _empty_tb_totals() -> dict:
    return {
        "total_debits": 0.0,
        "total_credits": 0.0,
        "is_balanced": False,
        "variance": 0.0,
    }


COA_ADD_NEW_LABEL = "➕ Add new account…"
COA_UNMAPPED_LABEL = "— Select COA —"


def _looks_like_tb_import_account_line_label(s: str) -> bool:
    """True when the CSV-derived account line looks like the TB book placeholder, not a real account name."""
    t = (s or "").strip().lower().replace(" ", "").replace("_", "")
    if not t:
        return False
    return t in ("tb-import", "tbimport") or "tb-import" in t


def _apply_tb_bank_mapping_to_records(records: list[dict]) -> int:
    """
    Set bank_account_id on each row from sidebar selectboxes (key tb_bank_map_*).
    Returns count of rows assigned to a real bank account.
    """
    baa = bank_accounts_for_tb_mapping()
    if not baa:
        return 0
    ids = [None] + [a["id"] for a in baa]
    n = 0
    for rec in records:
        fn = str(rec.get("Full name", "")).strip()
        h = hashlib.md5(fn.encode("utf-8")).hexdigest()[:16]
        key = f"tb_bank_map_{h}"
        idx = int(st.session_state.get(key, 0))
        if 0 < idx < len(ids):
            rec["bank_account_id"] = ids[idx]
            n += 1
    return n


def _is_blank_coa_cell(value: object) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    s = str(value).strip().lower()
    return s in ("", "nan", "none")


def _coa_cell_is_add_new(value: object) -> bool:
    if _is_blank_coa_cell(value):
        return False
    s = str(value).strip()
    if s == COA_ADD_NEW_LABEL:
        return True
    s_ell = s.replace("...", "…")
    canon = COA_ADD_NEW_LABEL.replace("...", "…")
    if s_ell == canon:
        return True
    low = s.lower()
    return "add new account" in low


def _suggest_next_coa_number(merged_coa: list[dict]) -> str:
    """Next free slot in 1000–1999 stepping by 10 (typical asset bank accounts)."""
    lo, hi = 1000, 1999
    nums: set[int] = set()
    for r in merged_coa:
        n = str(r.get("number", "")).strip()
        if n.isdigit():
            v = int(n)
            if lo <= v <= hi:
                nums.add(v)
    if not nums:
        return "1010"
    m = max(nums)
    cand = m + 10
    while cand <= hi and cand in nums:
        cand += 10
    if cand <= hi:
        return str(cand)
    for v in range(lo, hi + 1, 10):
        if v not in nums:
            return str(v)
    return "1010"


def _merge_coa_rows(base: list[dict], extra: list[dict]) -> list[dict]:
    """Merge chart rows with session custom COAs; extra overrides same account number."""
    by_num: dict[str, dict] = {}
    for r in base:
        num = str(r.get("number", "")).strip()
        if num:
            by_num[num] = {
                "number": num,
                "name": str(r.get("name", "")).strip(),
                "type": str(r.get("type", "")).strip(),
                "subtype": str(r.get("subtype", "") or "").strip(),
            }
    for e in extra:
        num = str(e.get("number", "")).strip()
        if not num:
            continue
        by_num[num] = {
            "number": num,
            "name": (e.get("name") or "").strip() or f"Account {num}",
            "type": (e.get("type") or "Asset").strip(),
            "subtype": str(e.get("subtype", "") or "").strip(),
        }
    return sorted(by_num.values(), key=lambda r: str(r["number"]))


def _coa_option_labels(coa_rows: list[dict]) -> list[str]:
    """Chart options in the COA column are account numbers only (name stays in Account line)."""
    out: list[str] = []
    for r in coa_rows:
        n = str(r.get("number", "")).strip()
        if n:
            out.append(n)
    return out


def _coa_select_options(
    real_labels: list[str], import_extras: list[str] | None = None
) -> list[str]:
    """Add-new first, chart labels, then import-only lines not on chart; unmapped if chart empty."""
    seen: set[str] = set(real_labels)
    extras: list[str] = []
    for x in import_extras or []:
        xs = (x or "").strip()
        if xs and xs not in seen:
            seen.add(xs)
            extras.append(xs)
    out = [COA_ADD_NEW_LABEL] + list(real_labels) + extras
    if not real_labels:
        out.append(COA_UNMAPPED_LABEL)
    return out


def _unique_import_coa_labels(preview_rows: list[dict], chart_opts: list[str]) -> list[str]:
    """
    Extra COA dropdown values: account numbers from the file that are not on the chart yet.
    """
    chart_nums = {str(o).strip() for o in chart_opts}
    chart_nums.discard("")
    out: list[str] = []
    seen: set[str] = set()
    for row in preview_rows:
        fn = (row.get("bank_account") or "").strip()
        if not fn:
            continue
        num = (str(row.get("csv_account_number") or "").strip() or _account_number_from_label(fn))
        if not num:
            continue
        if num in chart_nums:
            continue
        if num not in seen:
            seen.add(num)
            out.append(num)
    return out


def _first_real_coa_in_options(coa_opts: list[str]) -> str | None:
    for o in coa_opts:
        if o not in (COA_ADD_NEW_LABEL, COA_UNMAPPED_LABEL):
            return o
    return None


def _account_number_from_label(label: str) -> str:
    """Leading account number from '1100 — Cash' or '1100 - Cash' style labels."""
    s = (label or "").strip()
    if not s:
        return ""
    for sep in (" — ", " - ", " – "):
        if sep in s:
            return s.split(sep, 1)[0].strip()
    parts = s.split(None, 1)
    return parts[0].strip() if parts else ""


def _coerce_coa_cell_to_option(
    value: object,
    coa_opts: list[str],
    fallback: object | None = None,
) -> str:
    """
    SelectboxColumn requires each cell value to exactly match an entry in options.
    Normalize hyphen/em dash variants and map by account number.
    Blank/NaN uses fallback (e.g. last saved row) when valid, else unmapped — never snap to a random real account.
    """
    if not coa_opts:
        return "" if _is_blank_coa_cell(value) else str(value).strip()
    if _is_blank_coa_cell(value):
        if fallback is not None and not _is_blank_coa_cell(fallback):
            return _coerce_coa_cell_to_option(fallback, coa_opts, fallback=None)
        if COA_UNMAPPED_LABEL in coa_opts:
            return COA_UNMAPPED_LABEL
        fr = _first_real_coa_in_options(coa_opts)
        return fr if fr else coa_opts[0]
    if _coa_cell_is_add_new(value):
        return COA_ADD_NEW_LABEL if COA_ADD_NEW_LABEL in coa_opts else coa_opts[0]
    vs = str(value).strip()
    if vs in coa_opts:
        return vs

    def _norm(x: str) -> str:
        return (
            x.replace("—", "-")
            .replace("–", "-")
            .replace("  ", " ")
            .strip()
            .lower()
        )

    nv = _norm(vs)
    for opt in coa_opts:
        if opt in (COA_ADD_NEW_LABEL, COA_UNMAPPED_LABEL):
            continue
        if _norm(opt) == nv:
            return opt

    num = _account_number_from_label(vs)
    for opt in coa_opts:
        if opt in (COA_ADD_NEW_LABEL, COA_UNMAPPED_LABEL):
            continue
        ost = str(opt).strip()
        if ost == vs.strip() or (num and ost == num):
            return opt

    fr = _first_real_coa_in_options(coa_opts)
    if fr:
        return fr
    if COA_UNMAPPED_LABEL in coa_opts:
        return COA_UNMAPPED_LABEL
    return coa_opts[0]


def _ensure_coa_column_matches_options(
    df: pd.DataFrame,
    coa_opts: list[str],
    prev_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = df.copy()
    prev_coa = (
        prev_df["COA"].tolist()
        if prev_df is not None and "COA" in prev_df.columns
        else None
    )
    coerced: list[str] = []
    for j, v in enumerate(out["COA"]):
        fb = prev_coa[j] if prev_coa is not None and j < len(prev_coa) else None
        coerced.append(_coerce_coa_cell_to_option(v, coa_opts, fallback=fb))
    out["COA"] = coerced
    return out


def _type_for_coa_label(label: str, coa_rows: list[dict]) -> str:
    if (
        not label
        or not coa_rows
        or label in (COA_ADD_NEW_LABEL, COA_UNMAPPED_LABEL)
        or _coa_cell_is_add_new(label)
    ):
        return "—"
    num = _account_number_from_label(label)
    if not num:
        return "—"
    for r in coa_rows:
        if str(r.get("number", "")).strip() == num:
            return str(r.get("type") or "—")
    return "—"


def _display_type_row(coa_lab: str, coa_rows: list[dict], csv_type_fallback: str) -> str:
    """Chart type for selected Acct #; if none, show value from mapped Account type column."""
    t = _type_for_coa_label(coa_lab, coa_rows)
    if t and str(t).strip() != "—":
        return t
    c = (csv_type_fallback or "").strip()
    return c if c else "—"


def _tb_csv_types_aligned(n_rows: int) -> list[str]:
    raw = st.session_state.get("tb_csv_type_from_file")
    if not isinstance(raw, list):
        return [""] * n_rows
    out = [str(x or "").strip() for x in raw[:n_rows]]
    while len(out) < n_rows:
        out.append("")
    return out[:n_rows]


def _tb_type_series(df: pd.DataFrame, coa_rows: list[dict], csv_types: list[str]) -> pd.Series:
    n = len(df)
    aligned = list(csv_types[:n])
    while len(aligned) < n:
        aligned.append("")
    return pd.Series(
        [
            _display_type_row(str(df.iloc[i]["COA"]), coa_rows, aligned[i])
            for i in range(n)
        ],
        index=df.index,
    )


def _pick_coa_label(
    coa_number: str,
    coa_label_fuzzy: str,
    coa_options: list[str],
    bank_line: str = "",
) -> str:
    if not coa_options:
        return ""
    num = (coa_number or "").strip()
    if num and num in coa_options:
        return num
    bl_n = _account_number_from_label(bank_line).strip()
    if bl_n and bl_n in coa_options:
        return bl_n
    fuzz = (coa_label_fuzzy or "").strip()
    if fuzz in coa_options:
        return fuzz
    fuzz_n = _account_number_from_label(fuzz).strip()
    if fuzz_n and fuzz_n in coa_options:
        return fuzz_n
    return COA_UNMAPPED_LABEL


def _tb_preview_rows_coa_ready(df: pd.DataFrame) -> bool:
    for v in df["COA"]:
        if _coa_cell_is_add_new(v) or str(v).strip() == COA_UNMAPPED_LABEL:
            return False
    return True


def _tb_preview_to_dataframe(
    preview_rows: list[dict],
    coa_rows: list[dict],
    coa_options: list[str],
    import_extras: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    match_opts = list(coa_options) + list(import_extras)
    rows_out: list[dict] = []
    csv_types_out: list[str] = []
    for row in preview_rows:
        lab = _pick_coa_label(
            str(row.get("coa_number", "")),
            str(row.get("coa", "")),
            match_opts,
            str(row.get("bank_account", "")),
        )
        if not lab:
            lab = COA_UNMAPPED_LABEL
        ms = row.get("match_score")
        match_str = (
            f"{int(round(float(ms) * 100))}%" if ms is not None else "—"
        )
        deb = row.get("debits")
        crd = row.get("credits")
        csv_t = str(row.get("account_type_csv", "")).strip()
        csv_types_out.append(csv_t)
        type_disp = _display_type_row(lab, coa_rows, csv_t)
        rows_out.append(
            {
                "Full name": row["bank_account"],
                "COA": lab,
                "Type": type_disp,
                "Match": match_str,
                "Debits": float(deb) if deb is not None else 0.0,
                "Credits": float(crd) if crd is not None else 0.0,
            }
        )
    return pd.DataFrame(rows_out), csv_types_out


load_css()
render_sidebar("onboarding")
render_topbar()

if not db_ready():
    st.stop()

if not use_sample_data():
    st.session_state.pop("tb_import_cleared", None)

if st.session_state.pop("tb_discard_done", False):
    st.success(st.session_state.pop("tb_discard_msg", "Import discarded."))

# ── Breadcrumb ────────────────────────────────────────────────────────────────
st.html("""
<div style="font-size:0.75rem;color:#636262;margin-bottom:1.5rem;
            display:flex;align-items:center;gap:0.5rem;">
    <span style="font-weight:700;">STEP 1 OF 3</span>
    <span>•</span>
    <span>Trial Balance Initialization</span>
</div>
<h1 style="font-family:'Manrope',sans-serif;font-size:2.5rem;font-weight:800;
           margin:0 0 0.75rem;letter-spacing:-0.02em;">
    Import your financial <em style="color:#154212;">DNA.</em>
</h1>
<p style="color:#636262;max-width:36rem;line-height:1.6;margin-bottom:2.5rem;">
    Upload your current trial balance to sync the Atelier with your existing records.
    We'll handle the architectural mapping.
</p>
""")

if st.session_state.get("tb_discard_confirm"):
    st.warning(
        "Discard this import? Pending trial balance rows will be removed from the database "
        "(confirmed entries are kept). Your reference name, file selection, and column mapping "
        "will be reset."
    )
    c_yes, c_no = st.columns(2)
    with c_yes:
        if st.button("Yes, discard", key="tb_yes_discard", type="primary"):
            n = discard_pending_trial_balance()
            st.session_state["tb_discard_confirm"] = False
            st.session_state["tb_uploader_nonce"] = st.session_state.get("tb_uploader_nonce", 0) + 1
            st.session_state.pop("tb_ref_name", None)
            for fk in TB_MAP_FIELD_KEYS:
                st.session_state.pop(f"tb_map_{fk}", None)
            st.session_state.pop("tb_csv_hdr_sig", None)
            if use_sample_data():
                st.session_state["tb_import_cleared"] = True
            st.session_state.pop("tb_file_name", None)
            for k in (
                "tb_csv_sig",
                "tb_csv_df",
                "tb_csv_totals",
                "tb_custom_coa",
                "tb_prev_coa_labels",
                "tb_prev_coa_sig",
                "tb_prev_coa_map_sig",
                "tb_coa_pending_add_row",
                "tb_coa_pending_full_name",
                "tb_coa_pending_revert_coa",
                "tb_csv_hdr_sig",
                "tb_csv_map_sig",
                "tb_coa_import_extras",
                "tb_csv_type_from_file",
            ):
                st.session_state.pop(k, None)
            if use_sample_data():
                st.session_state["tb_discard_msg"] = "Demo import cleared. Form reset."
            elif n:
                st.session_state["tb_discard_msg"] = f"Discarded {n} pending row(s). Form reset."
            else:
                st.session_state["tb_discard_msg"] = (
                    "No pending rows in the database. Form reset."
                )
            st.session_state["tb_discard_done"] = True
            st.rerun()
    with c_no:
        if st.button("Cancel", key="tb_cancel_discard"):
            st.session_state["tb_discard_confirm"] = False
            st.rerun()
    st.html("<div style='height:1rem'></div>")

col_left, col_right = st.columns([1, 1.5], gap="large")

# ── Left: Upload & Column Mapping ─────────────────────────────────────────────
with col_left:
    st.html('<label class="mm-settings-label">Balance Reference Name</label>')
    ref_name = st.text_input(
        "ref_name",
        placeholder="e.g. FY24 Opening Balance",
        label_visibility="collapsed",
        key="tb_ref_name",
    )
    st.caption("This name will be used to identify this entry in your Ledger audit trail.")

    st.html("<div style='height:1rem'></div>")

    uploaded = st.file_uploader(
        "Drop .csv file here",
        type=["csv"],
        help="Trial balance by chart of account: map your CSV column headings to COA number/name, "
        "debits, and credits. Legacy files with Full name + Debit + Credit still work.",
        label_visibility="visible",
        key=f"tb_upload_{st.session_state.get('tb_uploader_nonce', 0)}",
    )

    tb_hdr_list: list[str] = []

    if uploaded is None:
        st.session_state.pop("tb_custom_coa", None)
        for _k in (
            "tb_coa_pending_add_row",
            "tb_coa_pending_full_name",
            "tb_coa_pending_revert_coa",
        ):
            st.session_state.pop(_k, None)

    if uploaded is not None:
        st.session_state["tb_import_cleared"] = False
        st.session_state["tb_file_name"] = uploaded.name
        st.success(f"File loaded: {uploaded.name}")
        st.session_state.setdefault("tb_custom_coa", [])
        raw_left = uploaded.getvalue()
        tb_hdr_list, _tb_hdr_i = trial_balance_csv_headers_from_bytes(raw_left)
        if tb_hdr_list:
            hsig = hashlib.sha256(
                b"\0".join(x.encode("utf-8", errors="replace") for x in tb_hdr_list)
            ).hexdigest()[:28]
            if st.session_state.get("tb_csv_hdr_sig") != hsig:
                st.session_state["tb_csv_hdr_sig"] = hsig
                sugg = suggest_trial_balance_column_mapping(tb_hdr_list)
                for fk in TB_MAP_FIELD_KEYS:
                    st.session_state.pop(f"tb_map_{fk}", None)
                for fk in TB_MAP_FIELD_KEYS:
                    allow_unused = fk in (
                        TB_FIELD_COA_NUMBER,
                        TB_FIELD_COA_NAME,
                        TB_FIELD_ACCOUNT_TYPE,
                    )
                    pick = sugg.get(fk)
                    if pick and pick in tb_hdr_list:
                        st.session_state[f"tb_map_{fk}"] = pick
                    elif allow_unused:
                        st.session_state[f"tb_map_{fk}"] = TB_COLUMN_NOT_USED
                    else:
                        st.session_state[f"tb_map_{fk}"] = tb_hdr_list[0]

    st.html("<div style='height:1.5rem'></div>")

    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1rem;
               margin-bottom:1.25rem;">Column Mapping</h4>
    """)
    if uploaded is None:
        st.caption("Upload a CSV to see its column headings here.")
    elif not tb_hdr_list:
        st.caption(
            "Could not detect a header row. Try a row that includes Account, Debit, and Credit labels."
        )
    else:
        st.caption(
            "Each dropdown lists columns from your file. Use Not used for optional fields."
        )
        for label, fk, allow_unused in TB_MAP_UI_SPECS:
            opts = ([TB_COLUMN_NOT_USED] if allow_unused else []) + tb_hdr_list
            sk = f"tb_map_{fk}"
            if sk not in st.session_state or st.session_state[sk] not in opts:
                st.session_state[sk] = opts[0]
            st.html(f'<label class="mm-settings-label">{label}</label>')
            st.selectbox(
                f"map_{fk}",
                opts,
                label_visibility="collapsed",
                key=sk,
            )
            st.html("<div style='height:0.25rem'></div>")

# ── Right: Import Preview ─────────────────────────────────────────────────────
with col_right:
    tb_parse_note = ""
    tb_csv_mode = False
    tb_parse_used_legacy = False
    coa_rows: list[dict] = []

    if uploaded is not None:
        raw_csv = uploaded.getvalue()
        mapping = {
            fk: st.session_state.get(f"tb_map_{fk}", TB_COLUMN_NOT_USED)
            for fk in TB_MAP_FIELD_KEYS
        }
        parsed, header_idx, map_err, tb_parse_used_legacy = (
            parse_trial_balance_csv_with_mapping(
                raw_csv,
                mapping,
                TB_COLUMN_NOT_USED,
            )
        )
        if parsed:
            merged_coa = _merge_coa_rows(
                chart_of_accounts(),
                st.session_state.get("tb_custom_coa", []),
            )
            sig = hashlib.sha256(raw_csv).hexdigest() + "|" + (uploaded.name or "")
            map_parts = "|".join(
                str(st.session_state.get(f"tb_map_{fk}", "")) for fk in TB_MAP_FIELD_KEYS
            )
            map_sig = hashlib.sha256(map_parts.encode()).hexdigest()[:24]
            need_preview_refresh = (
                sig != st.session_state.get("tb_csv_sig")
                or map_sig != st.session_state.get("tb_csv_map_sig")
            )
            if need_preview_refresh:
                st.session_state.pop("tb_prev_coa_labels", None)
                st.session_state.pop("tb_prev_coa_sig", None)
                st.session_state.pop("tb_prev_coa_map_sig", None)
                for _k in (
                    "tb_coa_pending_add_row",
                    "tb_coa_pending_full_name",
                    "tb_coa_pending_revert_coa",
                ):
                    st.session_state.pop(_k, None)
                st.session_state["tb_csv_sig"] = sig
                st.session_state["tb_csv_map_sig"] = map_sig
                preview, totals = build_tb_preview_from_csv(parsed, merged_coa)
                st.session_state["tb_csv_totals"] = totals
                opts = _coa_option_labels(merged_coa)
                im_ex = _unique_import_coa_labels(preview, opts)
                st.session_state["tb_coa_import_extras"] = im_ex
                tb_df, type_csv_list = _tb_preview_to_dataframe(
                    preview, merged_coa, opts, im_ex
                )
                st.session_state["tb_csv_df"] = tb_df
                st.session_state["tb_csv_type_from_file"] = type_csv_list
            TRIAL_BALANCE_TOTALS = st.session_state["tb_csv_totals"]
            tb_csv_mode = True
            TRIAL_BALANCE_IMPORT_PREVIEW = []
        else:
            for k in (
                "tb_csv_sig",
                "tb_csv_df",
                "tb_csv_totals",
                "tb_custom_coa",
                "tb_prev_coa_labels",
                "tb_prev_coa_sig",
                "tb_prev_coa_map_sig",
                "tb_coa_pending_add_row",
                "tb_coa_pending_full_name",
                "tb_coa_pending_revert_coa",
                "tb_csv_hdr_sig",
                "tb_csv_map_sig",
                "tb_coa_import_extras",
                "tb_csv_type_from_file",
            ):
                st.session_state.pop(k, None)
            TRIAL_BALANCE_IMPORT_PREVIEW = []
            TRIAL_BALANCE_TOTALS = _empty_tb_totals()
            if map_err:
                tb_parse_note = map_err
            elif header_idx is None:
                tb_parse_note = "Could not detect a usable header or data in this file."
            else:
                tb_parse_note = "No data rows with non-zero debit or credit for this mapping."
    elif st.session_state.get("tb_import_cleared") and use_sample_data():
        TRIAL_BALANCE_IMPORT_PREVIEW = []
        TRIAL_BALANCE_TOTALS = _empty_tb_totals()
    else:
        TRIAL_BALANCE_IMPORT_PREVIEW, TRIAL_BALANCE_TOTALS = trial_balance_import()

    total_deb = TRIAL_BALANCE_TOTALS["total_debits"]
    total_crd = TRIAL_BALANCE_TOTALS["total_credits"]
    is_balanced = TRIAL_BALANCE_TOTALS["is_balanced"]
    if tb_csv_mode:
        n_preview = len(st.session_state["tb_csv_df"])
    else:
        n_preview = len(TRIAL_BALANCE_IMPORT_PREVIEW)

    csv_confirm_ok = True
    can_confirm = is_balanced and n_preview > 0

    balanced_badge = (
        '<span style="background:#bcf0ae;color:#154212;font-size:0.65rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.1em;padding:0.25rem 0.75rem;'
        'border-radius:0.75rem;">● Balanced</span>'
        if is_balanced else
        '<span style="background:#ffdad8;color:#71151d;font-size:0.65rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.1em;padding:0.25rem 0.75rem;'
        'border-radius:0.75rem;">● Unbalanced</span>'
    )

    _fn = st.session_state.get("tb_file_name") or "your CSV"
    _fn_esc = html.escape(_fn)
    if tb_parse_note:
        preview_caption = html.escape(tb_parse_note)
    elif n_preview == 0:
        preview_caption = "No rows loaded yet. Upload a CSV or load data into the database."
    else:
        preview_caption = f"Displaying {n_preview} entries from {_fn_esc}"

    st.html(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                margin-bottom:0.75rem;">
        <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:1.1rem;margin:0;">
            Import Preview
        </h4>
        {balanced_badge}
    </div>
    <p style="font-size:0.7rem;color:#636262;margin-bottom:1rem;">
        {preview_caption}
    </p>
    """)

    if tb_csv_mode and tb_parse_used_legacy:
        st.info(
            "This file is being read using the classic Full name + Debit + Credit layout. "
            "Column mapping for chart-of-account columns does not apply to this parse; adjust "
            "your CSV or mapping if you use separate header columns."
        )

    if tb_csv_mode:
        merged_coa = _merge_coa_rows(
            chart_of_accounts(),
            st.session_state.get("tb_custom_coa", []),
        )
        real_labels = _coa_option_labels(merged_coa)
        coa_select_opts = _coa_select_options(
            real_labels, st.session_state.get("tb_coa_import_extras")
        )
        sig = st.session_state["tb_csv_sig"]
        csv_map_sig = st.session_state.get("tb_csv_map_sig") or ""
        # Include mapping in the editor key so a new map does not reuse stale data_editor
        # state for the same file (Streamlit keeps widget state per key).
        sig_key = f"{sig[:24]}_{csv_map_sig[:24]}"

        saved_tb_df = st.session_state["tb_csv_df"].copy()
        csv_types_row = _tb_csv_types_aligned(len(saved_tb_df))
        df_edit = _ensure_coa_column_matches_options(
            saved_tb_df,
            coa_select_opts,
        )
        pr_pin = st.session_state.get("tb_coa_pending_add_row")
        if pr_pin is not None and 0 <= pr_pin < len(df_edit):
            df_edit = df_edit.copy()
            df_edit.iloc[pr_pin, df_edit.columns.get_loc("COA")] = COA_ADD_NEW_LABEL
        df_edit["Type"] = _tb_type_series(df_edit, merged_coa, csv_types_row)
        coa_col_cfg = st.column_config.SelectboxColumn(
            "Acct #",
            options=coa_select_opts,
            required=True,
        )
        edited = st.data_editor(
            df_edit,
            column_config={
                "Full name": st.column_config.TextColumn("Account line"),
                "COA": coa_col_cfg,
                "Type": st.column_config.TextColumn("Type"),
                "Match": st.column_config.TextColumn("Match"),
                "Debits": st.column_config.NumberColumn(
                    "Debits",
                    format="%.2f",
                ),
                "Credits": st.column_config.NumberColumn(
                    "Credits",
                    format="%.2f",
                ),
            },
            disabled=["Full name", "Type", "Match", "Debits", "Credits"],
            hide_index=True,
            width="stretch",
            key=f"tb_coa_editor_{sig_key}",
        )
        curr = edited["COA"].tolist()
        prev_sig = st.session_state.get("tb_prev_coa_sig")
        prev_labels = st.session_state.get("tb_prev_coa_labels")
        prev_map = st.session_state.get("tb_prev_coa_map_sig")
        init_snapshot = (
            prev_labels is None
            or prev_sig != sig
            or prev_map != csv_map_sig
            or len(prev_labels) != len(curr)
        )

        pr_stale = st.session_state.get("tb_coa_pending_add_row")
        if pr_stale is not None:
            out_of_range = pr_stale < 0 or pr_stale >= len(curr)
            c_stale = curr[pr_stale] if not out_of_range else None
            picked_other = (
                not out_of_range
                and not _coa_cell_is_add_new(c_stale)
                and not _is_blank_coa_cell(c_stale)
            )
            if out_of_range or picked_other:
                for _k in (
                    "tb_coa_pending_add_row",
                    "tb_coa_pending_full_name",
                    "tb_coa_pending_revert_coa",
                ):
                    st.session_state.pop(_k, None)

        for i, c in enumerate(curr):
            if not _coa_cell_is_add_new(c):
                continue
            transitioned = init_snapshot or (
                prev_labels is not None
                and i < len(prev_labels)
                and not _coa_cell_is_add_new(prev_labels[i])
            )
            if not transitioned:
                continue
            st.session_state["tb_coa_pending_add_row"] = i
            st.session_state["tb_coa_pending_full_name"] = (
                str(edited.iloc[i]["Full name"]).strip() or "Account"
            )
            if prev_labels is not None and i < len(prev_labels):
                st.session_state["tb_coa_pending_revert_coa"] = prev_labels[i]
            else:
                st.session_state["tb_coa_pending_revert_coa"] = COA_UNMAPPED_LABEL
            break

        df_work = edited.copy()
        coa_loc = df_work.columns.get_loc("COA")
        pr_active = st.session_state.get("tb_coa_pending_add_row")
        if pr_active is not None and 0 <= pr_active < len(df_work):
            df_work = df_work.copy()
            df_work.iloc[pr_active, coa_loc] = COA_ADD_NEW_LABEL

        out = _ensure_coa_column_matches_options(
            df_work,
            coa_select_opts,
            prev_df=saved_tb_df,
        )
        out["Type"] = _tb_type_series(out, merged_coa, csv_types_row)
        st.session_state["tb_csv_df"] = out
        st.session_state["tb_prev_coa_labels"] = out["COA"].tolist()
        st.session_state["tb_prev_coa_sig"] = sig
        st.session_state["tb_prev_coa_map_sig"] = csv_map_sig

        pr_form = st.session_state.get("tb_coa_pending_add_row")
        if pr_form is not None and 0 <= pr_form < len(out):
            fn_pending = st.session_state.get("tb_coa_pending_full_name") or (
                str(out.iloc[pr_form]["Full name"]).strip() or "Account"
            )
            merged_suggest = _merge_coa_rows(
                chart_of_accounts(),
                st.session_state.get("tb_custom_coa", []),
            )
            suggested_num = _suggest_next_coa_number(merged_suggest)
            st.markdown("##### New chart account")
            st.caption(
                f"Import line: {fn_pending} — account name will match this line. "
                "Enter the account number (or keep the suggestion), then click Create account."
            )
            acct_num_in = st.text_input(
                "Account number",
                value=suggested_num,
                key=f"tb_pending_acct_num_{sig_key}_{pr_form}",
                label_visibility="visible",
            )
            b_create, b_cancel = st.columns(2)
            with b_create:
                if st.button("Create account", key=f"tb_pending_create_{sig_key}"):
                    num = (acct_num_in or "").strip() or suggested_num
                    if not num.isdigit():
                        st.error("Enter a numeric account number (e.g. 1010).")
                    else:
                        custom = list(st.session_state.get("tb_custom_coa", []))
                        custom = [
                            c
                            for c in custom
                            if str(c.get("number", "")).strip() != num
                        ]
                        custom.append(
                            {
                                "number": num,
                                "name": fn_pending,
                                "type": "Asset",
                            }
                        )
                        st.session_state["tb_custom_coa"] = custom
                        df_fix = st.session_state["tb_csv_df"].copy()
                        df_fix.iloc[pr_form, df_fix.columns.get_loc("COA")] = num
                        merged_new = _merge_coa_rows(chart_of_accounts(), custom)
                        tcsv = _tb_csv_types_aligned(len(df_fix))
                        df_fix["Type"] = _tb_type_series(df_fix, merged_new, tcsv)
                        st.session_state["tb_csv_df"] = df_fix
                        st.session_state["tb_prev_coa_labels"] = df_fix[
                            "COA"
                        ].tolist()
                        for _k in (
                            "tb_coa_pending_add_row",
                            "tb_coa_pending_full_name",
                            "tb_coa_pending_revert_coa",
                        ):
                            st.session_state.pop(_k, None)
                        st.rerun()
            with b_cancel:
                if st.button("Cancel", key=f"tb_pending_cancel_{sig_key}"):
                    rev = st.session_state.pop("tb_coa_pending_revert_coa", None)
                    pr_c = st.session_state.pop("tb_coa_pending_add_row", None)
                    st.session_state.pop("tb_coa_pending_full_name", None)
                    if (
                        rev is not None
                        and pr_c is not None
                        and 0 <= pr_c < len(st.session_state["tb_csv_df"])
                    ):
                        df_rev = st.session_state["tb_csv_df"].copy()
                        m2 = _merge_coa_rows(
                            chart_of_accounts(),
                            st.session_state.get("tb_custom_coa", []),
                        )
                        rl2 = _coa_option_labels(m2)
                        opt2 = _coa_select_options(
                            rl2, st.session_state.get("tb_coa_import_extras")
                        )
                        df_rev.iloc[pr_c, df_rev.columns.get_loc("COA")] = rev
                        df_done = _ensure_coa_column_matches_options(df_rev, opt2)
                        tcsv2 = _tb_csv_types_aligned(len(df_done))
                        df_done["Type"] = _tb_type_series(df_done, m2, tcsv2)
                        st.session_state["tb_csv_df"] = df_done
                        st.session_state["tb_prev_coa_labels"] = df_done[
                            "COA"
                        ].tolist()
                    st.rerun()

        merged_coa = _merge_coa_rows(
            chart_of_accounts(),
            st.session_state.get("tb_custom_coa", []),
        )
        csv_confirm_ok = _tb_preview_rows_coa_ready(st.session_state["tb_csv_df"])
        can_confirm = is_balanced and n_preview > 0 and csv_confirm_ok

        if n_preview > 0 and not csv_confirm_ok:
            st.warning(
                "Choose an **Acct #** for every row (a number from your file or from the chart). "
                "Use **Add new account…** only when you intend to create that row on the chart, "
                "then complete the form below the table. Confirm stays disabled while any row is "
                "still on Add new or **Select COA**."
            )

        if n_preview > 0:
            _lines = (
                st.session_state["tb_csv_df"]["Full name"]
                .dropna()
                .astype(str)
                .str.strip()
            )
            _distinct = [x for x in _lines.unique() if x]
            if _distinct and all(_looks_like_tb_import_account_line_label(u) for u in _distinct):
                st.warning(
                    "Every **Account line** looks like the book placeholder (**TB-IMPORT**). That usually "
                    "means the wrong CSV column is mapped to **Chart of Account (number)** or "
                    "**Chart of Account (name)**. Map the columns that describe each row’s account "
                    "(e.g. account number and title from your file), not a fixed book label."
                )

        if n_preview > 0:
            baa = bank_accounts_for_tb_mapping()
            if baa:
                with st.expander(
                    "Map account lines to bank accounts (Ledger opening balance)",
                    expanded=True,
                ):
                    st.caption(
                        "For each distinct **Account line**, choose a registered bank account. "
                        "The Ledger opening balance uses the net of mapped lines (debits minus credits) "
                        "per account. Choose **Book only** to keep those lines on the TB import book "
                        "(no effect on a real bank account)."
                    )
                    distinct_fn = (
                        st.session_state["tb_csv_df"]["Full name"]
                        .dropna()
                        .astype(str)
                        .str.strip()
                    )
                    seen: list[str] = []
                    labels = ["— Book only (TB-IMPORT) —"] + [
                        f"{a['account_name']} ****{a['account_number_masked']}" for a in baa
                    ]
                    for fn in distinct_fn:
                        fn = str(fn).strip()
                        if not fn or fn in seen:
                            continue
                        seen.append(fn)
                        h = hashlib.md5(fn.encode("utf-8")).hexdigest()[:16]
                        key = f"tb_bank_map_{h}"
                        st.selectbox(
                            f"Account line: {fn[:120]}",
                            options=list(range(len(labels))),
                            format_func=lambda i, lb=labels: lb[i],
                            key=key,
                        )
            elif not use_sample_data():
                st.info(
                    "Add at least one **checking, savings, or credit card** under **Bank Accounts** to "
                    "map trial balance lines here. Until then, lines save only to the book-only import "
                    "account (**TB-IMPORT**), and the Ledger opening-balance seed does not apply to "
                    "named bank accounts."
                )
    else:
        rows_html = ""
        for row in TRIAL_BALANCE_IMPORT_PREVIEW:
            deb_str = f"${row['debits']:,.2f}" if row["debits"] else "—"
            crd_str = f"${row['credits']:,.2f}" if row["credits"] else "—"

            if row["error"]:
                row_style = "background:#fff0f0;"
                bank_style = "color:#ba1a1a;font-weight:700;"
                coa_style = "color:#ba1a1a;"
            else:
                row_style = "background:#ffffff;"
                bank_style = "font-size:0.8rem;"
                coa_style = "color:#636262;font-size:0.8rem;"

            ms = row.get("match_score")
            if ms is not None:
                match_str = f"{int(round(float(ms) * 100))}%"
            else:
                match_str = "—"
            type_str = row.get("account_type") or "—"
            bank_esc = html.escape(str(row["bank_account"]))
            coa_esc = html.escape(str(row["coa"]))
            type_esc = html.escape(str(type_str))
            match_esc = html.escape(match_str)

            rows_html += f"""
            <tr style="{row_style}">
                <td style="padding:0.75rem 0.75rem;{bank_style}font-size:0.75rem;">
                    {bank_esc}
                </td>
                <td style="padding:0.75rem 0.75rem;{coa_style}">{coa_esc}</td>
                <td style="padding:0.75rem 0.75rem;font-size:0.75rem;color:#636262;">{type_esc}</td>
                <td style="padding:0.75rem 0.75rem;font-size:0.75rem;text-align:right;color:#636262;">
                    {match_esc}
                </td>
                <td style="padding:0.75rem 0.75rem;text-align:right;font-size:0.8rem;">
                    {deb_str}
                </td>
                <td style="padding:0.75rem 0.75rem;text-align:right;font-size:0.8rem;">
                    {crd_str}
                </td>
            </tr>"""

        st.html(f"""
        <div style="background:#ffffff;border-radius:0.5rem;overflow:hidden;
                    border:1px solid rgba(194,201,187,0.2);">
            <table style="width:100%;border-collapse:collapse;font-size:0.8rem;">
                <thead>
                    <tr style="background:#f3f3f3;">
                        <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                                   text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                            Account line
                        </th>
                        <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                                   text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                            Suggested COA
                        </th>
                        <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                                   text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                            Type
                        </th>
                        <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                                   text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                            Match
                        </th>
                        <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                                   text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                            Debits
                        </th>
                        <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                                   text-transform:uppercase;letter-spacing:0.1em;color:#636262;">
                            Credits
                        </th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        """)

    # Balance totals
    st.html("<div style='height:1rem'></div>")
    st.html(f"""
    <div style="background:#f3f3f3;border-radius:0.125rem;padding:1.25rem 1.5rem;
                display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                     letter-spacing:0.1em;color:#636262;">Balance Totals</span>
        <div style="display:flex;gap:3rem;">
            <div style="text-align:right;">
                <div style="font-size:0.6rem;color:#636262;font-weight:700;
                            text-transform:uppercase;margin-bottom:0.25rem;">Total Debits</div>
                <div style="font-size:1.25rem;font-weight:700;font-family:'Manrope',sans-serif;">
                    ${total_deb:,.2f}
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.6rem;color:#636262;font-weight:700;
                            text-transform:uppercase;margin-bottom:0.25rem;">Total Credits</div>
                <div style="font-size:1.25rem;font-weight:700;font-family:'Manrope',sans-serif;">
                    ${total_crd:,.2f}
                </div>
            </div>
        </div>
    </div>
    """)

    st.html("<div style='height:1rem'></div>")

    if is_balanced and n_preview > 0:
        st.html("""
        <div style="display:flex;align-items:center;gap:0.75rem;padding:1rem;
                    background:#f0fdf4;border-radius:0.25rem;margin-bottom:1rem;">
            <span class="material-symbols-outlined" style="color:#154212;">check_circle</span>
            <div>
                <div style="font-weight:700;font-size:0.875rem;color:#154212;">
                    Trial Balance is Balanced
                </div>
                <div style="font-size:0.7rem;color:#636262;">
                    Variance $0.00 — Ready for ledger entry!
                </div>
            </div>
        </div>
        """)

    col_discard, col_confirm = st.columns([1, 2], gap="small")
    with col_discard:
        if st.button("Discard", key="discard_tb"):
            st.session_state["tb_discard_confirm"] = True
            st.rerun()
    with col_confirm:
        if st.button(
            "Confirm & Save Entry →",
            key="confirm_tb",
            type="primary",
            disabled=not can_confirm,
        ):
            ref = (st.session_state.get("tb_ref_name") or "").strip()
            if not ref:
                st.warning("Enter a balance reference name before saving.")
            else:
                if tb_csv_mode and use_sample_data():
                    records = st.session_state["tb_csv_df"].to_dict("records")
                    path_tb = export_trial_balance_grid_csv(records, ref)
                    path_coa = export_chart_of_accounts_csv(chart_of_accounts())
                    st.warning(
                        "Demo mode is on (USE_SAMPLE_DATA=true). Nothing is written to PostgreSQL."
                    )
                    st.success(
                        f"Exported **trial balance** → `{path_tb}` and **chart of accounts** → "
                        f"`{path_coa}` (under `app/exports/`)."
                    )
                elif tb_csv_mode:
                    records = st.session_state["tb_csv_df"].to_dict("records")
                    n_mapped = _apply_tb_bank_mapping_to_records(records)
                    n = save_trial_balance_csv_to_db(ref, records)
                    path_tb = export_trial_balance_grid_csv(records, ref)
                    path_coa = export_chart_of_accounts_csv(chart_of_accounts())
                    extra = ""
                    if n_mapped:
                        extra = (
                            f" **{n_mapped}** line(s) mapped to bank accounts; "
                            "Ledger opening balances were seeded from the trial balance."
                        )
                    st.success(
                        f"Saved **{n}** trial balance line(s) to PostgreSQL (chart + "
                        f"`trial_balance_entries`).{extra} CSV snapshots: `{path_tb.name}` and "
                        f"`{path_coa.name}` in `app/exports/`."
                    )
                else:
                    records = [
                        {
                            "Full name": r.get("bank_account", ""),
                            "COA": r.get("coa", ""),
                            "Type": r.get("account_type", ""),
                            "Match": "—",
                            "Debits": float(r["debits"])
                            if r.get("debits") is not None
                            else 0.0,
                            "Credits": float(r["credits"])
                            if r.get("credits") is not None
                            else 0.0,
                        }
                        for r in TRIAL_BALANCE_IMPORT_PREVIEW
                    ]
                    if records:
                        path_tb = export_trial_balance_grid_csv(records, ref)
                        path_coa = export_chart_of_accounts_csv(chart_of_accounts())
                        st.success(
                            f"Exported **trial balance** → `{path_tb.name}` and **chart** → "
                            f"`{path_coa.name}` under `app/exports/`."
                        )
                    else:
                        st.success("Trial balance confirmed.")
                st.switch_page("pages/4_Bank_Statement_Template.py")

# ── Accounting standards ───────────────────────────────────────────────────────
st.html("""
<div style="margin-top:3rem;display:flex;gap:3rem;align-items:center;
            padding:2rem;background:#f9f9f9;border-radius:0.5rem;">
    <div style="flex:1;">
        <p style="font-size:0.7rem;font-style:italic;color:#636262;line-height:1.6;margin:0;">
            <span style="font-size:0.6rem;font-weight:800;text-transform:uppercase;
                         letter-spacing:0.1em;color:#636262;display:block;margin-bottom:0.5rem;">
                Accounting Standards
            </span>
            "A Trial Balance is the pulse of your atelier. By ensuring every debit meets its
            credit, we create a symmetry that reflects the true health of your creative enterprise."
        </p>
    </div>
    <div style="flex:1;text-align:right;">
        <p style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;
                  color:#636262;">
            Encrypted 256-bit Secure Transfer<br/>
            Compliant with Digital Atelier Financial Protocol V5
        </p>
    </div>
</div>
""")
