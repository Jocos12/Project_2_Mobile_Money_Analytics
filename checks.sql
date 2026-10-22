-- checks.sql : verification for section 2.2. Compare with audit.json from capture.py.
--   psql -U postgres -d momo -f checks.sql

\echo '=== row counts (expected 228000 / 248000 / 228600 / 285600 / 20003300)'
SELECT 'customers' AS tbl, count(*) FROM customers
UNION ALL SELECT 'accounts', count(*) FROM accounts
UNION ALL SELECT 'devices', count(*) FROM devices
UNION ALL SELECT 'account_devices', count(*) FROM account_devices
UNION ALL SELECT 'transfers', count(*) FROM transfers;

\echo '=== transfer audit (expected min 1788235200, max 1790798399, sum 231482327870)'
SELECT count(*) AS transfer_count,
       min(occurred_at) AS min_occurred_at,
       max(occurred_at) AS max_occurred_at,
       sum(amount_rwf)  AS sum_amount_rwf
FROM transfers;

\echo '=== account roles (expected person 240000, merchant 6000, agent 2000)'
SELECT role, count(*) FROM accounts GROUP BY role ORDER BY role;

\echo '=== constraints (convalidated must be t)'
SELECT conrelid::regclass AS tbl, conname, contype, convalidated
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
ORDER BY 1, 2;

\echo '=== indexes'
SELECT tablename, indexname, indexdef
FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2;

\echo '=== sizes in GB (1 GB = 1,000,000,000 bytes)'
SELECT relname,
       round(pg_table_size(oid)/1e9, 3)    AS table_gb,
       round(pg_indexes_size(oid)/1e9, 3)  AS index_gb
FROM pg_class
WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'
ORDER BY relname;
SELECT round(pg_database_size(current_database())/1e9, 3) AS database_gb;
