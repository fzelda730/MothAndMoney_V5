"""
MOTH AND MONEY — BANK PDF PARSERS (LOGIC PACKAGE)
/logic/pdf_parsers/

Formal:  One module per built_in_parser_key for bank statement PDF layouts.
Human:   Code ships the “template” for PDFs; Template Manager stays CSV-only.

Accounting Rule:
    Parsers return normalized transaction dicts for statement import posting only.
"""

from __future__ import annotations
