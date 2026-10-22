-- post_load.sql : foreign keys, indexes, ANALYZE (section 2.2). Timed separately from loading.
--   psql -U postgres -d momo -f post_load.sql
\timing on
SET maintenance_work_mem = '1GB';   -- session only; record it in the report

\echo '--- foreign keys'
ALTER TABLE accounts        ADD CONSTRAINT fk_accounts_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
ALTER TABLE account_devices ADD CONSTRAINT fk_ad_account        FOREIGN KEY (account_id)  REFERENCES accounts(account_id);
ALTER TABLE account_devices ADD CONSTRAINT fk_ad_device         FOREIGN KEY (device_id)   REFERENCES devices(device_id);
ALTER TABLE transfers       ADD CONSTRAINT fk_tr_sender         FOREIGN KEY (sender_id)   REFERENCES accounts(account_id);
ALTER TABLE transfers       ADD CONSTRAINT fk_tr_receiver       FOREIGN KEY (receiver_id) REFERENCES accounts(account_id);

\echo '--- indexes'
CREATE INDEX idx_accounts_customer ON accounts (customer_id, account_id);
CREATE INDEX idx_ad_device         ON account_devices (device_id, account_id);
CREATE INDEX idx_tr_sender   ON transfers (sender_id, occurred_at)
    INCLUDE (receiver_id, amount_rwf, transfer_id);
CREATE INDEX idx_tr_receiver ON transfers (receiver_id, occurred_at)
    INCLUDE (sender_id, amount_rwf, transfer_id);
CREATE INDEX idx_tr_time_brin ON transfers USING BRIN (occurred_at);

\echo '--- analyze'
ANALYZE;
