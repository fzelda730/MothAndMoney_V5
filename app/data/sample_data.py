"""
Sample placeholder data for Moth and Money V4.
All data is fictional and for UI demonstration only.
"""

# ============================================================
# STUDIO PROFILE
# ============================================================

STUDIO = {
    "artist_name":      "Julian Voss",
    "studio_name":      "The Verdant Atelier",
    "bio":              "A focused space for organic sculpture and ecological installations, "
                        "balancing fine art with financial integrity.",
    "email":            "julian@theatelier.com",
    "tax_id":           "XX-882104-Z",
    "base_currency":    "USD",
    "fiscal_year_start":"January",
    "default_tax_rate": 8.5,
    "accounting_method":"Cash",
}

# ============================================================
# BANK ACCOUNTS
# ============================================================

BANK_ACCOUNTS = [
    {
        "id":           "acct-001",
        "account_name": "Main Studio Checking",
        "bank_name":    "Chase Bank",
        "masked":       "4421",
        "account_type": "checking",
        "icon":         "account_balance",
        "icon_color":   "#154212",
        "accent":       "#154212",
        "beginning_balance": 28450.00,
        "total_debits":      -4220.15,
        "total_credits":     12850.50,
        "ending_balance":    37080.35,
    },
    {
        "id":           "acct-002",
        "account_name": "Emergency Reserve",
        "bank_name":    "Chase Bank",
        "masked":       "8834",
        "account_type": "savings",
        "icon":         "savings",
        "icon_color":   "#154212",
        "accent":       "#a1d494",
        "beginning_balance": 15000.00,
        "total_debits":      0.00,
        "total_credits":     1500.00,
        "ending_balance":    16500.00,
    },
    {
        "id":           "acct-003",
        "account_name": "Artist Rewards Visa",
        "bank_name":    "Amex",
        "masked":       "1002",
        "account_type": "credit_card",
        "icon":         "credit_card",
        "icon_color":   "#71151d",
        "accent":       "#ffb3b1",
        "beginning_balance": -1240.20,
        "total_debits":      -2140.00,
        "total_credits":     1500.00,
        "ending_balance":    -1880.20,
    },
    {
        "id":           "acct-004",
        "account_name": "Petty Cash Box",
        "bank_name":    "Cash",
        "masked":       "—",
        "account_type": "cash",
        "icon":         "payments",
        "icon_color":   "#636262",
        "accent":       "#e5e2e1",
        "beginning_balance": 450.00,
        "total_debits":      -85.50,
        "total_credits":     0.00,
        "ending_balance":    364.50,
    },
]

# Dashboard summary stats
DASHBOARD_STATS = {
    "total_portfolio_value": 142850.00,
    "portfolio_trend":       12.5,
    "available_liquidity":   34200.00,
    "pending_commissions":   12400.00,    # placeholder until AR is designed
    "studio_income":         8420.00,
    "studio_income_label":   "Settled this month",
    "material_costs":        2140.00,
    "material_costs_label":  "Supplies & Studio Rent",
}

TAX_PROVISION = {
    "quarterly_sales":   24100.00,
    "reserve_amount":    6025.00,
    "tax_rate":          8.5,
}

# ============================================================
# LEDGER TRANSACTIONS
# ============================================================

LEDGER_TRANSACTIONS = [
    {
        "date":         "Oct 12, 2023",
        "payee":        "The Canvas Depot",
        "sub":          "Store #4412 · Studio Supplies",
        "coa":          "5120-001",
        "debit":        459.00,
        "credit":       None,
        "status":       "cleared",
        "flagged":      False,
    },
    {
        "date":         "Oct 10, 2023",
        "payee":        "Client Retainer: V. Gogh",
        "sub":          "Q4 Landscape Commission",
        "coa":          "4010-005",
        "debit":        None,
        "credit":       2500.00,
        "status":       "cleared",
        "flagged":      False,
    },
    {
        "date":         "Oct 08, 2023",
        "payee":        "Studio Rental Corp",
        "sub":          "Monthly Fixed Rent",
        "coa":          "6180-100",
        "debit":        1800.00,
        "credit":       None,
        "status":       "cleared",
        "flagged":      False,
    },
    {
        "date":         "Oct 05, 2023",
        "payee":        "Freight Logistics Intl",
        "sub":          "Shipping Paris Exhibition",
        "coa":          "5280-012",
        "debit":        870.50,
        "credit":       None,
        "status":       "pending",
        "flagged":      False,
    },
    {
        "date":         "Oct 04, 2023",
        "payee":        "Misc Cash Deposit",
        "sub":          "Uncategorized Transaction",
        "coa":          None,
        "debit":        None,
        "credit":       620.50,
        "status":       "flagged",
        "flagged":      True,
    },
]

LEDGER_SUMMARY = {
    "beginning_balance": 12450.00,
    "total_debits":      3120.50,
    "total_credits":     3120.50,
    "ending_balance":    12450.00,
    "is_balanced":       True,
}

# ============================================================
# CHART OF ACCOUNTS (for display)
# ============================================================

CHART_OF_ACCOUNTS = [
    # Assets
    {"number": "1100", "name": "Cash",                          "type": "Asset",   "subtype": "Current Asset"},
    {"number": "1200", "name": "Accounts Receivable",           "type": "Asset",   "subtype": "Current Asset"},
    {"number": "1300", "name": "Art Inventory",                 "type": "Asset",   "subtype": "Inventory"},
    {"number": "1400", "name": "Digital Assets",                "type": "Asset",   "subtype": "Current Asset"},
    {"number": "1600", "name": "Equipment",                     "type": "Asset",   "subtype": "Fixed Asset"},
    # Liabilities
    {"number": "2100", "name": "Accounts Payable",              "type": "Liability","subtype": "Current Liability"},
    {"number": "2200", "name": "Credit Card Payable",           "type": "Liability","subtype": "Current Liability"},
    {"number": "2300", "name": "Tax Reserve",                   "type": "Liability","subtype": "Current Liability"},
    # Equity
    {"number": "3100", "name": "Owner Equity",                  "type": "Equity",  "subtype": "Owner's Equity"},
    {"number": "3200", "name": "Retained Earnings",             "type": "Equity",  "subtype": "Retained Earnings"},
    # Income
    {"number": "4100", "name": "Gallery Sales (Direct)",        "type": "Income",  "subtype": "Operating Income"},
    {"number": "4200", "name": "Online Atelier / Digital Shop", "type": "Income",  "subtype": "Operating Income"},
    {"number": "4300", "name": "Consultancy & Curatorial",      "type": "Income",  "subtype": "Operating Income"},
    {"number": "4400", "name": "Commission Income",             "type": "Income",  "subtype": "Operating Income"},
    # Expenses
    {"number": "5100", "name": "Studio Rent & Utilities",       "type": "Expense", "subtype": "Overhead"},
    {"number": "5200", "name": "Material Supplies",             "type": "Expense", "subtype": "Cost of Goods"},
    {"number": "5300", "name": "Marketing & Exhibition Fees",   "type": "Expense", "subtype": "Marketing"},
    {"number": "5400", "name": "Professional Staff",            "type": "Expense", "subtype": "Payroll"},
    {"number": "5500", "name": "Software & Subscriptions",      "type": "Expense", "subtype": "Overhead"},
    {"number": "5600", "name": "Shipping & Logistics",          "type": "Expense", "subtype": "Cost of Goods"},
    {"number": "5700", "name": "Travel & Dining",               "type": "Expense", "subtype": "Travel"},
]

# ============================================================
# REPORTS DATA
# ============================================================

PL_INCOME = [
    {"account": "Gallery Sales (Direct)",        "debit": None,        "credit": 285000.00, "total": 285000.00},
    {"account": "Online Atelier Subscriptions",  "debit": None,        "credit": 92450.00,  "total": 92450.00},
    {"account": "Consultancy & Curatorial",      "debit": None,        "credit": 35400.00,  "total": 35400.00},
]

PL_EXPENSES = [
    {"account": "Studio Rent & Utilities",       "debit": 72000.00,    "credit": None,       "total": 72000.00},
    {"account": "Material Supplies (Moth Silk)", "debit": 42150.00,    "credit": None,       "total": 42150.00},
    {"account": "Marketing & Exhibition Fees",   "debit": 38060.00,    "credit": None,       "total": 38060.00},
    {"account": "Professional Staff (3 FTE)",    "debit": 32000.00,    "credit": None,       "total": 32000.00},
]

PL_SUMMARY = {
    "gross_revenue":       412850.00,
    "revenue_vs_ly":       12.4,
    "operating_expenses":  184210.00,
    "net_profit":          228640.00,
    "generated_on":        "October 24, 2024 at 14:32 PST",
    "fiscal_year":         "Fiscal Year 2024 • Jan 01 - Dec 31",
    "net_profit_note":     "Your highest margin since the gallery opening in 2021.",
}

QUARTERLY_PERFORMANCE = [
    {"quarter": "Q1 2024", "revenue": 54200,  "projected": False},
    {"quarter": "Q2 2024", "revenue": 48150,  "projected": False},
    {"quarter": "Q3 2024", "revenue": 62800,  "projected": False},
    {"quarter": "Q4 2024", "revenue": 63490,  "projected": True},
]

# Balance Sheet (simplified cash-basis)
BALANCE_SHEET = {
    "assets": [
        {"account": "Cash — Main Studio Checking", "amount": 37080.35},
        {"account": "Cash — Emergency Reserve",    "amount": 16500.00},
        {"account": "Cash — Petty Cash Box",       "amount": 364.50},
        {"account": "Art Inventory (at cost)",      "amount": 48000.00},
        {"account": "Equipment (at cost)",          "amount": 12400.00},
    ],
    "liabilities": [
        {"account": "Credit Card Payable — Amex",  "amount": 1880.20},
        {"account": "Tax Reserve",                  "amount": 6025.00},
    ],
}

# Trial Balance (for Reports tab)
TRIAL_BALANCE_REPORT = [
    {"bank_account": "1020-4492-001", "coa": "1100 - Cash",         "debits": 12450.00, "credits": None},
    {"bank_account": "1020-4492-001", "coa": "1200 - Receivables",  "debits": 4200.50,  "credits": None},
    {"bank_account": "9901-3321-882", "coa": "2100 - Payables",     "debits": None,     "credits": 8100.00},
    {"bank_account": "9901-3321-882", "coa": "3100 - Equity",       "debits": None,     "credits": 5000.00},
    {"bank_account": "1020-4492-001", "coa": "4100 - Sales",        "debits": None,     "credits": 3550.50},
]

# ============================================================
# IMPORT TEMPLATES
# ============================================================

IMPORT_TEMPLATES = [
    {
        "id":            "tmpl-001",
        "name":          "Chase Standard CSV",
        "type":          "bank_statement",
        "accounts":      ["Main Studio Checking ****4421", "Emergency Reserve ****8834"],
        "column_map": {
            "date":             "Transaction Date",
            "transaction_type": "Type",
            "payee":            "Description",
            "amount":           "Amount (USD)",
            "chart_of_account": "Account Code",
            "description":      "Note",
        },
    },
    {
        "id":            "tmpl-002",
        "name":          "Amex Business Gold",
        "type":          "credit_card",
        "accounts":      ["Artist Rewards Visa ****1002"],
        "column_map": {
            "date":             "Date",
            "payee":            "Description",
            "account":          "Account",
            "amount":           "Amount",
            "description":      "Note",
        },
    },
]

# Sample CC live preview rows
CC_PREVIEW_ROWS = [
    {"date": "Oct 24, 2023", "payee": "Adobe Systems Inc.",  "sub": "Creative Cloud Subscription", "account": "Software & Apps", "amount": -54.99},
    {"date": "Oct 22, 2023", "payee": "Amazon Web Services", "sub": "Cloud Infrastructure",         "account": "Hosting Services","amount": -1240.12},
    {"date": "Oct 21, 2023", "payee": "Starbucks #4829",     "sub": "Travel & Dining",              "account": "Meals & Ent.",    "amount": -12.45},
    {"date": "Oct 19, 2023", "payee": "Delta Airlines",      "sub": "NY to SF Flight",              "account": "Travel",          "amount": -489.00},
]

# Sample bank statement live preview rows
BANK_PREVIEW_ROWS = [
    {"date": "10/24/2023", "type": "DEBIT",  "payee": "Paper Supply Co",     "amount": -246.12, "coa": "Materials"},
    {"date": "10/25/2023", "type": "CREDIT", "payee": "Client Deposit: Smith","amount": 1500.00, "coa": "Consulting"},
    {"date": "10/26/2023", "type": "DEBIT",  "payee": "Studio Rent",          "amount": -2000.00,"coa": "Operations"},
]

# ============================================================
# TRIAL BALANCE IMPORT (Onboarding)
# ============================================================

TRIAL_BALANCE_IMPORT_PREVIEW = [
    {"bank_account": "1020-4492-001", "coa": "1100 - Cash",        "debits": 12450.00, "credits": None,     "error": False},
    {"bank_account": "1020-4492-001", "coa": "1200 - Receivables", "debits": 4200.50,  "credits": None,     "error": False},
    {"bank_account": "9901-3321-882", "coa": "2100 - Payables",    "debits": None,     "credits": 8100.00,  "error": False},
    {"bank_account": "9901-3321-882", "coa": "3100 - Equity",      "debits": None,     "credits": 5000.00,  "error": False},
    {"bank_account": "ERR-404-NULL",  "coa": "Unmapped Header",    "debits": 0.00,     "credits": 0.00,     "error": True},
    {"bank_account": "1020-4492-001", "coa": "4100 - Sales",       "debits": None,     "credits": 3550.50,  "error": False},
]

TRIAL_BALANCE_TOTALS = {
    "total_debits":  16650.50,
    "total_credits": 16650.50,
    "is_balanced":   True,
    "variance":      0.00,
}
