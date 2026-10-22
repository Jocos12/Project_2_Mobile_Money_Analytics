-- trace_account.sql : section 3.3, follow one account in PostgreSQL.
--   psql -U postgres -d momo -v acct=998 -f trace_account.sql
SELECT c.customer_id, c.region,
       a.account_id, a.role,
       ad.device_id, d.access_type, ad.first_day, ad.last_day, ad.observations,
       t.transfer_id, t.receiver_id,
       t.occurred_at,
       to_timestamp(t.occurred_at) AT TIME ZONE 'Africa/Kigali' AS cat_time,
       t.amount_rwf
FROM accounts a
JOIN customers       c  ON c.customer_id = a.customer_id
JOIN account_devices ad ON ad.account_id = a.account_id
JOIN devices         d  ON d.device_id   = ad.device_id
JOIN transfers       t  ON t.sender_id   = a.account_id
WHERE a.account_id = :acct
ORDER BY ad.device_id, t.occurred_at
LIMIT 3;
