"""
MOTH AND MONEY — TEMPLATE MANAGER (UI)
/ui/template_manager.py

Formal:  Streamlit surface for defining bank_templates CSV column maps.
Human:   Point Date / Payee / Amount at your sample file — chart account is chosen on Statement Upload.

Accounting Rule:
    Rule 11 — no SQL or structural validation here; logic.bank_templates only.
"""

from __future__ import annotations

import pandas
import streamlit as st

from logic.bank_templates import (
    BUILT_IN_PDF_KIND,
    CSV_HEADERS_KIND,
    build_bank_csv_template_preview_dataframe,
    describe_linked_chart_accounts_for_bank_template_catalog,
    ingest_menu_display_label,
    list_bank_templates_for_ingest_menu,
    load_active_chart_accounts_for_template_picker,
    load_linked_chart_account_numbers_for_bank_template,
    read_csv_header_labels_from_bytes,
    save_linked_chart_accounts_for_bank_template,
    save_user_csv_bank_template,
)

_TEMPLATE_MANAGER_UPLOAD_EPOCH_KEY = "template_manager_upload_epoch"


def _chart_row_display_label(chart_row: dict) -> str:
    """
    Formal:  One-line label for multiselects (same shape as Statement Upload target picker).
    Human:   Account number first so sorting and scanning stay easy.

    Accounting Rule:
        N/A — UI label only.
    """
    return (
        f"{chart_row['account_number']} — {chart_row['account_name']} "
        f"({chart_row['account_category']})"
    )


def _reset_template_manager_form_after_successful_save() -> None:
    """
    Formal:  Clears draft widgets so the next run shows a blank mapping form.
    Human:   After you save, the sample file and picks drop away so you are not stuck on the old CSV.

    Accounting Rule:
        N/A — UI state only; bank_templates row is already persisted.
    """
    st.session_state.pop("template_manager_sample_signature", None)
    st.session_state.pop("template_manager_sample_headers", None)
    for widget_state_key in (
        "template_manager_template_name",
        "template_manager_date_col_pick",
        "template_manager_payee_col_pick",
        "template_manager_amount_col_pick",
        "template_manager_reference_col_pick",
        "template_manager_is_liability",
    ):
        st.session_state.pop(widget_state_key, None)
    st.session_state[_TEMPLATE_MANAGER_UPLOAD_EPOCH_KEY] = int(
        st.session_state.get(_TEMPLATE_MANAGER_UPLOAD_EPOCH_KEY, 0)
    ) + 1


def render_template_manager_page() -> None:
    """
    Formal:  Template Manager: sample CSV upload, header mapping, save to bank_templates.
    Human:   Train the forge once per bank export shape — then Ingest can reuse it.

    Accounting Rule:
        Rule 9 — formal field names in labels; one short human sentence under each cluster.
    """
    if st.session_state.pop("template_manager_show_saved_banner", False):
        st.success(
            "Saved this template to bank_templates. It will show up on Statement Upload."
        )

    st.title("Template Manager")
    st.caption(
        "Formal: bank_templates CSV column maps (one row per export shape). "
        "Human: Name this after the bank or file layout — you pick which chart account receives "
        "each statement on Statement Upload; optional short lists below cover CSV and built-in PDF drivers."
    )

    template_display_name = st.text_input(
        "Template name",
        key="template_manager_template_name",
        help=(
            "Formal: bank_templates.name. Human: One name per export shape — it appears in the "
            "Ingest list; reuse it for every account that uses that bank’s CSV."
        ),
    )

    upload_widget_epoch = int(st.session_state.get(_TEMPLATE_MANAGER_UPLOAD_EPOCH_KEY, 0))
    uploaded_sample_file = st.file_uploader(
        "Sample bank CSV",
        type=["csv"],
        key=f"template_manager_sample_csv_{upload_widget_epoch}",
        help=(
            "Formal: header row only is read for column names. Human: Use a small export "
            "that looks like the real statement."
        ),
    )

    sample_csv_header_labels: list[str] = []
    if uploaded_sample_file is not None:
        file_signature = (uploaded_sample_file.name, uploaded_sample_file.size)
        if st.session_state.get("template_manager_sample_signature") != file_signature:
            st.session_state.template_manager_sample_signature = file_signature
            try:
                st.session_state.template_manager_sample_headers = (
                    read_csv_header_labels_from_bytes(uploaded_sample_file.getvalue())
                )
            except ValueError as parse_error:
                st.error(str(parse_error))
                st.session_state.pop("template_manager_sample_headers", None)
        sample_csv_header_labels = st.session_state.get("template_manager_sample_headers", [])
    else:
        st.session_state.pop("template_manager_sample_signature", None)
        st.session_state.pop("template_manager_sample_headers", None)

    if len(sample_csv_header_labels) > 0:
        st.markdown("##### Sample file headers")
        st.caption(
            "Formal: First-row column labels from your CSV. Human: Match Date, Payee, Amount; "
            "Reference is optional."
        )
        header_preview_dataframe = pandas.DataFrame(
            [{"Column name": column_label} for column_label in sample_csv_header_labels]
        )
        st.dataframe(header_preview_dataframe, width="stretch", hide_index=True)

        date_column_label = st.selectbox(
            "Date column",
            options=sample_csv_header_labels,
            key="template_manager_date_col_pick",
            help="Formal: bank_templates.date_col. Human: Which header holds the transaction date?",
        )
        payee_column_label = st.selectbox(
            "Payee column",
            options=sample_csv_header_labels,
            key="template_manager_payee_col_pick",
            help="Formal: bank_templates.payee_col. Human: Which header names the merchant or transfer?",
        )
        amount_column_label = st.selectbox(
            "Amount column",
            options=sample_csv_header_labels,
            key="template_manager_amount_col_pick",
            help="Formal: bank_templates.amount_col. Human: Which header holds the debit/credit amount?",
        )
        _reference_not_mapped_display = "— Not mapped —"
        reference_select_options = [_reference_not_mapped_display] + sample_csv_header_labels
        reference_column_display_pick = st.selectbox(
            "Reference column (optional)",
            options=reference_select_options,
            key="template_manager_reference_col_pick",
            help=(
                "Formal: bank_templates.reference_col (memo, check number, or bank transaction id). "
                "Human: Skip this if your export has no separate reference column."
            ),
        )
        reference_column_value = (
            ""
            if reference_column_display_pick == _reference_not_mapped_display
            else reference_column_display_pick
        )
        is_liability_template = st.checkbox(
            "Mark as liability / credit card style (formal: bank_templates.is_liability)",
            value=False,
            key="template_manager_is_liability",
            help=(
                "Human: Check if this template is for a card or loan bucket — logic can use it "
                "later for sign conventions during ingest."
            ),
        )

        date_pick_stripped = str(date_column_label).strip()
        payee_pick_stripped = str(payee_column_label).strip()
        amount_pick_stripped = str(amount_column_label).strip()
        mapping_ready_for_preview = (
            len(date_pick_stripped) > 0
            and len(payee_pick_stripped) > 0
            and len(amount_pick_stripped) > 0
            and len({date_pick_stripped, payee_pick_stripped, amount_pick_stripped}) == 3
        )
        if mapping_ready_for_preview and uploaded_sample_file is not None:
            st.markdown("##### Sample rows from your mapping")
            st.caption(
                "Formal: First five data rows projected through date_col, payee_col, amount_col, "
                "and reference_col when set. "
                "Human: If dates, names, amounts, or references look wrong, re-pick columns before you save."
            )
            try:
                mapping_preview_dataframe = build_bank_csv_template_preview_dataframe(
                    uploaded_sample_file.getvalue(),
                    date_col=date_column_label,
                    payee_col=payee_column_label,
                    amount_col=amount_column_label,
                    reference_col=reference_column_value,
                )
                st.dataframe(
                    mapping_preview_dataframe,
                    width="stretch",
                    hide_index=True,
                )
            except ValueError as preview_error:
                st.warning(str(preview_error))

        if st.button(
            "Save Template",
            type="primary",
            width="stretch",
            key="template_manager_save_template_button",
        ):
            try:
                save_user_csv_bank_template(
                    template_name=template_display_name,
                    date_col=date_column_label,
                    payee_col=payee_column_label,
                    amount_col=amount_column_label,
                    reference_col=reference_column_value,
                    is_liability=is_liability_template,
                )
                st.session_state["template_manager_show_saved_banner"] = True
                _reset_template_manager_form_after_successful_save()
                st.rerun()
            except ValueError as human_friendly_error:
                st.error(str(human_friendly_error))
            except Exception as unexpected_error:
                st.error(
                    "Save did not finish. Check that the database is not open elsewhere. "
                    f"Details: {unexpected_error!s}"
                )

    st.divider()
    st.markdown("### Saved templates")
    st.caption(
        "Formal: Current bank_templates rows. Human: Linked posting accounts shows chart buckets "
        "saved for Statement Upload (or “any active account” when none). Built-in PDF rows ship with the app."
    )
    try:
        template_catalog_rows = list_bank_templates_for_ingest_menu()
    except Exception as load_error:
        st.warning(f"Could not load bank_templates: {load_error!s}")
        template_catalog_rows = []

    if len(template_catalog_rows) == 0:
        st.info("No templates yet — save a CSV map above or rely on built-in seeds after init.")
    else:
        catalog_table = pandas.DataFrame(
            [
                {
                    "Display name": ingest_menu_display_label(row),
                    "ingest_kind": row["ingest_kind"],
                    "Linked posting accounts": describe_linked_chart_accounts_for_bank_template_catalog(
                        int(row["id"])
                    ),
                    "linked_account_number": (
                        str(int(row["linked_account_number"]))
                        if row["linked_account_number"] is not None
                        else "—"
                    ),
                    "date_col": row["date_col"] or "—",
                    "payee_col": row["payee_col"] or "—",
                    "amount_col": row["amount_col"] or "—",
                    "reference_col": row.get("reference_col") or "—",
                    "is_liability": row["is_liability"],
                    "built_in_parser_key": row["built_in_parser_key"] or "—",
                }
                for row in template_catalog_rows
            ]
        )
        st.dataframe(catalog_table, width="stretch", hide_index=True)

        templates_with_chart_short_list: list[dict] = [
            template_catalog_row
            for template_catalog_row in template_catalog_rows
            if str(template_catalog_row.get("ingest_kind") or "")
            in (CSV_HEADERS_KIND, BUILT_IN_PDF_KIND)
        ]
        if len(templates_with_chart_short_list) > 0:
            st.markdown("##### Optional: chart account short list (CSV maps and built-in PDF)")
            st.caption(
                "Formal: bank_template_chart_links. Human: Choose which chart buckets Statement "
                "Upload offers for each ingest driver — useful when one CSV shape or one PDF parser "
                "feeds several accounts. Leave all unchecked and save to allow every active account."
            )
            try:
                template_manager_chart_rows = load_active_chart_accounts_for_template_picker()
            except Exception as chart_load_error:
                st.warning(
                    "Could not load chart accounts for linking. "
                    f"Details: {chart_load_error!s}"
                )
                template_manager_chart_rows = []

            if len(template_manager_chart_rows) == 0:
                st.info(
                    "Add active accounts under Onboarding before you can attach a short list."
                )
            else:
                account_labels_ordered: list[str] = [
                    _chart_row_display_label(chart_row) for chart_row in template_manager_chart_rows
                ]
                account_number_by_label: dict[str, int] = {
                    _chart_row_display_label(chart_row): int(chart_row["account_number"])
                    for chart_row in template_manager_chart_rows
                }

                for template_row in templates_with_chart_short_list:
                    template_primary_key = int(template_row["id"])
                    expander_label = (
                        f"{ingest_menu_display_label(template_row)} — chart accounts for posting"
                    )
                    with st.expander(expander_label, expanded=False):
                        linked_account_numbers = load_linked_chart_account_numbers_for_bank_template(
                            template_primary_key
                        )
                        linked_number_set = set(linked_account_numbers)
                        default_labels = sorted(
                            [
                                _chart_row_display_label(chart_row)
                                for chart_row in template_manager_chart_rows
                                if int(chart_row["account_number"]) in linked_number_set
                            ]
                        )
                        epoch_state_key = f"template_manager_chart_link_epoch_{template_primary_key}"
                        link_widget_epoch = int(st.session_state.get(epoch_state_key, 0))
                        selected_account_labels = st.multiselect(
                            "Accounts allowed when this template is selected on Statement Upload",
                            options=account_labels_ordered,
                            default=default_labels,
                            key=(
                                "template_manager_chart_link_multi_"
                                f"{template_primary_key}_{link_widget_epoch}"
                            ),
                            help=(
                                "Human: Pick the cash or card buckets that use this driver; "
                                "empty selection saved means no restriction."
                            ),
                        )
                        if st.button(
                            "Save chart links",
                            key=(
                                "template_manager_chart_link_save_"
                                f"{template_primary_key}_{link_widget_epoch}"
                            ),
                            width="stretch",
                        ):
                            try:
                                chosen_account_numbers = [
                                    account_number_by_label[label_text]
                                    for label_text in selected_account_labels
                                ]
                                save_linked_chart_accounts_for_bank_template(
                                    bank_template_identifier=template_primary_key,
                                    chart_account_numbers=chosen_account_numbers,
                                )
                                st.session_state[epoch_state_key] = link_widget_epoch + 1
                                st.success("Saved chart links for this template.")
                                st.rerun()
                            except ValueError as friendly_template_error:
                                st.error(str(friendly_template_error))
                            except Exception as unexpected_link_error:
                                st.error(
                                    "Save did not finish. Check that the database is not locked. "
                                    f"Details: {unexpected_link_error!s}"
                                )
