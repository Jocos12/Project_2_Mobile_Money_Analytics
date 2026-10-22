-- load.sql : bulk load (section 2.2). Run from the folder that holds the CSVs:
--   psql -U postgres -d momo -f load.sql
-- \copy reads the files on the client side, relative to the current folder.
\timing on
\echo '--- loading customers'
\copy customers FROM 'customers.csv' CSV HEADER
\echo '--- loading devices'
\copy devices FROM 'devices.csv' CSV HEADER
\echo '--- loading accounts'
\copy accounts FROM 'accounts.csv' CSV HEADER
\echo '--- loading account_devices'
\copy account_devices FROM 'account_devices.csv' CSV HEADER
\echo '--- loading transfers'
\copy transfers FROM 'transfers.csv' CSV HEADER
