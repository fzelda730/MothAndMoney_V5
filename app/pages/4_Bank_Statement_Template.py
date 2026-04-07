from __future__ import annotations

import hashlib
import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import load_css, render_sidebar
from components.topbar import render_topbar
from data.bank_statement_csv import (
    BANK_COLUMN_NOT_USED,
    BANK_MAP_FIELD_KEYS,
    bank_statement_csv_headers_from_bytes,
    build_bank_statement_preview_rows,
    suggest_bank_column_mapping,
    unique_payee_candidates_from_bytes,
)
from data.providers import (
    chart_of_accounts,
    db_ready,
    import_templates,
    payee_rules_for_template,
    persist_payee_rule,
    save_bank_statement_template_to_db,
)
from db.connection import use_sample_data

COA_SKIP_LABEL = "— Skip (no rule) —"
DEMO_PAYEE_RULES_KEY = "bank_payee_demo_rules"


def _payee_rule_widget_key(tpl_id: str, csv_sig: str, norm: str) -> str:
    h = hashlib.sha256(f"{tpl_id}|{csv_sig}|{norm}".encode()).hexdigest()[:16]
    return f"bank_payee_coa_{h}"

st.set_page_config(
    page_title="Bank Statement Template | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("onboarding")
render_topbar()

if not db_ready():
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
st.html("""
<div style="font-size:0.65rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;margin-bottom:0.5rem;">
    Configuration › Template Studio
</div>
<h1 class="mm-page-title" style="font-size:2rem;margin-bottom:0.25rem;">
    Moth and Money <strong style="color:#154212;">V5</strong>
</h1>
<p class="mm-page-description" style="margin-bottom:2.5rem;">
    Design a persistent blueprint for your bank statements. Map column data once and maintain
    consistent financial clarity for your digital atelier.
</p>
""")

col_left, col_right = st.columns([1, 1.2], gap="large")

bank_hdr_list: list[str] = []
bank_hdr_idx = 0
bank_raw: bytes | None = None

# ── Left: Template Identity + Upload + Column Mapping ─────────────────────────
with col_left:
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.25rem;">Template Identity</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1rem;">
        Provide a descriptive name for your template to reuse it across monthly
        reconciled statements.
    </p>
    """)

    st.html('<label class="mm-settings-label">Template Name</label>')
    st.text_input(
        "bank_tmpl_name",
        placeholder="e.g. Chase Business Checking",
        label_visibility="collapsed",
        key="bank_tmpl_name",
    )

    st.html("<div style='height:1.5rem'></div>")

    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.25rem;">Upload Preview</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1rem;">
        Upload a sample .csv file to identify available columns for the mapping process.
    </p>
    """)

    uploaded = st.file_uploader(
        "Select a sample statement",
        type=["csv"],
        help="Accepts CSV files. Top up to 10MB.",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        st.success(f"Loaded: {uploaded.name}")
        bank_raw = uploaded.getvalue()
        bank_hdr_list, bank_hdr_idx = bank_statement_csv_headers_from_bytes(bank_raw)
        hsig = hashlib.sha256(bank_raw).hexdigest()[:28]
        if st.session_state.get("bank_csv_hdr_sig") != hsig:
            st.session_state["bank_csv_hdr_sig"] = hsig
            for fk in BANK_MAP_FIELD_KEYS:
                st.session_state.pop(f"tpl_bank_{fk}", None)
            if bank_hdr_list:
                sugg = suggest_bank_column_mapping(bank_hdr_list)
                for fk in BANK_MAP_FIELD_KEYS:
                    pick = sugg.get(fk)
                    if pick and pick in bank_hdr_list:
                        st.session_state[f"tpl_bank_{fk}"] = pick
                    else:
                        st.session_state[f"tpl_bank_{fk}"] = BANK_COLUMN_NOT_USED
            else:
                for fk in BANK_MAP_FIELD_KEYS:
                    st.session_state[f"tpl_bank_{fk}"] = BANK_COLUMN_NOT_USED
    else:
        st.session_state.pop("bank_csv_hdr_sig", None)

    st.html("<div style='height:1.5rem'></div>")

    # ── Column Mapping ────────────────────────────────────────────────────────
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.5rem;">Column Mapping</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1.25rem;">
        Select the corresponding columns from your file to match the Atelier's system requirements.
    </p>
    """)

    BANK_TEMPLATE_FIELDS = [
        ("📅", "date", "Date"),
        ("🔄", "transaction_type", "Transaction Type"),
        ("👤", "payee", "Payee"),
        ("💰", "amount", "Amount"),
        ("📋", "chart_of_account", "Chart of Account"),
        ("📝", "description", "Description"),
    ]

    if uploaded is None:
        st.caption("Upload a CSV to see its column headings here.")
    elif not bank_hdr_list:
        st.caption(
            "Could not detect a header row. Ensure the first non-empty row contains column titles."
        )
    else:
        st.caption(
            "Each dropdown lists columns from your file. Use “Not used” for fields your file omits."
        )
        opts = [BANK_COLUMN_NOT_USED] + bank_hdr_list
        for emoji, map_key, field in BANK_TEMPLATE_FIELDS:
            col_icon, col_label, col_select = st.columns([0.3, 1.2, 2], gap="small")
            with col_icon:
                st.html(f"<div style='padding-top:0.6rem;font-size:1.1rem;'>{emoji}</div>")
            with col_label:
                st.html(
                    f"<div style='padding-top:0.7rem;font-size:0.8rem;font-weight:600;"
                    f"color:#1a1c1c;'>{field}</div>"
                )
            with col_select:
                sk = f"tpl_bank_{map_key}"
                if sk not in st.session_state or st.session_state[sk] not in opts:
                    st.session_state[sk] = BANK_COLUMN_NOT_USED
                st.selectbox(
                    f"bank_map_{field}",
                    opts,
                    label_visibility="collapsed",
                    key=sk,
                )

    # ── Payee Intelligence (inline) ───────────────────────────────────────────
    st.html("<div style='height:1rem'></div>")
    with st.expander("✨ Payee Intelligence — Auto-categorize vendors", expanded=False):
        bank_tmpls = [t for t in import_templates() if t.get("type") == "bank_statement"]
        if bank_tmpls:
            id_to_name = {t["id"]: t.get("name") or t["id"] for t in bank_tmpls}
            tpl_ids = [t["id"] for t in bank_tmpls]
            preferred = st.session_state.get("bank_stmt_template_id")
            if preferred in tpl_ids and "bank_payee_tpl_pick" not in st.session_state:
                st.session_state["bank_payee_tpl_pick"] = preferred
            tpl_sel = st.selectbox(
                "Payee rules apply to this template",
                options=tpl_ids,
                format_func=lambda i, m=id_to_name: m.get(i, i),
                key="bank_payee_tpl_pick",
            )
        else:
            tpl_sel = (st.session_state.get("bank_stmt_template_id") or "").strip()
            st.caption(
                "Save a bank statement template using the button below, then reopen this page "
                "to pick it here—or your last saved template id will be used if present."
            )

        csv_sig = st.session_state.get("bank_csv_hdr_sig") or "no_csv"
        column_map_pi = {
            fk: st.session_state.get(f"tpl_bank_{fk}", BANK_COLUMN_NOT_USED)
            for fk in BANK_MAP_FIELD_KEYS
        }
        pay_col = column_map_pi.get("payee")
        desc_col = column_map_pi.get("description")
        if pay_col == BANK_COLUMN_NOT_USED and desc_col == BANK_COLUMN_NOT_USED:
            st.caption("Map Payee or Description in Column Mapping to discover payee text from your CSV.")
        elif bank_raw is None or not bank_hdr_list:
            st.caption("Upload a CSV to list distinct payees from your file (up to 100, first 200 rows).")
        else:
            candidates = unique_payee_candidates_from_bytes(
                bank_raw,
                bank_hdr_list,
                bank_hdr_idx,
                column_map_pi,
                BANK_COLUMN_NOT_USED,
            )
            if not candidates:
                st.caption("No payee or description values found in the scanned rows.")
            else:
                if use_sample_data():
                    st.caption(
                        "Demo mode: rules are kept in this session only (not PostgreSQL). "
                        "They are still used if you add a bank import that calls the resolver."
                    )
                else:
                    st.caption(
                        "Choose a chart account per payee. Patterns are stored normalized (case/spacing-insensitive). "
                        "Skip removes a saved rule for that payee."
                    )

                coa_rows = chart_of_accounts()
                coa_labels = [COA_SKIP_LABEL]
                coa_ids: list[str | None] = [None]
                for r in coa_rows:
                    cid = (r.get("id") or "").strip()
                    if not cid:
                        continue
                    coa_labels.append(f'{r["number"]} - {r["name"]}')
                    coa_ids.append(cid)

                if use_sample_data():
                    rules_map: dict[str, str] = (
                        st.session_state.get(DEMO_PAYEE_RULES_KEY, {}).get(tpl_sel, {}) or {}
                    )
                else:
                    rules_map = {
                        r["payee_pattern"]: r["coa_id"]
                        for r in payee_rules_for_template(tpl_sel)
                    }

                for display, norm in candidates:
                    sk = _payee_rule_widget_key(tpl_sel or "none", csv_sig, norm)
                    if sk not in st.session_state:
                        cid_existing = rules_map.get(norm)
                        default_i = 0
                        if cid_existing and cid_existing in coa_ids:
                            default_i = coa_ids.index(cid_existing)
                        st.session_state[sk] = default_i
                    st.selectbox(
                        display[:120],
                        options=list(range(len(coa_labels))),
                        format_func=lambda i, labels=coa_labels: labels[i],
                        key=sk,
                        label_visibility="visible",
                    )

                if st.button("Save payee rules", key="bank_save_payee_rules"):
                    if not (tpl_sel or "").strip():
                        st.warning("Select or save a bank template before saving payee rules.")
                    else:
                        n_ok = 0
                        tpl_key = tpl_sel or "none"
                        for _display, norm in candidates:
                            sk = _payee_rule_widget_key(tpl_key, csv_sig, norm)
                            idx = int(st.session_state.get(sk, 0))
                            if idx < 0 or idx >= len(coa_ids):
                                idx = 0
                            chosen = coa_ids[idx]
                            if use_sample_data():
                                all_d = st.session_state.setdefault(DEMO_PAYEE_RULES_KEY, {})
                                bucket = all_d.setdefault(tpl_sel, {})
                                if chosen:
                                    bucket[norm] = chosen
                                    n_ok += 1
                                else:
                                    bucket.pop(norm, None)
                            else:
                                persist_payee_rule(tpl_sel, norm, chosen)
                        if use_sample_data():
                            st.success(
                                f"Payee rules updated in session (demo): {n_ok} with a COA, "
                                "others skipped or cleared."
                            )
                        else:
                            st.success("Payee rules saved to the database.")

# ── Right: Live Preview ───────────────────────────────────────────────────────
with col_right:
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.5rem;">Live Preview</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1.25rem;">
        Verification of the first 3 rows of your statement using the current mapping.
    </p>
    """)

    if use_sample_data():
        st.info(
            "Demo mode: the preview reflects your uploaded CSV only; saving does not write to PostgreSQL."
        )

    preview_rows_html = ""
    if bank_raw is not None and bank_hdr_list:
        column_map = {
            fk: st.session_state.get(f"tpl_bank_{fk}", BANK_COLUMN_NOT_USED)
            for fk in BANK_MAP_FIELD_KEYS
        }
        preview_data = build_bank_statement_preview_rows(
            bank_raw,
            bank_hdr_list,
            bank_hdr_idx,
            column_map,
            BANK_COLUMN_NOT_USED,
            max_rows=3,
        )
        for row in preview_data:
            type_color = "#154212" if row["type"] == "CREDIT" else "#71151d"
            type_bg = "#bcf0ae" if row["type"] == "CREDIT" else "#ffdad8"
            amt_color = "#154212" if row["amount"] >= 0 else "#71151d"
            d = html.escape(str(row["date"]))
            t = html.escape(str(row["type"]))
            p = html.escape(str(row["payee"]))
            c = html.escape(str(row["coa"]))
            preview_rows_html += f"""
        <tr style="background:#ffffff;">
            <td style="padding:0.75rem;font-size:0.75rem;color:#636262;">{d}</td>
            <td style="padding:0.75rem;">
                <span style="background:{type_bg};color:{type_color};font-size:0.6rem;
                             font-weight:700;padding:0.125rem 0.5rem;border-radius:0.75rem;">
                    {t}
                </span>
            </td>
            <td style="padding:0.75rem;font-size:0.8rem;font-weight:600;">{p}</td>
            <td style="padding:0.75rem;text-align:right;font-size:0.8rem;color:{amt_color};
                       font-weight:600;">${abs(row['amount']):,.2f}</td>
            <td style="padding:0.75rem;font-size:0.75rem;color:#636262;">{c}</td>
        </tr>"""
    elif uploaded is None:
        st.caption("Upload a CSV to populate the preview.")
    else:
        st.caption("No data rows to show yet, or headers could not be read.")

    st.html(f"""
    <div style="background:#ffffff;border-radius:0.5rem;overflow:hidden;
                border:1px solid rgba(194,201,187,0.2);">
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#f3f3f3;">
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Date</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Type</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Payee</th>
                    <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Amount</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">COA</th>
                </tr>
            </thead>
            <tbody>{preview_rows_html or ""}</tbody>
        </table>
    </div>
    """)

st.html("<div style='height:2rem'></div>")

# ── Actions ───────────────────────────────────────────────────────────────────
col_cancel, col_spacer, col_save = st.columns([1, 3, 1], gap="small")
with col_cancel:
    if st.button("Cancel", key="bank_cancel"):
        st.switch_page("pages/2_Onboarding.py")
with col_save:
    if st.button("💾 Save Template", key="bank_save", type="primary"):
        name = (st.session_state.get("bank_tmpl_name") or "").strip()
        if not name:
            st.warning("Enter a template name before saving.")
        else:
            if use_sample_data():
                st.warning(
                    "Demo mode (USE_SAMPLE_DATA=true): the template is not stored in PostgreSQL. "
                    "Set USE_SAMPLE_DATA=false in app/.env to save to the database."
                )
            else:
                column_map = {
                    k: st.session_state.get(f"tpl_bank_{k}") or BANK_COLUMN_NOT_USED
                    for k in (
                        "date",
                        "transaction_type",
                        "payee",
                        "amount",
                        "chart_of_account",
                        "description",
                    )
                }
                new_id = save_bank_statement_template_to_db(name, column_map)
                if new_id:
                    st.session_state["bank_stmt_template_id"] = new_id
                    st.session_state["bank_payee_tpl_pick"] = new_id
                st.success("Bank statement template saved to the database.")
            st.switch_page("pages/5_Credit_Card_Config.py")
