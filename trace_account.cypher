// trace_account.cypher : section 3.3, follow the same account in Neo4j.
//   cypher-shell -u neo4j -p <password> --param "acct => 998" -f trace_account.cypher
MATCH (c:Customer)-[:OWNS]->(a:Account {account_id: $acct})-[u:USED_DEVICE]->(d:Device)
MATCH (a)-[t:TRANSFER]->(b:Account)
RETURN c.customer_id AS customer_id, c.region AS region,
       a.account_id AS account_id, a.role AS role,
       d.device_id AS device_id, d.access_type AS access_type,
       u.first_day AS first_day, u.last_day AS last_day, u.observations AS observations,
       t.transfer_id AS transfer_id, b.account_id AS receiver_id,
       t.occurred_at AS occurred_at,
       datetime({epochSeconds: t.occurred_at, timezone: 'Africa/Kigali'}) AS cat_time,
       t.amount_rwf AS amount_rwf
ORDER BY device_id, occurred_at
LIMIT 3;
