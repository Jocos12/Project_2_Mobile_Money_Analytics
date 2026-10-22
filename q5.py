# q5.py - Q5 rapid onward payments: 3 directed transfers through 4 distinct accounts
import csv

from common import *

SQL = """
SELECT t1.transfer_id, t2.transfer_id, t3.transfer_id, t3.receiver_id
FROM transfers t1
JOIN transfers t2 ON t2.sender_id = t1.receiver_id
JOIN transfers t3 ON t3.sender_id = t2.receiver_id
WHERE t1.sender_id = %(account)s
  AND t1.occurred_at >= %(start)s AND t1.occurred_at < %(end)s
  AND t2.occurred_at >  t1.occurred_at AND t2.occurred_at <= t1.occurred_at + 600
  AND t3.occurred_at >  t2.occurred_at AND t3.occurred_at <= t2.occurred_at + 600
  AND 90  * t1.amount_rwf::bigint <= 100 * t2.amount_rwf::bigint
  AND 100 * t2.amount_rwf::bigint <= 105 * t1.amount_rwf::bigint
  AND 90  * t2.amount_rwf::bigint <= 100 * t3.amount_rwf::bigint
  AND 100 * t3.amount_rwf::bigint <= 105 * t2.amount_rwf::bigint
  AND t1.sender_id   <> t1.receiver_id
  AND t1.sender_id   <> t2.receiver_id
  AND t1.sender_id   <> t3.receiver_id
  AND t1.receiver_id <> t2.receiver_id
  AND t1.receiver_id <> t3.receiver_id
  AND t2.receiver_id <> t3.receiver_id
ORDER BY t1.transfer_id, t2.transfer_id, t3.transfer_id, t3.receiver_id
"""

CYP = """
MATCH (a:Account {account_id:$account})-[t1:TRANSFER]->(b:Account)
      -[t2:TRANSFER]->(c:Account)-[t3:TRANSFER]->(d:Account)
WHERE t1.occurred_at >= $start AND t1.occurred_at < $end
  AND t2.occurred_at >  t1.occurred_at AND t2.occurred_at <= t1.occurred_at + 600
  AND t3.occurred_at >  t2.occurred_at AND t3.occurred_at <= t2.occurred_at + 600
  AND 90  * t1.amount_rwf <= 100 * t2.amount_rwf AND 100 * t2.amount_rwf <= 105 * t1.amount_rwf
  AND 90  * t2.amount_rwf <= 100 * t3.amount_rwf AND 100 * t3.amount_rwf <= 105 * t2.amount_rwf
  AND a <> b AND a <> c AND a <> d AND b <> c AND b <> d AND c <> d
RETURN t1.transfer_id AS t1, t2.transfer_id AS t2, t3.transfer_id AS t3, d.account_id AS final_receiver
ORDER BY t1, t2, t3, final_receiver
"""

DETAIL = """
SELECT transfer_id, sender_id, receiver_id,
       to_char(to_timestamp(occurred_at) AT TIME ZONE 'Africa/Kigali', 'YYYY-MM-DD HH24:MI:SS'),
       amount_rwf
FROM transfers WHERE transfer_id = ANY(%(ids)s) ORDER BY occurred_at
"""


def show_chain(ids, title="Chain"):
    """Print stored transfer details (CAT times, amounts, % of previous amount)."""
    rows = {r[0]: r for r in run_pg(DETAIL, {"ids": list(ids)})}
    print(f"\n{title}:")
    prev = None
    for i in ids:
        tid, s, r, ts, amt = rows[i]
        pct = "" if prev is None else f"  ({100 * amt / prev:.2f}% of previous)"
        print(f"  transfer {tid}: {s} -> {r}  {ts} CAT  {amt:,} RWF{pct}")
        prev = amt


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
        for r in pg_r:
            all_rows.append((k, acct) + r)
            if first is None:
                first = (k, r)

    print("\nChains found (set, review account, t1, t2, t3, final receiver):")
    for row in all_rows[:12]:
        print("  ", row)
    if first:
        show_chain(first[1][:3], f"Example chain from set {first[0]}")
    else:
        print("\nNo chain found in any set.")

    with open("q5_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["set", "review_account", "t1", "t2", "t3", "final_receiver"])
        w.writerows(all_rows)
    print("\nFull output saved to q5_results.csv")
