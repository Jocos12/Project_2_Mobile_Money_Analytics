# q3.py - Q3 shared devices: other accounts on the same device with overlapping days
import csv

from common import *

SQL = """SELECT b.account_id, b.device_id, d.access_type,
                GREATEST(a.first_day, b.first_day) AS overlap_start,
                LEAST(a.last_day, b.last_day) AS overlap_end
         FROM account_devices a
         JOIN account_devices b ON b.device_id = a.device_id AND b.account_id <> a.account_id
         JOIN devices d ON d.device_id = a.device_id
         WHERE a.account_id = %(account)s
           AND GREATEST(a.first_day, b.first_day) <= LEAST(a.last_day, b.last_day)
         ORDER BY b.account_id, b.device_id"""

CYP = """MATCH (a:Account {account_id:$account})-[u1:USED_DEVICE]->(d:Device)<-[u2:USED_DEVICE]-(b:Account)
         WHERE b <> a
         WITH b, d,
              CASE WHEN u1.first_day > u2.first_day THEN u1.first_day ELSE u2.first_day END AS s,
              CASE WHEN u1.last_day  < u2.last_day  THEN u1.last_day  ELSE u2.last_day  END AS e
         WHERE s <= e
         RETURN b.account_id AS other_account, d.device_id AS device_id,
                d.access_type AS access_type, s AS overlap_start, e AS overlap_end
         ORDER BY other_account, device_id"""

if __name__ == "__main__":
    all_rows = []
    print(f"{'set':<4}{'account':>8}{'PG rows':>9}{'Neo4j rows':>12}  status")
    for k, (acct, dest, day) in SETS.items():
        p = {"account": acct}
        pg_r = [tuple(r) for r in run_pg(SQL, p)]
        neo_r = [tuple(r) for r in run_neo(CYP, p)]
        ok = norm(pg_r) == norm(neo_r)
        print(f"{k:<4}{acct:>8}{len(pg_r):>9}{len(neo_r):>12}  {'OK' if ok else 'MISMATCH'}")
        for r in pg_r:
            all_rows.append((k, acct) + r)

    print()
    print("First rows per set (account, device, type, overlap start-end):")
    shown = {}
    for row in all_rows:
        k = row[0]
        shown[k] = shown.get(k, 0) + 1
        if shown[k] <= 3:
            print(f"  {k}  acct {row[1]}  ->  other {row[2]}, device {row[3]}, {row[4]}, days {row[5]}-{row[6]}")

    with open("q3_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["set", "review_account", "other_account", "device_id",
                    "access_type", "overlap_start", "overlap_end"])
        w.writerows(all_rows)
    print("\nFull output saved to q3_results.csv")
