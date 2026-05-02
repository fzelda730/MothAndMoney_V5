# Moth and Money V5 — UI and logic architecture

Formal overview of how **`/ui`** and **`/logic`** relate, and how Trial Balance bytes move into **`moth_and_money.db`**.

---

## Module dependency (class-style diagram)

Python here is mostly **functions in modules**, not classes. Boxes below stand for **modules**; arrows mean “imports and calls into.”

```mermaid
classDiagram
direction TB

class system_init_py {
  <<ui/system_init.py>>
  render_system_initialization_page()
}
class admin_settings_py {
  <<ui/admin_settings.py>>
  render_admin_settings_page()
}
class database_reset_section_py {
  <<ui/database_reset_section.py>>
  render_database_reset_danger_zone_section()
}
class trial_balance_py {
  <<ui/trial_balance.py>>
  render_trial_balance_page()
}
class dashboard_py {
  <<ui/dashboard.py>>
  render_dashboard_page()
}

class opening_trial_balance_import_py {
  <<logic/opening_trial_balance_import.py>>
  read_trial_balance_dataframe_from_csv_bytes()
  import_opening_trial_balance_from_csv_bytes()
}
class tb_processor_py {
  <<logic/tb_processor.py>>
  build_proposed_trial_balance_editor_dataframe()
  commit_proposed_trial_balance_from_editor_dataframe()
  proposal_debit_and_credit_totals()
  proposal_is_balanced_for_commit()
}
class seeding_py {
  <<logic/seeding.py>>
  seed_chart_of_accounts_from_trial_balance_dataframe()
}
class initial_funding_py {
  <<logic/initial_funding.py>>
  post_opening_balance_from_trial_balance_dataframe()
  compute_opening_trial_balance_totals_from_dataframe()
}

system_init_py ..> database_reset_section_py : uses
system_init_py ..> opening_trial_balance_import_py : read CSV
system_init_py ..> tb_processor_py : build, audit, commit

admin_settings_py ..> database_reset_section_py : Danger Zone
admin_settings_py ..> sqlite_lifecycle : count rows

database_reset_section_py ..> sqlite_lifecycle : reset file

trial_balance_py ..> connection_py : read reports
dashboard_py ..> connection_py : read dashboard

tb_processor_py ..> seeding_py : seed chart on commit
tb_processor_py ..> initial_funding_py : _parse_currency…
tb_processor_py ..> connection_py : journal + ledger insert

opening_trial_balance_import_py ..> seeding_py : legacy import
opening_trial_balance_import_py ..> initial_funding_py : legacy post

class sqlite_lifecycle {
  <<database/sqlite_lifecycle.py>>
}
class connection_py {
  <<database/connection.py>>
}
```

**Note:** `import_opening_trial_balance_from_csv_bytes` is a **legacy** path (CLI / older callers). System Initialization uses **`tb_processor.commit_proposed_trial_balance_from_editor_dataframe`** after `st.data_editor`.

---

## Data flow: upload → SQLite (System Initialization)

```mermaid
flowchart LR
  subgraph ui [ui]
    upload[st.file_uploader]
    editor[st.data_editor]
    commit[Commit opening Trial Balance]
  end

  subgraph logic [logic]
    read[read_trial_balance_dataframe_from_csv_bytes]
    raw[Raw DataFrame]
    build[build_proposed_trial_balance_editor_dataframe]
    grid[Proposed chart and Debit or Credit grid]
    gate[proposal_is_balanced_for_commit]
    commitFn[commit_proposed_trial_balance_from_editor_dataframe]
    seed[seed_chart_of_accounts_from_trial_balance_dataframe]
    jour[INSERT journal_entries]
    led[INSERT ledger_entries]
  end

  subgraph database [database]
    db[(moth_and_money.db)]
  end

  upload --> read --> raw --> build --> grid
  grid --> editor
  editor --> gate
  gate --> commit
  commit --> commitFn
  commitFn --> seed --> db
  commitFn --> jour --> led --> db
```

---

## Chambers (constitutional)

| Layer | Role |
|--------|------|
| **`/ui`** | Streamlit layout, `st.file_uploader`, `st.data_editor`, buttons, captions. |
| **`/logic`** | CSV normalization (when needed), keyword mapping, `Decimal` totals, orchestration of chart + opening entry. |
| **`/database`** | Engine, sessions, schema bootstrap, SQLite file reset, raw SQL for journal/ledger in `tb_processor` commit path. |

---

*Generated for Moth and Money V5; update this file when modules or import paths change.*
