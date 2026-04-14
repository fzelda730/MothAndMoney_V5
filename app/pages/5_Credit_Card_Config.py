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
from data.credit_card_statement_csv import (
    CC_COLUMN_NOT_USED,
    CC_MAP_FIELD_KEYS,
    build_cc_preview_rows,
    detect_cc_header_row,
    iter_cc_csv_rows,
    suggest_credit_card_column_mapping,
)
from data.credit_card_statement_pdf import credit_card_grid_from_pdf_bytes
from data.universal_layout_audit import (
    preview_rows_for_ui,
    universal_layout_audit_credit_card_pdf,
)
from data.providers import (
    db_ready,
    import_templates,
    save_credit_card_template_to_db,
)
from db.connection import use_sample_data


st.set_page_config(
    page_title="Credit Card Config | Moth and Money",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar("onboarding")
render_topbar()

if not db_ready():
    st.stop()

# ── Back link + Header ────────────────────────────────────────────────────────
if st.button("← Back to Onboarding", key="cc_back"):
    st.switch_page("pages/2_Onboarding.py")

st.html("""
<h1 class="mm-page-title" style="margin-top:1rem;margin-bottom:0.25rem;">
    Moth and Money Ledger For Creatives
</h1>
<div style="font-size:0.65rem;color:#636262;font-weight:700;text-transform:uppercase;
            letter-spacing:0.1em;margin-bottom:0.25rem;">Configuration Stage</div>
<h2 style="font-family:'Manrope',sans-serif;font-size:1.6rem;font-weight:800;
           margin:0 0 2rem;letter-spacing:-0.02em;">
    Credit Card Statement Template Configuration
</h2>
""")

col_left, col_right = st.columns([1, 1.2], gap="large")

cc_hdr_list: list[str] = []
cc_hdr_idx = 0
cc_raw: bytes | None = None
cc_grid: list[list[str]] = []
ula_preview_rows: list[dict] = []
ula_meta: dict | None = None

# ── Left: Template Identity + Upload + Column Mapping ─────────────────────────
with col_left:
    st.html("""
    <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
        Template Identity
    </h4>
    """)

    st.html('<label class="mm-settings-label">Template Name</label>')
    st.text_input(
        "cc_tmpl_name",
        placeholder="e.g. Amex Business Gold",
        label_visibility="collapsed",
        key="cc_tmpl_name",
    )

    st.html("<div style='height:1.5rem'></div>")

    st.html("""
    <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
        Upload Sample Statement
    </h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:0.75rem;">
        Upload a CSV export or a statement PDF. PDFs are read with table detection (works best when the
        issuer embeds a text table; scanned image PDFs are not supported).
    </p>
    """)

    uploaded = st.file_uploader(
        "Drag and drop a CSV or PDF statement",
        type=["csv", "pdf"],
        help="CSV or PDF for mapping and preview (typical limit ~200MB).",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        st.success(f"Loaded: {uploaded.name}")
        cc_raw = uploaded.getvalue()
        name_l = (uploaded.name or "").lower()
        is_pdf = name_l.endswith(".pdf")
        cc_upload_kind = "pdf" if is_pdf else "csv"
        pdf_err: str | None = None
        if is_pdf:
            try:
                cc_grid = credit_card_grid_from_pdf_bytes(cc_raw)
            except RuntimeError as ex:
                pdf_err = str(ex)
                cc_grid = []
        else:
            cc_grid = iter_cc_csv_rows(cc_raw)
        cc_hdr_list, cc_hdr_idx = detect_cc_header_row(cc_grid)
        if pdf_err:
            st.error(pdf_err)
        elif is_pdf and not cc_grid:
            st.warning(
                "No table-like structure was found in this PDF. Try a CSV export, or a PDF with "
                "selectable text and a clear transaction grid."
            )
        if is_pdf and cc_raw and not pdf_err:
            try:
                ula = universal_layout_audit_credit_card_pdf(cc_raw)
                ula_preview_rows = preview_rows_for_ui(ula, maximum=100)
                ula_meta = {
                    "matched_headers": ula.matched_headers,
                    "header_groups": ula.header_groups,
                    "amount_mode": ula.amount_mode,
                    "warnings": list(ula.warnings),
                    "total_parsed": len(ula.rows),
                }
            except Exception as ex:
                st.warning(f"Universal Layout Audit failed: {ex}")
        hsig = hashlib.sha256(
            f"{cc_upload_kind}:{hashlib.sha256(cc_raw).hexdigest()}".encode()
        ).hexdigest()[:28]
        if st.session_state.get("cc_csv_hdr_sig") != hsig:
            st.session_state["cc_csv_hdr_sig"] = hsig
            for fk in CC_MAP_FIELD_KEYS:
                st.session_state.pop(f"tpl_cc_{fk}", None)
            if cc_hdr_list:
                sugg = suggest_credit_card_column_mapping(cc_hdr_list)
                for fk in CC_MAP_FIELD_KEYS:
                    pick = sugg.get(fk)
                    if pick and pick in cc_hdr_list:
                        st.session_state[f"tpl_cc_{fk}"] = pick
                    else:
                        st.session_state[f"tpl_cc_{fk}"] = CC_COLUMN_NOT_USED
            else:
                for fk in CC_MAP_FIELD_KEYS:
                    st.session_state[f"tpl_cc_{fk}"] = CC_COLUMN_NOT_USED
    else:
        st.session_state.pop("cc_csv_hdr_sig", None)

    st.html("<div style='height:1.5rem'></div>")

    if uploaded is not None and (uploaded.name or "").lower().endswith(".pdf") and ula_meta:
        with st.expander("Universal Layout Audit (preview)", expanded=True):
            st.caption(
                "Transaction zone detection (3 of 4: Date, Description/Transaction, Amount, Balance). "
                "Verify standardized rows before relying on column mapping below."
            )
            st.write("**Header groups detected:**", ula_meta["header_groups"])
            st.write("**Amount column mode:**", ula_meta["amount_mode"])
            if ula_meta.get("matched_headers"):
                st.caption("Header cells: " + " | ".join(ula_meta["matched_headers"][:12]))
            for w in ula_meta.get("warnings") or []:
                st.warning(w)
            n = len(ula_preview_rows)
            total = ula_meta.get("total_parsed", n)
            if n >= 5:
                st.success(f"Showing first 5 of {total} parsed row(s).")
                display = ula_preview_rows[:5]
            elif n > 0:
                st.warning(
                    f"Only {n} row(s) parsed (aim for at least 5 when the statement has enough transactions). "
                    f"Total usable rows: {total}."
                )
                display = ula_preview_rows
            else:
                st.info("No transaction rows in the audit result yet.")
                display = []
            if display:
                st.dataframe(pd.DataFrame(display), use_container_width=True)

    st.html("""
    <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
        Column Mapping
    </h4>
    """)

    CC_TEMPLATE_FIELDS = [
        ("📅", "date", "Date"),
        ("🔄", "transaction_type", "Transaction Type"),
        ("👤", "payee", "Payee"),
        ("💰", "amount", "Amount"),
        ("📋", "account", "Chart of Account"),
        ("📝", "description", "Description"),
    ]

    if uploaded is None:
        st.caption("Upload a CSV or PDF to see its column headings here.")
    elif not cc_hdr_list:
        st.caption(
            "Could not detect a header row. Ensure the first non-empty row contains column titles."
        )
    else:
        st.caption(
            "Each dropdown lists columns from your file. Use “Not used” for fields your file omits."
        )
        opts = [CC_COLUMN_NOT_USED] + cc_hdr_list
        for emoji, map_key, field in CC_TEMPLATE_FIELDS:
            col_icon, col_label, col_select = st.columns([0.3, 1.2, 2], gap="small")
            with col_icon:
                st.html(f"<div style='padding-top:0.6rem;font-size:1.1rem;'>{emoji}</div>")
            with col_label:
                st.html(
                    f"<div style='padding-top:0.7rem;font-size:0.8rem;font-weight:600;"
                    f"color:#1a1c1c;'>{field}</div>"
                )
            with col_select:
                sk = f"tpl_cc_{map_key}"
                if sk not in st.session_state or st.session_state[sk] not in opts:
                    st.session_state[sk] = CC_COLUMN_NOT_USED
                st.selectbox(
                    f"cc_map_{field}",
                    opts,
                    label_visibility="collapsed",
                    key=sk,
                )

    st.html("<div style='height:1rem'></div>")
    st.info(
        "Payee-to-chart rules are managed per card account on the **Ledger** page. Choose the account "
        "in Ledger, then open **Payee rules for this account** there."
    )

# ── Right: Live Preview + Save ───────────────────────────────────────────────
with col_right:
    st.html("""
    <h4 class="mm-settings-label" style="font-size:0.65rem;margin-bottom:0.5rem;">
        Live Preview
    </h4>
    <p style="font-size:0.75rem;color:#636262;margin-bottom:1.25rem;">
        First 3 rows using your file and current column mapping.
    </p>
    """)

    if use_sample_data():
        st.info(
            "Demo mode: preview uses your upload only; saving the template does not write to PostgreSQL."
        )

    preview_rows_html = ""
    if cc_raw is not None and cc_hdr_list and cc_grid:
        column_map = {
            fk: st.session_state.get(f"tpl_cc_{fk}", CC_COLUMN_NOT_USED)
            for fk in CC_MAP_FIELD_KEYS
        }
        preview_data = build_cc_preview_rows(
            cc_hdr_list,
            cc_hdr_idx,
            column_map,
            grid_rows=cc_grid,
            not_used=CC_COLUMN_NOT_USED,
            max_rows=3,
        )
        for row in preview_data:
            amt_color = "#71151d" if row["amount"] < 0 else "#154212"
            d = html.escape(str(row["date"]))
            p = html.escape(str(row["payee"]))
            s = html.escape(str(row["sub"])) if row["sub"] else ""
            sub_html = (
                f'<div style="font-size:0.65rem;color:#636262;">{s}</div>' if s else ""
            )
            acct = html.escape(str(row["account"]))
            preview_rows_html += f"""
        <tr style="background:#ffffff;">
            <td style="padding:0.75rem;font-size:0.75rem;color:#636262;">{d}</td>
            <td style="padding:0.75rem;">
                <div style="font-size:0.8rem;font-weight:600;">{p}</div>
                {sub_html}
            </td>
            <td style="padding:0.75rem;">
                <span style="background:#eeeeee;color:#636262;font-size:0.65rem;font-weight:600;
                             padding:0.1rem 0.5rem;border-radius:0.125rem;">
                    {acct}
                </span>
            </td>
            <td style="padding:0.75rem;text-align:right;font-size:0.8rem;color:{amt_color};
                       font-weight:600;">${abs(row['amount']):,.2f}</td>
        </tr>"""
    elif uploaded is None:
        st.caption("Upload a CSV or PDF to populate the preview.")
    else:
        st.caption("No preview rows yet, or headers could not be read.")

    st.html(f"""
    <div style="background:#ffffff;border-radius:0.5rem;overflow:hidden;
                border:1px solid rgba(194,201,187,0.2);margin-bottom:1.5rem;">
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#f3f3f3;">
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Date</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Payee</th>
                    <th style="padding:0.75rem;text-align:left;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Account</th>
                    <th style="padding:0.75rem;text-align:right;font-size:0.6rem;font-weight:700;
                               text-transform:uppercase;letter-spacing:0.1em;color:#636262;">Amount</th>
                </tr>
            </thead>
            <tbody>{preview_rows_html or ""}</tbody>
        </table>
    </div>
    """)

    st.caption(
        "After you confirm the mapping, save the template. Refine payee-to-chart rules on the Ledger page "
        "for each account."
    )

    if st.button("💾 Save Template", key="cc_save", type="primary", use_container_width=True):
        name = (st.session_state.get("cc_tmpl_name") or "").strip()
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
                    k: st.session_state.get(f"tpl_cc_{k}") or CC_COLUMN_NOT_USED
                    for k in CC_MAP_FIELD_KEYS
                }
                new_id = save_credit_card_template_to_db(name, column_map)
                if new_id:
                    st.session_state["cc_stmt_template_id"] = new_id
                st.success(
                    "Credit card template saved to the database. Onboarding complete!"
                )
            st.switch_page("pages/1_Dashboard.py")
