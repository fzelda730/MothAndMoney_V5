"""
Unified data access: sample_data when USE_SAMPLE_DATA=true, else PostgreSQL queries.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from db.connection import check_connection, use_sample_data


def db_ready() -> bool:
    """Return False and show an error if DB mode is on but the database is unreachable."""
    if use_sample_data():
        return True
    ok, err = check_connection()
    if ok:
        return True
    st.error(
        "PostgreSQL is not reachable. Set USE_SAMPLE_DATA=true in app/.env to use demo data, "
        "or fix DATABASE_URL / DB_* and ensure the database is running."
    )
    if err:
        st.caption(err)
    return False


def bank_accounts():
    if use_sample_data():
        from data.sample_data import BANK_ACCOUNTS

        return BANK_ACCOUNTS
    from db import queries

    return queries.fetch_bank_accounts()


def studio_profile():
    if use_sample_data():
        from data.sample_data import STUDIO

        return STUDIO
    from db import queries

    return queries.fetch_studio_profile()


def save_studio_profile_to_db(**kwargs) -> None:
    """Persist studio_profile row. Only use when USE_SAMPLE_DATA is false."""
    from db import queries

    queries.update_studio_profile(**kwargs)


def dashboard_stats():
    """Portfolio headline stats remain demo-derived until summary tables exist."""
    from data.sample_data import DASHBOARD_STATS

    return DASHBOARD_STATS


def tax_provision():
    from data.sample_data import TAX_PROVISION

    return TAX_PROVISION


def ledger_transactions(bank_account_id: str | None):
    if use_sample_data():
        from data.sample_data import LEDGER_TRANSACTIONS

        return LEDGER_TRANSACTIONS
    from db import queries

    if not bank_account_id:
        return []
    return queries.fetch_ledger_transactions(bank_account_id)


def ledger_summary(bank_account_id: str | None):
    if use_sample_data():
        from data.sample_data import BANK_ACCOUNTS, LEDGER_SUMMARY

        if not bank_account_id:
            return {
                "beginning_balance": 0.0,
                "total_debits": 0.0,
                "total_credits": 0.0,
                "ending_balance": 0.0,
                "is_balanced": True,
            }
        for a in BANK_ACCOUNTS:
            if a.get("id") == bank_account_id:
                beg = float(a.get("beginning_balance") or 0)
                td = abs(float(a.get("total_debits") or 0))
                tc = abs(float(a.get("total_credits") or 0))
                end = float(a.get("ending_balance") or 0)
                return {
                    "beginning_balance": beg,
                    "total_debits": td,
                    "total_credits": tc,
                    "ending_balance": end,
                    "is_balanced": abs((beg - td + tc) - end) < 0.02,
                }
        return {**LEDGER_SUMMARY}

    from db import queries

    if not bank_account_id:
        return {
            "beginning_balance": 0.0,
            "total_debits": 0.0,
            "total_credits": 0.0,
            "ending_balance": 0.0,
            "is_balanced": True,
        }
    return queries.fetch_ledger_summary(bank_account_id)


def import_templates():
    if use_sample_data():
        from data.sample_data import IMPORT_TEMPLATES

        return IMPORT_TEMPLATES
    from db import queries

    return queries.fetch_import_templates()


def import_template_by_id(template_id: str) -> dict | None:
    """Single import template by id (bank_statement or credit_card). None if missing."""
    tid = (template_id or "").strip()
    if not tid:
        return None
    if use_sample_data():
        for t in import_templates():
            if (t.get("id") or "").strip() == tid:
                return t
        return None
    from db import queries

    return queries.fetch_import_template_by_id(tid)


def chart_of_accounts():
    if use_sample_data():
        from data.sample_data import CHART_OF_ACCOUNTS

        return CHART_OF_ACCOUNTS
    from db import queries

    return queries.fetch_chart_of_accounts()


def save_chart_of_account_to_db(
    *,
    account_number: str,
    account_name: str,
    account_type: str,
    account_subtype: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Insert a chart of accounts row. Returns (new_id, None) on success, (None, message) on error.
    Demo mode does not persist; returns (None, message).
    """
    if use_sample_data():
        return (
            None,
            "Adding chart accounts requires PostgreSQL. Set USE_SAMPLE_DATA=false in app/.env and configure "
            "the database.",
        )
    from db import queries

    return queries.insert_chart_of_account(
        account_number=account_number,
        account_name=account_name,
        account_type=account_type,
        account_subtype=account_subtype,
    )


_DEMO_PG_ONLY = (
    "Editing chart accounts requires PostgreSQL. Set USE_SAMPLE_DATA=false in app/.env and configure "
    "the database."
)


def get_chart_of_account_for_edit(coa_id: str) -> dict | None:
    """Single COA row for edit form; None if missing or demo mode."""
    if use_sample_data():
        return None
    from db import queries

    return queries.fetch_chart_of_account_by_id(coa_id)


def update_chart_of_account_in_db(
    coa_id: str,
    *,
    account_number: str,
    account_name: str,
    account_type: str,
    account_subtype: str | None = None,
) -> tuple[bool, str | None]:
    """Returns (True, None) on success."""
    if use_sample_data():
        return False, _DEMO_PG_ONLY
    from db import queries

    return queries.update_chart_of_account(
        coa_id,
        account_number=account_number,
        account_name=account_name,
        account_type=account_type,
        account_subtype=account_subtype,
    )


def delete_chart_of_account_from_db(coa_id: str) -> tuple[bool, str | None]:
    """Returns (True, None) on success."""
    if use_sample_data():
        return False, _DEMO_PG_ONLY
    from db import queries

    return queries.delete_chart_of_account(coa_id)


def trial_balance_report():
    if use_sample_data():
        from data.sample_data import TRIAL_BALANCE_REPORT

        return TRIAL_BALANCE_REPORT
    from db import queries

    return queries.fetch_trial_balance_report()


def _demo_general_ledger_detail(
    period_start: date,
    period_end: date,
    coa_number_from: str | None,
    coa_number_to: str | None,
    bank_account_id: str | None,
) -> list[dict]:
    """
    Demo GL from SAMPLE_ACCOUNT_DETAIL only (bank_account_id ignored).
    There is no trial_balance_entries in demo mode—beginning is prior sample lines only.
    PostgreSQL mode adds confirmed TB opening per the queries layer.
    """
    from data.sample_data import CHART_OF_ACCOUNTS, SAMPLE_ACCOUNT_DETAIL

    ps, pe = period_start, period_end
    if ps > pe:
        ps, pe = pe, ps

    def in_range(num: str) -> bool:
        cf = (coa_number_from or "").strip()
        ct = (coa_number_to or "").strip()
        if not cf and not ct:
            return True
        if cf and ct:
            return cf <= num <= ct
        if cf:
            return num >= cf
        return num <= ct

    coas = [a for a in CHART_OF_ACCOUNTS if in_range(a["number"])]
    out: list[dict] = []
    for a in coas:
        num = a["number"]
        name = a["name"]
        beg = 0.0
        for r in SAMPLE_ACCOUNT_DETAIL:
            if r["account_number"] != num:
                continue
            if r["date"] < ps:
                deb = float(r["debit"] or 0)
                crd = float(r["credit"] or 0)
                beg += deb - crd
        period_rows = [
            r
            for r in SAMPLE_ACCOUNT_DETAIL
            if r["account_number"] == num and ps <= r["date"] <= pe
        ]
        period_rows.sort(key=lambda x: x["date"])
        lines: list[dict] = []
        run = beg
        for r in period_rows:
            deb = float(r["debit"] or 0)
            crd = float(r["credit"] or 0)
            run += deb - crd
            lines.append(
                {
                    "date": r["date"].isoformat(),
                    "payee": r.get("payee") or "",
                    "description": r.get("memo") or "",
                    "debit": deb if deb else None,
                    "credit": crd if crd else None,
                    "balance": run,
                }
            )
        ending = run
        at_raw = (a.get("type") or "asset").strip()
        atype = at_raw.lower()
        out.append(
            {
                "coa_number": num,
                "coa_name": name,
                "coa_type": atype,
                "beginning_balance": beg,
                "ending_balance": ending,
                "lines": lines,
            }
        )
    return out


def general_ledger_report(
    period_start: date,
    period_end: date,
    coa_number_from: str | None = None,
    coa_number_to: str | None = None,
    bank_account_id: str | None = None,
) -> list[dict]:
    """Chart-account GL: beginning, period lines, ending; debit minus credit net."""
    if use_sample_data():
        return _demo_general_ledger_detail(
            period_start,
            period_end,
            coa_number_from,
            coa_number_to,
            bank_account_id,
        )
    from db import queries

    return queries.fetch_general_ledger_detail(
        period_start,
        period_end,
        coa_number_from,
        coa_number_to,
        bank_account_id,
    )


def trial_balance_import():
    if use_sample_data():
        from data.sample_data import TRIAL_BALANCE_IMPORT_PREVIEW, TRIAL_BALANCE_TOTALS

        return TRIAL_BALANCE_IMPORT_PREVIEW, TRIAL_BALANCE_TOTALS
    from db import queries

    preview, totals = queries.fetch_trial_balance_import_preview()
    if preview:
        return preview, totals
    return [], {
        "total_debits": 0.0,
        "total_credits": 0.0,
        "is_balanced": False,
        "variance": 0.0,
    }


def discard_pending_trial_balance() -> int:
    """Delete pending trial_balance_entries (no-op in demo mode)."""
    if use_sample_data():
        return 0
    from db import queries

    return queries.delete_pending_trial_balance_entries()


def save_trial_balance_csv_to_db(reference_name: str, rows: list[dict]) -> int:
    """Persist CSV trial balance rows when USE_SAMPLE_DATA=false. Returns inserted line count."""
    if use_sample_data():
        return 0
    if not (reference_name or "").strip():
        return 0
    from db import queries

    return queries.save_trial_balance_csv_import(reference_name, rows)


def bank_accounts_for_tb_mapping() -> list[dict]:
    """
    Registered bank accounts for mapping trial balance lines (excludes TB-IMPORT book).
    Each dict: id, account_name, account_number_masked.
    """
    if use_sample_data():
        from data.sample_data import BANK_ACCOUNTS

        return [
            {
                "id": a["id"],
                "account_name": a["account_name"],
                "account_number_masked": str(a.get("masked") or "").strip(),
            }
            for a in BANK_ACCOUNTS
            if (a.get("account_type") or "").lower() != "cash"
        ]
    from db import queries

    return queries.fetch_bank_accounts_for_tb_mapping()


def save_bank_statement_template_to_db(template_name: str, column_map: dict) -> str:
    """Insert a bank statement import template. Returns new row id, or empty string if demo or failure."""
    if use_sample_data():
        return ""
    if not (template_name or "").strip():
        return ""
    from db import queries

    return queries.insert_import_template(template_name, "bank_statement", column_map)


def bank_import_template_by_id(template_id: str) -> dict | None:
    """Single bank_statement template by id, or None."""
    tid = (template_id or "").strip()
    if not tid:
        return None
    if use_sample_data():
        for t in import_templates():
            if t.get("id") == tid and t.get("type") == "bank_statement":
                return t
        return None
    from db import queries

    row = queries.fetch_import_template_by_id(tid)
    if not row or row.get("type") != "bank_statement":
        return None
    return row


def update_bank_statement_template_in_db(
    template_id: str, template_name: str, column_map: dict
) -> bool:
    """Update an existing bank_statement template. False in demo mode or if no row updated."""
    if use_sample_data():
        return False
    if not (template_id or "").strip() or not (template_name or "").strip():
        return False
    from db import queries

    return queries.update_import_template(
        template_id, template_name, column_map, "bank_statement"
    )


def payee_rules_schema_ready() -> bool:
    """
    True in demo mode, or when PostgreSQL payee_rules has been migrated (bank_account_id column).
    When ready, result is cached for the session. When not ready, we re-check each run so a
    migration without restarting Streamlit is picked up.
    """
    if use_sample_data():
        return True
    k = "_cache_payee_rules_bank_account_id_col"
    if st.session_state.get(k) is True:
        return True
    from db import queries

    ok = queries.schema_has_payee_rules_bank_account_id()
    if ok:
        st.session_state[k] = True
    return ok


def payee_rules_for_bank_account(bank_account_id: str) -> list[dict]:
    """payee_rules rows for a bank account (session-backed in demo mode)."""
    aid = (bank_account_id or "").strip()
    if not aid:
        return []
    if use_sample_data():
        import hashlib

        from data.sample_data import CHART_OF_ACCOUNTS

        rules_map = st.session_state.get("payee_demo_rules", {}).get(aid, {}) or {}
        coa_by_id = {str(c.get("id", "")): c for c in CHART_OF_ACCOUNTS}
        out: list[dict] = []
        for pat in sorted(rules_map.keys()):
            cid = rules_map[pat]
            coa = coa_by_id.get(cid, {})
            hid = hashlib.sha256(f"{aid}|{pat}".encode()).hexdigest()[:12]
            out.append(
                {
                    "id": f"demo-{hid}",
                    "payee_pattern": pat,
                    "coa_id": cid,
                    "coa_number": coa.get("number", ""),
                    "coa_name": coa.get("name", ""),
                }
            )
        return out
    if not payee_rules_schema_ready():
        return []
    from db import queries

    return queries.fetch_payee_rules_for_bank_account(aid)


def persist_payee_rule_for_bank_account(
    bank_account_id: str, payee_pattern_normalized: str, coa_id: str | None
) -> None:
    """Upsert or delete a payee rule for one bank account."""
    aid = (bank_account_id or "").strip()
    pid = (payee_pattern_normalized or "").strip()
    if not aid or not pid:
        return
    if use_sample_data():
        bucket = st.session_state.setdefault("payee_demo_rules", {}).setdefault(aid, {})
        c = (coa_id or "").strip()
        if c:
            bucket[pid] = c
        else:
            bucket.pop(pid, None)
        return
    if not payee_rules_schema_ready():
        return
    from db import queries

    if coa_id and (coa_id or "").strip():
        queries.upsert_payee_rule_for_bank_account(aid, pid, coa_id.strip())
    else:
        queries.delete_payee_rule_for_bank_account(aid, pid)


def delete_payee_rule_for_bank_account(
    bank_account_id: str, payee_pattern_normalized: str
) -> None:
    """Remove a payee rule row."""
    if use_sample_data():
        aid = (bank_account_id or "").strip()
        pid = (payee_pattern_normalized or "").strip()
        if aid and pid:
            d = st.session_state.setdefault("payee_demo_rules", {})
            b = d.get(aid)
            if isinstance(b, dict):
                b.pop(pid, None)
        return
    if not payee_rules_schema_ready():
        return
    from db import queries

    queries.delete_payee_rule_for_bank_account(bank_account_id, payee_pattern_normalized)


def resolve_bank_import_payee_coa_id(payee_raw: str, bank_account_id: str) -> str | None:
    """
    Resolve COA id from payee text for a bank import batch (exact normalized match).
    In demo mode, reads rules from session key payee_demo_rules if present.
    """
    from data.bank_statement_csv import normalize_payee_for_rule

    norm = normalize_payee_for_rule(payee_raw)
    aid = (bank_account_id or "").strip()
    if not norm or not aid:
        return None
    if use_sample_data():
        nested = st.session_state.get("payee_demo_rules", {}).get(aid, {})
        return nested.get(norm)
    if not payee_rules_schema_ready():
        return None
    from db import queries

    return queries.resolve_coa_id_for_bank_payee(payee_raw, bank_account_id)


def save_credit_card_template_to_db(template_name: str, column_map: dict) -> str:
    """Insert a credit card import template. Empty string if demo mode or insert failed."""
    if use_sample_data():
        return ""
    if not (template_name or "").strip():
        return ""
    from db import queries

    return queries.insert_import_template(template_name, "credit_card", column_map)


def banks_for_onboarding() -> list[dict]:
    """Institutions for account registration (empty in demo mode)."""
    if use_sample_data():
        return []
    from db import queries

    return queries.fetch_banks()


def bank_accounts_manage() -> list[dict]:
    """Registered accounts with transaction counts for onboarding management."""
    if use_sample_data():
        return []
    from db import queries

    return queries.fetch_bank_accounts_manage()


def save_bank_account_to_db(
    *,
    existing_bank_id: str | None,
    new_bank_name: str | None,
    bank_type_for_new: str | None,
    template_id: str | None,
    account_name: str,
    account_number_masked: str,
    account_type: str,
) -> tuple[str | None, str | None]:
    """
    Insert a bank_accounts row, creating a bank row when existing_bank_id is empty.
    Returns (new_account_id, error_message). error_message None on success.
    """
    if use_sample_data():
        return None, "Set USE_SAMPLE_DATA=false in app/.env to register accounts in PostgreSQL."
    from db import queries

    try:
        bid = (existing_bank_id or "").strip()
        if bid:
            banks = queries.fetch_banks()
            if not any(b["id"] == bid for b in banks):
                return None, "Selected institution was not found."
        else:
            name = (new_bank_name or "").strip()
            if not name:
                return None, "Institution name is required for a new bank."
            bt = (bank_type_for_new or "").strip().lower()
            if bt not in ("depository", "credit_card"):
                return None, "Choose whether the institution is a bank or a card issuer."
            bid = queries.insert_bank(name, bt)
        aid = queries.insert_bank_account(
            bid,
            (template_id or "").strip() or None,
            account_name.strip(),
            account_number_masked.strip(),
            account_type.strip().lower(),
        )
        return aid, None
    except Exception as e:
        return None, str(e)


def delete_bank_account_from_db(bank_account_id: str) -> str | None:
    """
    Remove a bank account when it has no transactions. Returns None on success, else message.
    """
    if use_sample_data():
        return "Account removal is only available when using PostgreSQL (USE_SAMPLE_DATA=false)."
    from db import queries

    return queries.delete_bank_account_if_safe(bank_account_id)


def resolve_credit_card_import_payee_coa_id(payee_raw: str, bank_account_id: str) -> str | None:
    """
    Resolve COA id from payee for a credit card import (same payee_rules table as bank).
    Demo mode uses payee_demo_rules keyed by bank_account_id (same as bank import).
    """
    from data.credit_card_statement_csv import normalize_payee_for_rule

    norm = normalize_payee_for_rule(payee_raw)
    aid = (bank_account_id or "").strip()
    if not norm or not aid:
        return None
    if use_sample_data():
        nested = st.session_state.get("payee_demo_rules", {}).get(aid, {})
        return nested.get(norm)
    if not payee_rules_schema_ready():
        return None
    from db import queries

    return queries.resolve_coa_id_for_bank_payee(payee_raw, bank_account_id)


def _account_type_for_id(bank_account_id: str) -> str | None:
    aid = (bank_account_id or "").strip()
    if not aid:
        return None
    for a in bank_accounts():
        if (a.get("id") or "").strip() == aid:
            return (a.get("account_type") or "").strip().lower() or None
    return None


def _validate_template_type_for_account(account_type: str, template_type: str) -> str | None:
    """Return error message if incompatible, else None."""
    at = (account_type or "").strip().lower()
    tpt = (template_type or "").strip()
    if at == "credit_card" and tpt != "credit_card":
        return (
            "This account is a credit card, but the selected template is not a credit card template."
        )
    if at in ("checking", "savings", "cash") and tpt != "bank_statement":
        return (
            "This account is a bank account, but the selected template is not a bank statement template."
        )
    return None


def preview_ledger_csv_import(
    bank_account_id: str,
    template_id: str,
    file_bytes: bytes,
    date_start: date | None,
    date_end: date | None,
    filename: str = "upload.csv",
) -> tuple[list[dict] | None, str | None]:
    """
    Parse CSV or PDF using the selected template; resolve initial COA from payee rules.
    PDFs are converted to a row grid via pdfplumber (same approach as Credit Card template).
    Returns (rows with coa_id set, None) or (None, error_message).
    """
    from data.ledger_statement_import import (
        extract_statement_grid_from_pdf,
        format_ledger_parse_failure_message,
        parse_ledger_csv_rows,
    )

    aid = (bank_account_id or "").strip()
    tid = (template_id or "").strip()
    if not aid:
        return None, "No bank account selected."
    if not tid:
        return None, "No import template selected."

    tmpl = import_template_by_id(tid)
    if not tmpl:
        return None, "Template not found."

    at = _account_type_for_id(aid)
    if not at:
        return None, "Bank account not found."

    err = _validate_template_type_for_account(at, tmpl.get("type") or "")
    if err:
        return None, err

    tpt = (tmpl.get("type") or "").strip()
    cm = tmpl.get("column_map") or {}

    is_pdf = (filename or "").lower().endswith(".pdf")
    grid_rows = None
    if is_pdf:
        try:
            grid_rows = extract_statement_grid_from_pdf(tpt, file_bytes)
        except RuntimeError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Could not read PDF: {e}"
        if not grid_rows or not any(
            any((c or "").strip() for c in row) for row in grid_rows
        ):
            return None, (
                "No table-like rows found in this PDF. Try a CSV export, or a PDF with "
                "selectable text and an embedded transaction table (scanned image PDFs are not supported)."
            )

    try:
        rows, diag = parse_ledger_csv_rows(
            file_bytes=file_bytes,
            template_type=tpt,
            column_map=cm,
            date_start=date_start,
            date_end=date_end,
            grid_rows=grid_rows,
        )
    except Exception as e:
        return None, (f"Could not parse PDF: {e}" if is_pdf else f"Could not parse CSV: {e}")

    if not rows:
        return None, format_ledger_parse_failure_message(diag, date_start, date_end)

    for r in rows:
        if tpt == "credit_card":
            r["coa_id"] = resolve_credit_card_import_payee_coa_id(r["payee"], aid)
        else:
            r["coa_id"] = resolve_bank_import_payee_coa_id(r["payee"], aid)
    return rows, None


def commit_ledger_csv_import(
    bank_account_id: str,
    template_id: str,
    filename: str,
    date_start: date | None,
    date_end: date | None,
    transaction_rows: list[dict],
) -> tuple[int, str | None]:
    """
    Insert import batch + transactions, then upsert payee rules for rows with a coa_id.
    Each row must have: date, payee, payee_normalized, debit_amount, credit_amount,
    description (optional), source, coa_id (required chart-of-accounts id).
    Returns (inserted_count, error_message); in demo mode inserted_count is 0 and message explains.
    """
    aid = (bank_account_id or "").strip()
    tid = (template_id or "").strip()
    if not aid or not tid:
        return 0, "No bank account or template."
    if not transaction_rows:
        return 0, "No rows to import."

    missing_coa = [
        i + 1
        for i, r in enumerate(transaction_rows)
        if not (r.get("coa_id") or "").strip()
    ]
    if missing_coa:
        head = ", ".join(str(n) for n in missing_coa[:25])
        tail = f" (+{len(missing_coa) - 25} more)" if len(missing_coa) > 25 else ""
        return (
            0,
            "Every row must have a chart account assigned. "
            f"Missing on row(s): {head}{tail}.",
        )

    txn_payload = [
        {
            "date": r["date"],
            "payee": r["payee"],
            "payee_normalized": r["payee_normalized"],
            "debit_amount": r["debit_amount"],
            "credit_amount": r["credit_amount"],
            "description": r.get("description"),
            "coa_id": r.get("coa_id"),
            "source": r["source"],
        }
        for r in transaction_rows
    ]

    if use_sample_data():
        for r in transaction_rows:
            cid = (r.get("coa_id") or "").strip()
            pn = (r.get("payee_normalized") or "").strip()
            if cid and pn:
                persist_payee_rule_for_bank_account(aid, pn, cid)
        return (
            0,
            "Demo mode: payee rules saved in session. Set USE_SAMPLE_DATA=false in app/.env to import "
            "transactions into PostgreSQL.",
        )

    from db import queries

    try:
        queries.insert_ledger_import_batch_and_transactions(
            bank_account_id=aid,
            template_id=tid,
            filename=filename or "upload.csv",
            period_start=date_start,
            period_end=date_end,
            transaction_rows=txn_payload,
        )
    except Exception as e:
        return 0, str(e)

    for r in transaction_rows:
        cid = (r.get("coa_id") or "").strip()
        pn = (r.get("payee_normalized") or "").strip()
        if cid and pn:
            persist_payee_rule_for_bank_account(aid, pn, cid)

    return len(txn_payload), None


def process_ledger_csv_upload(
    bank_account_id: str,
    file_bytes: bytes,
    filename: str,
    date_start: date | None,
    date_end: date | None,
) -> tuple[int, str | None]:
    """
    Legacy one-step import using the account's linked template in PostgreSQL only.
    Prefer preview_ledger_csv_import + commit_ledger_csv_import from the Ledger page.
    """
    if use_sample_data():
        return (
            0,
            "Imports require PostgreSQL. Set USE_SAMPLE_DATA=false in app/.env and configure the database.",
        )
    aid = (bank_account_id or "").strip()
    if not aid:
        return 0, "No bank account selected."
    from data.ledger_statement_import import (
        format_ledger_parse_failure_message,
        parse_ledger_csv_rows,
    )
    from db import queries

    ctx = queries.fetch_bank_account_import_context(aid)
    if not ctx:
        return 0, "Bank account not found."
    tid = (ctx.get("template_id") or "").strip()
    if not tid:
        return (
            0,
            "This account has no import template. Open Bank & card accounts and link a template.",
        )
    tpt = (ctx.get("template_type") or "").strip()
    at = (ctx.get("account_type") or "").strip().lower()
    if at == "credit_card" and tpt != "credit_card":
        return (
            0,
            "This account is a credit card, but the linked template is not a credit card template. "
            "Update the account on Bank & card accounts.",
        )
    if at in ("checking", "savings", "cash") and tpt != "bank_statement":
        return (
            0,
            "This account is a bank account, but the linked template is not a bank statement template. "
            "Update the account on Bank & card accounts.",
        )

    try:
        rows, diag = parse_ledger_csv_rows(
            file_bytes=file_bytes,
            template_type=tpt,
            column_map=ctx.get("column_map") or {},
            date_start=date_start,
            date_end=date_end,
        )
    except Exception as e:
        return 0, f"Could not parse CSV: {e}"

    if not rows:
        return (0, format_ledger_parse_failure_message(diag, date_start, date_end))

    for r in rows:
        if tpt == "credit_card":
            cid = resolve_credit_card_import_payee_coa_id(r["payee"], aid)
        else:
            cid = resolve_bank_import_payee_coa_id(r["payee"], aid)
        r["coa_id"] = cid

    txn_payload = [
        {
            "date": r["date"],
            "payee": r["payee"],
            "payee_normalized": r["payee_normalized"],
            "debit_amount": r["debit_amount"],
            "credit_amount": r["credit_amount"],
            "description": r.get("description"),
            "coa_id": r.get("coa_id"),
            "source": r["source"],
        }
        for r in rows
    ]

    try:
        queries.insert_ledger_import_batch_and_transactions(
            bank_account_id=aid,
            template_id=tid,
            filename=filename or "upload.csv",
            period_start=date_start,
            period_end=date_end,
            transaction_rows=txn_payload,
        )
    except Exception as e:
        return 0, str(e)

    return len(txn_payload), None


def first_non_cash_bank_account_id() -> str | None:
    if use_sample_data():
        for a in bank_accounts():
            if a.get("account_type") != "cash":
                return a["id"]
        return None
    from db import queries

    return queries.first_bank_account_id_non_cash()
