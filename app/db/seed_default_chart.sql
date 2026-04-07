-- ============================================================
-- Optional default studio row + Creatives chart (no transactions).
-- Run after schema.sql when you want starter COA without seed_demo.sql.
-- Idempotent: safe to re-run.
-- ============================================================

INSERT INTO studio_profile (artist_name, studio_name)
SELECT 'Julian Voss', 'The Digital Atelier'
WHERE NOT EXISTS (SELECT 1 FROM studio_profile LIMIT 1);

INSERT INTO chart_of_accounts (account_number, account_name, account_type, account_subtype) VALUES
('1100', 'Cash',                         'asset',   'current_asset'),
('1200', 'Accounts Receivable',          'asset',   'current_asset'),
('1300', 'Art Inventory',                'asset',   'inventory'),
('1400', 'Digital Assets',               'asset',   'current_asset'),
('1500', 'Prepaid Expenses',             'asset',   'current_asset'),
('1600', 'Equipment',                    'asset',   'fixed_asset'),
('2100', 'Accounts Payable',             'liability','current_liability'),
('2200', 'Credit Card Payable',          'liability','current_liability'),
('2300', 'Tax Reserve',                  'liability','current_liability'),
('2400', 'Deferred Revenue',             'liability','current_liability'),
('3100', 'Owner Equity',                 'equity',  'owners_equity'),
('3200', 'Retained Earnings',            'equity',  'retained_earnings'),
('4100', 'Gallery Sales (Direct)',       'income',  'operating_income'),
('4200', 'Online Atelier / Digital Shop','income',  'operating_income'),
('4300', 'Consultancy & Curatorial',     'income',  'operating_income'),
('4400', 'Commission Income',            'income',  'operating_income'),
('4500', 'Licensing & Royalties',        'income',  'operating_income'),
('4900', 'Other Income',                 'income',  'other_income'),
('5100', 'Studio Rent & Utilities',      'expense', 'overhead'),
('5200', 'Material Supplies',            'expense', 'cost_of_goods'),
('5300', 'Marketing & Exhibition Fees',  'expense', 'marketing'),
('5400', 'Professional Staff',           'expense', 'payroll'),
('5500', 'Software & Subscriptions',     'expense', 'overhead'),
('5600', 'Shipping & Logistics',         'expense', 'cost_of_goods'),
('5700', 'Travel & Dining',              'expense', 'travel'),
('5800', 'Photography & Documentation',  'expense', 'marketing'),
('5900', 'Other Expenses',               'expense', 'other_expense')
ON CONFLICT (account_number) DO NOTHING;
