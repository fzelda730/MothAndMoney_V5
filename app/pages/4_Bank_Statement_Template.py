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
    bank_statement_headers_from_grid,
    build_bank_statement_preview_rows,
    suggest_bank_column_mapping,
)
from data.ledger_statement_import import extract_statement_grid_from_pdf
from data.providers import (
    bank_import_template_by_id,
    db_ready,
    import_templates,
    save_bank_statement_template_to_db,
    update_bank_statement_template_in_db,
)
from db.connection import use_sample_data

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

bank_tmpls_bs = [t for t in import_templates() if t.get("type") == "bank_statement"]
tpl_id_options = [""] + [t["id"] for t in bank_tmpls_bs]
tpl_id_label = {t["id"]: f'{t.get("name") or t["id"]}' for t in bank_tmpls_bs}

# ── Left: Template Identity + Upload + Column Mapping ─────────────────────────
with col_left:
    st.html("""
    <h4 style="font-family:'Manrope',sans-serif;font-weight:700;font-size:0.95rem;
               margin-bottom:0.25rem;">Template Identity</h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1rem;">
        Choose an existing bank template to view and edit, or start a new one. Name and column
        mapping apply to the selected template when you save.
    </p>
    """)

    st.html('<label class="mm-settings-label">Saved template</label>')
    tpl_sel = st.selectbox(
        "bank_tpl_selector",
        options=tpl_id_options,
        format_func=lambda x: "— New template —" if x == "" else tpl_id_label.get(x, x),
        label_visibility="collapsed",
        key="bank_tpl_selector",
    )

    if tpl_sel != st.session_state.get("_bank_tpl_synced_selector"):
        st.session_state["_bank_tpl_synced_selector"] = tpl_sel
        if not tpl_sel:
            st.session_state["bank_tmpl_name"] = ""
            for fk in BANK_MAP_FIELD_KEYS:
                st.session_state[f"tpl_bank_{fk}"] = BANK_COLUMN_NOT_USED
                st.session_state[f"tpl_bank_manual_{fk}"] = ""
        else:
            loaded = bank_import_template_by_id(tpl_sel)
            if loaded:
                st.session_state["bank_tmpl_name"] = loaded.get("name") or ""
                cm = loaded.get("column_map") or {}
                for fk in BANK_MAP_FIELD_KEYS:
                    v = cm.get(fk)
                    if isinstance(v, str) and v.strip() and v != BANK_COLUMN_NOT_USED:
                        st.session_state[f"tpl_bank_{fk}"] = v
                        st.session_state[f"tpl_bank_manual_{fk}"] = v.strip()
                    else:
                        st.session_state[f"tpl_bank_{fk}"] = BANK_COLUMN_NOT_USED
                        st.session_state[f"tpl_bank_manual_{fk}"] = ""
            st.session_state["bank_stmt_template_id"] = tpl_sel
            st.session_state["bank_payee_tpl_pick"] = tpl_sel

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
        Upload a sample <strong>CSV</strong> or <strong>PDF</strong> to identify columns for mapping.
        PDFs use the same table extraction as the Ledger (text tables only; scanned image PDFs are not supported).
    </p>
    """)

    uploaded = st.file_uploader(
        "Select a sample statement",
        type=["csv", "pdf"],
        help="CSV or PDF for mapping and preview (typical limit ~200MB).",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        st.success(f"Loaded: {uploaded.name}")
        bank_raw = uploaded.getvalue()
        name_l = (uploaded.name or "").lower()
        bank_hdr_list = []
        bank_hdr_idx = 0
        if name_l.endswith(".pdf"):
            pdf_err: str | None = None
            pdf_grid: list[list[str]] | None = None
            try:
                pdf_grid = extract_statement_grid_from_pdf("bank_statement", bank_raw)
            except RuntimeError as ex:
                pdf_err = str(ex)
            except Exception as ex:
                pdf_err = f"Could not read PDF: {ex}"
            if pdf_err:
                st.error(pdf_err)
                st.session_state.pop("bank_stmt_grid_rows", None)
            elif not pdf_grid or not any(
                any((c or "").strip() for c in row) for row in pdf_grid
            ):
                st.error(
                    "No table-like rows found in this PDF. Try a CSV export, or a PDF with "
                    "selectable text and an embedded transaction table (scanned image PDFs are not supported)."
                )
                st.session_state.pop("bank_stmt_grid_rows", None)
            else:
                st.session_state["bank_stmt_grid_rows"] = pdf_grid
                bank_hdr_list, bank_hdr_idx = bank_statement_headers_from_grid(pdf_grid)
        else:
            st.session_state.pop("bank_stmt_grid_rows", None)
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
        st.session_state.pop("bank_stmt_grid_rows", None)

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

    if bank_hdr_list:
        st.caption(
            "Each dropdown lists columns from your file. Use “Not used” for fields your file omits."
        )
        for emoji, map_key, field in BANK_TEMPLATE_FIELDS:
            sk = f"tpl_bank_{map_key}"
            opts = [BANK_COLUMN_NOT_USED] + bank_hdr_list
            cur = st.session_state.get(sk, BANK_COLUMN_NOT_USED)
            if cur not in opts and cur != BANK_COLUMN_NOT_USED and isinstance(cur, str):
                opts = [BANK_COLUMN_NOT_USED, cur] + [h for h in bank_hdr_list if h != cur]
            col_icon, col_label, col_select = st.columns([0.3, 1.2, 2], gap="small")
            with col_icon:
                st.html(f"<div style='padding-top:0.6rem;font-size:1.1rem;'>{emoji}</div>")
            with col_label:
                st.html(
                    f"<div style='padding-top:0.7rem;font-size:0.8rem;font-weight:600;"
                    f"color:#1a1c1c;'>{field}</div>"
                )
            with col_select:
                if sk not in st.session_state or st.session_state[sk] not in opts:
                    st.session_state[sk] = BANK_COLUMN_NOT_USED
                st.selectbox(
                    f"bank_map_{field}",
                    opts,
                    label_visibility="collapsed",
                    key=sk,
                )
    elif not bank_hdr_list:
        if uploaded is not None:
            st.caption(
                "Could not detect a header row. Ensure the first non-empty row contains column titles."
            )
        else:
            st.caption(
                "Upload a CSV or PDF to pick columns from a sample, or type the exact header text from your bank file."
            )
            for emoji, map_key, field in BANK_TEMPLATE_FIELDS:
                mk = f"tpl_bank_manual_{map_key}"
                col_icon, col_label, col_inp = st.columns([0.3, 1.2, 2], gap="small")
                with col_icon:
                    st.html(f"<div style='padding-top:0.6rem;font-size:1.1rem;'>{emoji}</div>")
                with col_label:
                    st.html(
                        f"<div style='padding-top:0.7rem;font-size:0.8rem;font-weight:600;"
                        f"color:#1a1c1c;'>{field}</div>"
                    )
                with col_inp:
                    st.text_input(
                        f"bank_manual_{field}",
                        placeholder=BANK_COLUMN_NOT_USED,
                        label_visibility="collapsed",
                        key=mk,
                    )

    # ── Payee Intelligence (inline) ───────────────────────────────────────────
    st.html("<div style='height:1rem'></div>")
    st.info(
        "Payee-to-chart rules are managed per bank or card account on the **Ledger** page, not on this "
        "template screen. Open **Ledger** from the sidebar after selecting the working account."
    )

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
            "Demo mode: the preview reflects your uploaded CSV or PDF only; saving does not write to PostgreSQL."
        )

    preview_rows_html = ""
    grid_for_preview = st.session_state.get("bank_stmt_grid_rows")
    if not isinstance(grid_for_preview, list):
        grid_for_preview = None

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
            grid_rows=grid_for_preview,
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
        st.caption("Upload a CSV or PDF to populate the preview.")
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

    edit_sel = (st.session_state.get("bank_tpl_selector") or "").strip()
    if edit_sel:
        st.markdown("---")
        st.subheader("Saved template (database)")
        rec = bank_import_template_by_id(edit_sel)
        if rec:
            st.caption(f"Template id: `{rec['id']}` · type: {rec.get('type', 'bank_statement')}")
            st.write("**Column map**")
            st.json(rec.get("column_map") or {})

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
            if bank_hdr_list:
                column_map = {
                    k: st.session_state.get(f"tpl_bank_{k}") or BANK_COLUMN_NOT_USED
                    for k in BANK_MAP_FIELD_KEYS
                }
            else:
                column_map = {
                    k: (st.session_state.get(f"tpl_bank_manual_{k}") or "").strip()
                    or BANK_COLUMN_NOT_USED
                    for k in BANK_MAP_FIELD_KEYS
                }
            sel_save = (st.session_state.get("bank_tpl_selector") or "").strip()
            if use_sample_data():
                st.warning(
                    "Demo mode (USE_SAMPLE_DATA=true): the template is not stored in PostgreSQL. "
                    "Set USE_SAMPLE_DATA=false in app/.env to save to the database."
                )
            elif sel_save:
                if update_bank_statement_template_in_db(sel_save, name, column_map):
                    st.success("Bank statement template updated in the database.")
                else:
                    st.error("Could not update template (check id and database connection).")
            else:
                new_id = save_bank_statement_template_to_db(name, column_map)
                if new_id:
                    st.session_state["bank_stmt_template_id"] = new_id
                    st.session_state["bank_payee_tpl_pick"] = new_id
                    # Do not set st.session_state["bank_tpl_selector"] here: Streamlit forbids
                    # changing a widget-bound key after that widget has been rendered this run.
                st.success("Bank statement template saved to the database.")
            st.switch_page("pages/5_Credit_Card_Config.py")
