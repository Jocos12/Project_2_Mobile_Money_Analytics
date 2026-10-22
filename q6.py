# q6.py - Q6 circular payments: 3-8 transfers starting and ending at the review account
# Needs q5.py in the same folder (reuses show_chain).
import csv

from common import *
from q5 import show_chain

SQL = """
WITH RECURSIVE chain(cur, ids, first_t, last_t, last_amt, n) AS (
  SELECT t.receiver_id, ARRAY[t.transfer_id], t.occurred_at, t.occurred_at,
         t.amount_rwf::bigint, 1
  FROM transfers t
  WHERE t.sender_id = %(account)s
    AND t.occurred_at >= %(start)s AND t.occurred_at < %(end)s
  UNION ALL
  SELECT t.receiver_id, c.ids || t.transfer_id, c.first_t, t.occurred_at,
         t.amount_rwf::bigint, c.n + 1
  FROM chain c
  JOIN transfers t ON t.sender_id = c.cur
  WHERE c.cur <> %(account)s                 -- stop at the first return
    AND c.n < 8
    AND t.occurred_at >  c.last_t
    AND t.occurred_at <  %(end)s
    AND t.occurred_at - c.first_t <= 1800
    AND 90  * c.last_amt <= 100 * t.amount_rwf::bigint
    AND 100 * t.amount_rwf::bigint <= 105 * c.last_amt
)
SELECT ids, n FROM chain
WHERE cur = %(account)s AND n BETWEEN 3 AND 8
ORDER BY ids
"""

CYP = """
MATCH p = (a:Account {account_id:$account})-[ts:TRANSFER*3..8]->(a)
WHERE all(r IN ts WHERE r.occurred_at >= $start AND r.occurred_at < $end)
  AND all(n IN nodes(p)[1..-1] WHERE n <> a)
  AND all(i IN range(1, size(ts) - 1) WHERE
        ts[i].occurred_at > ts[i-1].occurred_at
        AND 90  * ts[i-1].amount_rwf <= 100 * ts[i].amount_rwf
        AND 100 * ts[i].amount_rwf   <= 105 * ts[i-1].amount_rwf)
  AND ts[size(ts) - 1].occurred_at - ts[0].occurred_at <= 1800
RETURN [r IN ts | r.transfer_id] AS ids, size(ts) AS n
ORDER BY ids
"""

if __name__ == "__main__":
    all_rows = []
    print(f"{'set':<4}{'account':>8}{'PG rows':>9}{'Neo4j rows':>12}  status")
    first = None
    for k, (acct, dest, day) in SETS.items():
        s, e = hour_window(day)
        p = {"account": acct, "start": s, "end": e}
        pg_r = [tuple(r) for r in run_pg(SQL, p)]
        neo_r = [tuple(r) for r in run_neo(CYP, p)]
        ok = norm(pg_r) == norm(neo_r)
        print(f"{k:<4}{acct:>8}{len(pg_r):>9}{len(neo_r):>12}  {'OK' if ok else 'MISMATCH'}")
        for ids, n in pg_r:
            all_rows.append((k, acct, n, ids))
            if first is None:
                first = (k, acct, ids)

    print("\nCycles found (set, review account, length, transfer IDs):")
    for row in all_rows[:12]:
        print("  ", row)
    if first:
        show_chain(first[2], f"Example cycle from set {first[0]} (account {first[1]})")
    else:
        print("\nNo cycle found in any set.")

    with open("q6_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["set", "review_account", "length", "transfer_ids"])
        for k, acct, n, ids in all_rows:
            w.writerow([k, acct, n, " ".join(map(str, ids))])
    print("\nFull output saved to q6_results.csv")
