"""
MOTH AND MONEY — STATEMENT UPLOAD (UI)
/ui/statement_upload.py

Formal:  Ingest: choose bank_templates driver; upload PDF or CSV; preview; post to ledger.
Human:   Pick the format, pick the money bucket, drop the file, confirm, then commit.

Accounting Rule:
    Rule 11 — rows come from logic.bank_templates.list_bank_templates_for_ingest_menu only.
    Rule 5 — source_metadata is the upload filename; duplicate filenames are blocked.
"""

from __future__ import annotations

import pandas
import streamlit as st
from streamlit.column_config import SelectboxColumn, TextColumn

from database.statement_import_chart_seed import STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER
from logic.bank_statement_posting import post_statement_import_transactions
from logic.bank_templates import (
    BUILT_IN_PDF_KIND,
    CSV_HEADERS_KIND,
    describe_linked_chart_accounts_for_bank_template_catalog,
    ingest_menu_display_label,
    list_bank_templates_for_ingest_menu,
    load_active_chart_accounts_for_template_picker,
    load_linked_chart_account_numbers_for_bank_template,
    statement_upload_chart_account_rows_respecting_template_links,
)
from logic.built_in_pdf_extract import (
    bank_statement_transactions_for_posting,
    dataframe_from_built_in_pdf,
)
from logic.csv_statement_extract import (
    dataframe_from_csv_statement_transactions,
    transaction_dicts_from_csv_template,
)
from logic.payee_statement_classification import (
    build_offset_account_option_labels,
    enrich_statement_transactions_with_payee_offsets_using_default_session,
    merge_edited_preview_into_posting_rows,
    statement_preview_rows_to_dataframe_rows,
)


def _statement_upload_apply_linked_table_selection_to_target_key(
    *,
    linked_table_session_key: str,
    target_widget_session_key: str,
    linked_target_option_labels: list[str],
) -> None:
    """
    Formal:  Copies st.dataframe single-row selection into statement_upload_target_account_*.
    Human:   Clicking a linked-account row chooses the same posting label the old selectbox used.

    Accounting Rule:
        N/A — UI session sync only.
    """
    if len(linked_target_option_labels) == 0:
        return

    selected_row_indexes: list[int] = []
    if linked_table_session_key in st.session_state:
        table_state = st.session_state[linked_table_session_key]
        if isinstance(table_state, dict):
            selection_payload = table_state.get("selection")
            if isinstance(selection_payload, dict):
                raw_rows = selection_payload.get("rows") or []
                selected_row_indexes = [int(row_index) for row_index in raw_rows]

    if len(selected_row_indexes) == 1:
        row_index = selected_row_indexes[0]
        if 0 <= row_index < len(linked_target_option_labels):
            st.session_state[target_widget_session_key] = linked_target_option_labels[
                row_index
            ]
            return

    prior_label = st.session_state.get(target_widget_session_key)
    if prior_label not in linked_target_option_labels:
        st.session_state[target_widget_session_key] = linked_target_option_labels[0]


def _statement_upload_resolve_target_account_number(
    *,
    chosen_template_row: dict,
    statement_upload_chart_accounts: list[dict],
    template_row_identifier: int,
) -> int | None:
    """
    Formal:  Target chart account from template default, linked-table selection, or selectbox value.
    Human:   CSV maps always pick here (legacy linked_account_number on csv rows is ignored).

    Accounting Rule:
        N/A — UI routing only.
    """
    ingest_kind = str(chosen_template_row.get("ingest_kind") or "")
    bound_linked_account = chosen_template_row["linked_account_number"]
    if ingest_kind != CSV_HEADERS_KIND and bound_linked_account is not None:
        return int(bound_linked_account)

    widget_key = f"statement_upload_target_account_{template_row_identifier}"
    selected_label = st.session_state.get(widget_key)
    if selected_label is None or selected_label == "":
        return None
    try:
        account_number_token = str(selected_label).split("—")[0].strip()
        return int(account_number_token)
    except ValueError:
        return None


def render_statement_upload_page() -> None:
    """
    Formal:  Statement Upload: ingest source, optional file by kind, preview, post balanced lines.
    Human:   Same driver list as Template Manager; PDF uses built-in code, CSV uses saved headers.

    Accounting Rule:
        Each file becomes one journal entry; every transaction is two ledger lines — register account
        paired with your chosen offset account or import clearing (5890). Payee mappings save on post.
    """
    st.title("Statement Upload")
    st.caption(
        "Formal: bank_templates drivers (CSV maps or built-in PDF). "
        "Human: Choose the export shape, pick your chart account when needed, upload, preview, then post."
    )

    try:
        ingest_template_catalog = list_bank_templates_for_ingest_menu()
    except Exception as load_error:
        st.warning(
            "Could not load bank templates. Run Onboarding or restart after database init. "
            f"Details: {load_error!s}"
        )
        ingest_template_catalog = []

    if len(ingest_template_catalog) == 0:
        st.info(
            "No ingest sources yet. Open Template Manager to save a CSV map, or re-run the app "
            "so built-in PDF drivers (Chase card, Chase checking, etc.) can seed."
        )
        return

    dropdown_labels = [ingest_menu_display_label(row) for row in ingest_template_catalog]
    selected_label = st.selectbox(
        "Ingest source",
        options=dropdown_labels,
        help=(
            "Formal: bank_templates row driving the parser. Human: CSV maps use your saved headers; "
            "built-in PDF rows call packaged logic for that bank."
        ),
    )
    selected_index = dropdown_labels.index(selected_label)
    chosen_template_row = ingest_template_catalog[selected_index]
    template_row_identifier = int(chosen_template_row["id"])
    ingest_kind = str(chosen_template_row["ingest_kind"])
    template_table_linked_account = chosen_template_row["linked_account_number"]
    effective_bound_linked_account: int | None = None
    if ingest_kind != CSV_HEADERS_KIND and template_table_linked_account is not None:
        effective_bound_linked_account = int(template_table_linked_account)

    statement_upload_chart_accounts, chart_link_restriction_warning = (
        statement_upload_chart_account_rows_respecting_template_links(
            chosen_template_row=chosen_template_row,
            all_active_chart_account_rows=load_active_chart_accounts_for_template_picker(),
        )
    )
    if chart_link_restriction_warning is not None:
        st.warning(chart_link_restriction_warning)
        linked_fallback_check = load_linked_chart_account_numbers_for_bank_template(
            template_row_identifier
        )
        if len(linked_fallback_check) > 0:
            st.info(
                "Template Manager short list for this driver was: "
                f"{describe_linked_chart_accounts_for_bank_template_catalog(template_row_identifier)}. "
                "Those accounts are inactive or missing from the chart, so the dropdown shows "
                "every active account until you fix links or reactivate an account."
            )

    if effective_bound_linked_account is None:
        st.markdown("##### Chart account for this upload")
        st.caption(
            "Formal: Target chart_of_accounts for this statement. "
            "Human: The register leg posts here; the other leg uses each row's offset account or 5890."
        )
        if len(statement_upload_chart_accounts) == 0:
            st.warning(
                "There are no active chart accounts yet. Add one under Onboarding before you post."
            )
        else:
            linked_account_numbers_for_template = (
                load_linked_chart_account_numbers_for_bank_template(
                    template_row_identifier
                )
            )
            template_chart_short_list_is_active = (
                len(linked_account_numbers_for_template) > 0
                and chart_link_restriction_warning is None
            )
            target_account_widget_key = (
                f"statement_upload_target_account_{template_row_identifier}"
            )
            if template_chart_short_list_is_active:
                st.markdown("##### Accounts you linked to this template")
                st.caption(
                    "Human: You set this list in Template Manager. "
                    "Click a row to choose the posting account for this upload."
                )
                linked_rows_sorted = sorted(
                    statement_upload_chart_accounts,
                    key=lambda chart_row: int(chart_row["account_number"]),
                )
                linked_target_option_labels = [
                    f"{chart_row['account_number']} — {chart_row['account_name']} "
                    f"({chart_row['account_category']})"
                    for chart_row in linked_rows_sorted
                ]
                linked_preview_dataframe = pandas.DataFrame(
                    [
                        {
                            "Account number": chart_row["account_number"],
                            "Account name": chart_row["account_name"],
                            "Category": chart_row["account_category"],
                        }
                        for chart_row in linked_rows_sorted
                    ]
                )
                linked_table_session_key = (
                    f"statement_upload_linked_table_{template_row_identifier}"
                )
                st.dataframe(
                    linked_preview_dataframe,
                    width="stretch",
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key=linked_table_session_key,
                )
                _statement_upload_apply_linked_table_selection_to_target_key(
                    linked_table_session_key=linked_table_session_key,
                    target_widget_session_key=target_account_widget_key,
                    linked_target_option_labels=linked_target_option_labels,
                )
            else:
                statement_labels = [
                    f"{row['account_number']} — {row['account_name']} ({row['account_category']})"
                    for row in statement_upload_chart_accounts
                ]
                st.selectbox(
                    "Target chart account",
                    options=statement_labels,
                    key=target_account_widget_key,
                    help=(
                        "Formal: Posting destination for this file. Human: Required before Post to ledger."
                    ),
                )
    else:
        st.markdown("##### Default posting account")
        st.caption(
            "Formal: bank_templates.linked_account_number. Human: The register leg posts here; "
            "offset legs follow your per-line classifications."
        )
        st.info(
            "This driver defaults to chart account number "
            f"**{effective_bound_linked_account}** for this upload."
        )

    upload_epoch_key = f"statement_upload_upload_epoch_{template_row_identifier}"
    upload_epoch = int(st.session_state.get(upload_epoch_key, 0))

    parsed_preview_dataframe = None
    transactions_for_post: list[dict] | None = None
    active_upload_metadata: str = ""

    uploaded_pdf_handle = None
    uploaded_csv_handle = None

    if ingest_kind == BUILT_IN_PDF_KIND:
        st.markdown("##### Bank statement PDF")
        uploaded_pdf_handle = st.file_uploader(
            "Statement PDF",
            type=["pdf"],
            key=f"statement_upload_pdf_{template_row_identifier}_{upload_epoch}",
            help=(
                "Formal: Audit source file for built_in_pdf drivers. Human: Only PDF when this driver is selected."
            ),
        )
        if uploaded_pdf_handle is not None:
            active_upload_metadata = str(uploaded_pdf_handle.name)
            try:
                pdf_bytes = uploaded_pdf_handle.getvalue()
                parsed_preview_dataframe = dataframe_from_built_in_pdf(
                    template_row=chosen_template_row,
                    pdf_bytes=pdf_bytes,
                )
                transactions_for_post = bank_statement_transactions_for_posting(
                    template_row=chosen_template_row,
                    pdf_bytes=pdf_bytes,
                )
            except ValueError as preview_error:
                st.warning(str(preview_error))

    elif ingest_kind == CSV_HEADERS_KIND:
        st.markdown("##### Bank statement CSV")
        uploaded_csv_handle = st.file_uploader(
            "Statement CSV",
            type=["csv"],
            key=f"statement_upload_csv_{template_row_identifier}_{upload_epoch}",
            help=(
                "Formal: Must match the column map you saved for this template name. Human: Export from your bank."
            ),
        )
        if uploaded_csv_handle is not None:
            active_upload_metadata = str(uploaded_csv_handle.name)
            try:
                csv_transaction_dicts = transaction_dicts_from_csv_template(
                    template_row=chosen_template_row,
                    csv_bytes=uploaded_csv_handle.getvalue(),
                )
                parsed_preview_dataframe = dataframe_from_csv_statement_transactions(
                    csv_transaction_dicts
                )
                transactions_for_post = csv_transaction_dicts
            except ValueError as preview_error:
                st.warning(str(preview_error))
    else:
        st.warning(f"Unknown ingest_kind `{ingest_kind}` — add support in the forge.")

    if parsed_preview_dataframe is not None and len(parsed_preview_dataframe) > 0:
        if transactions_for_post is None or len(transactions_for_post) == 0:
            st.warning("Parsed preview is empty — cannot classify or post.")
        else:
            classify_workbench_key = (
                f"statement_classify_enriched_{template_row_identifier}"
            )
            classify_source_marker_key = (
                f"statement_classify_source_{template_row_identifier}"
            )

            if st.session_state.get(classify_source_marker_key) != active_upload_metadata:
                st.session_state[classify_workbench_key] = (
                    enrich_statement_transactions_with_payee_offsets_using_default_session(
                        transaction_rows=transactions_for_post,
                    )
                )
                st.session_state[classify_source_marker_key] = active_upload_metadata

            enriched_transaction_rows: list[dict] = st.session_state[
                classify_workbench_key
            ]

            active_chart_rows = load_active_chart_accounts_for_template_picker()
            offset_option_labels, label_to_account_number = (
                build_offset_account_option_labels(
                    active_chart_account_rows=active_chart_rows,
                    clearing_account_number=STATEMENT_IMPORT_CLEARING_ACCOUNT_NUMBER,
                )
            )
            account_number_to_option_label = {
                account_number: label
                for label, account_number in label_to_account_number.items()
            }

            preview_row_dicts = statement_preview_rows_to_dataframe_rows(
                enriched_transaction_rows,
                label_for_account_number=account_number_to_option_label,
            )
            classification_preview_dataframe = pandas.DataFrame(preview_row_dicts)

            st.markdown("##### Review and classify (per line)")
            st.caption(
                "Human: Saved payee mappings fill first. 🟡 means a guess — confirm the offset account. "
                "Choosing clearing leaves the line on 5890 and forgets a saved mapping for that payee. "
                "Submit saves non-clearing choices for next time."
            )

            if classification_preview_dataframe["classification_status"].str.contains(
                "🟡", regex=False
            ).any():
                st.info(
                    "Some rows are **suggested** classifications — give them a quick look before you post."
                )

            edited_classification_dataframe = st.data_editor(
                classification_preview_dataframe,
                width="stretch",
                column_config={
                    "posting_date_iso": TextColumn("Posting date", disabled=True),
                    "payee": TextColumn("Payee", disabled=True),
                    "amount": TextColumn("Amount", disabled=True),
                    "reference": TextColumn("Reference", disabled=True),
                    "offset_account_label": SelectboxColumn(
                        "Offset account",
                        options=offset_option_labels,
                        required=True,
                    ),
                    "classification_status": TextColumn(
                        "Classification status", disabled=True
                    ),
                },
                hide_index=True,
                num_rows="fixed",
                key=f"statement_classify_editor_{template_row_identifier}",
            )

            entry_description_input = st.text_input(
                "Journal description (optional)",
                value=f"Statement import: {ingest_menu_display_label(chosen_template_row)}",
                key=f"statement_upload_entry_desc_{template_row_identifier}",
                help="Formal: journal_entries.entry_description. Human: One sentence for this whole file.",
            )

            target_account = _statement_upload_resolve_target_account_number(
                chosen_template_row=chosen_template_row,
                statement_upload_chart_accounts=statement_upload_chart_accounts,
                template_row_identifier=template_row_identifier,
            )
            post_disabled = target_account is None

            if st.button(
                "Post to ledger",
                type="primary",
                key=f"statement_upload_post_{template_row_identifier}",
                disabled=post_disabled,
                width="stretch",
            ):
                if post_disabled:
                    st.error("Pick a target account before posting.")
                else:
                    assert target_account is not None
                    try:
                        source_name = active_upload_metadata.strip() or "statement_upload"

                        liability_raw = chosen_template_row.get("is_liability", 0)
                        try:
                            is_liability_driver = bool(int(liability_raw))
                        except (TypeError, ValueError):
                            is_liability_driver = bool(liability_raw)

                        merged_posting_rows = merge_edited_preview_into_posting_rows(
                            enriched_transaction_rows=enriched_transaction_rows,
                            edited_preview_records=edited_classification_dataframe.to_dict(
                                "records"
                            ),
                        )
                        line_count = post_statement_import_transactions(
                            target_account_number=target_account,
                            source_metadata=str(source_name),
                            entry_description=str(entry_description_input),
                            is_liability_template=is_liability_driver,
                            transaction_rows=merged_posting_rows,
                        )
                        st.success(
                            f"Posted {len(merged_posting_rows)} transactions "
                            f"({line_count} ledger lines). "
                            "Saved payee mappings apply on your next upload."
                        )
                        st.session_state[upload_epoch_key] = upload_epoch + 1
                        st.session_state.pop(classify_workbench_key, None)
                        st.session_state.pop(classify_source_marker_key, None)
                        st.rerun()
                    except ValueError as post_error:
                        st.error(str(post_error))
                    except Exception as unexpected:
                        st.error(
                            "Post did not finish. Close other programs using the database, then retry. "
                            f"Details: {unexpected!s}"
                        )

    st.info(
        "Human: Drivers use your Template Manager maps (CSV) or built-in PDF code (e.g. Chase). "
        f"Selected: **{ingest_menu_display_label(chosen_template_row)}**."
    )
