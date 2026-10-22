# q1.py - Q1 account activity: outgoing count and total RWF in the hour
from common import *

SQL = """SELECT COUNT(*), COALESCE(SUM(amount_rwf), 0)
         FROM transfers
         WHERE sender_id = %(account)s
           AND occurred_at >= %(start)s AND occurred_at < %(end)s"""

CYP = """MATCH (a:Account {account_id:$account})-[t:TRANSFER]->()
         WHERE t.occurred_at >= $start AND t.occurred_at < $end
         RETURN count(t) AS n, coalesce(sum(t.amount_rwf), 0) AS total"""

if __name__ == "__main__":
    for k, (acct, dest, day) in SETS.items():
        s, e = hour_window(day)
        p = {"account": acct, "start": s, "end": e}
        pg_r = run_pg(SQL, p)
        neo_r = run_neo(CYP, p)
        status = "OK" if norm(pg_r) == norm(neo_r) else "MISMATCH"
        print(k, acct, "PG:", pg_r, "Neo4j:", neo_r, status)
