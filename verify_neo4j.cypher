// verify_neo4j.cypher : section 3.2 checks.
// Run: cypher-shell -u neo4j -p <password> -f verify_neo4j.cypher

// node counts (expected 228000 / 248000 / 228600, total 704600)
MATCH (c:Customer) RETURN 'Customer' AS label, count(c) AS n
UNION ALL
MATCH (a:Account) RETURN 'Account' AS label, count(a) AS n
UNION ALL
MATCH (d:Device) RETURN 'Device' AS label, count(d) AS n;

// relationship counts (expected 248000 / 285600 / 20003300, total 20536900)
MATCH ()-[r:OWNS]->() RETURN 'OWNS' AS type, count(r) AS n
UNION ALL
MATCH ()-[r:USED_DEVICE]->() RETURN 'USED_DEVICE' AS type, count(r) AS n
UNION ALL
MATCH ()-[r:TRANSFER]->() RETURN 'TRANSFER' AS type, count(r) AS n;

// account roles (expected agent 2000, merchant 6000, person 240000)
MATCH (a:Account) RETURN a.role AS role, count(*) AS n ORDER BY role;

// exactly one owner per account (expected one row: owners=1, accounts=248000)
MATCH (a:Account)
OPTIONAL MATCH (c:Customer)-[:OWNS]->(a)
WITH a, count(c) AS owners
RETURN owners, count(*) AS accounts ORDER BY owners;

// transfer audit (expected count 20003300, min 1788235200, max 1790798399, sum 231482327870)
MATCH ()-[t:TRANSFER]->()
RETURN count(t) AS transfer_count,
       min(t.occurred_at) AS min_occurred_at,
       max(t.occurred_at) AS max_occurred_at,
       sum(t.amount_rwf)  AS sum_amount_rwf;

// unique transfer_id (expected total = distinct_ids = 20003300)
MATCH ()-[t:TRANSFER]->()
RETURN count(t) AS total, count(DISTINCT t.transfer_id) AS distinct_ids;
