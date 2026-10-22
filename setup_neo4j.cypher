// setup_neo4j.cypher : unique constraints + range index (section 3.2)
// Run: cypher-shell -u neo4j -p <password> -f setup_neo4j.cypher
CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE;
CREATE CONSTRAINT account_id_unique  IF NOT EXISTS FOR (a:Account)  REQUIRE a.account_id  IS UNIQUE;
CREATE CONSTRAINT device_id_unique   IF NOT EXISTS FOR (d:Device)   REQUIRE d.device_id   IS UNIQUE;
CREATE RANGE INDEX transfer_occurred_at IF NOT EXISTS FOR ()-[t:TRANSFER]-() ON (t.occurred_at);
CALL db.awaitIndexes(3600);
SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties;
SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, state, populationPercent;
