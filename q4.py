# q4.py - Q4 ownership and device network (distinct accounts by owner region)
#
# Usage:
#   python q4.py            -> depths 4 6 8 10 (all 6 sets, both engines)
#   python q4.py 4 6        -> only depths 4 and 6
#   python q4.py 8 10       -> only depths 8 and 10
#   python q4.py plot       -> count-versus-depth chart from q4_results.csv
#
# Results are APPENDED to q4_results.csv (delete it to start over).
import csv
import os
import sys
from time import perf_counter

from common import *

TIMEOUT = 60  # seconds per query, as required for measured runs

SQL = """
WITH RECURSIVE edges(sk, si, dk, di) AS (
  SELECT 'Customer', customer_id, 'Account', account_id FROM accounts
  UNION ALL
  SELECT 'Account', account_id, 'Customer', customer_id FROM accounts
  UNION ALL
  SELECT 'Account', account_id, 'Device', device_id FROM account_devices
  UNION ALL
  SELECT 'Device', device_id, 'Account', account_id FROM account_devices
), walk(kind, id, depth) AS (
  SELECT 'Account', %(account)s::integer, 0
  UNION
  SELECT e.dk, e.di, w.depth + 1
  FROM walk w JOIN edges e ON e.sk = w.kind AND e.si = w.id
  WHERE w.depth < %(depth)s
)
SELECT c.region, COUNT(DISTINCT w.id)
FROM walk w
JOIN accounts a ON a.account_id = w.id
JOIN customers c ON c.customer_id = a.customer_id
WHERE w.kind = 'Account' AND w.id <> %(account)s
GROUP BY c.region
ORDER BY c.region
"""


def cypher(depth):
    # variable-length bounds cannot be parameters in Cypher
    return f"""
    MATCH (a:Account {{account_id:$account}})
    MATCH (a)-[:OWNS|USED_DEVICE*1..{depth}]-(b:Account)
    WHERE b <> a
    WITH DISTINCT b
    MATCH (c:Customer)-[:OWNS]->(b)
    RETURN c.region AS region, count(b) AS accounts
    ORDER BY region
    """


def attempt(fn):
    t0 = perf_counter()
    try:
        rows = fn()
        return "OK", rows, perf_counter() - t0
    except Exception as ex:  # timeouts, memory errors, ...
        msg = str(ex).lower()
        timed_out = any(w in msg for w in ("timeout", "timed out", "canceling statement", "terminated"))
        return ("TIMEOUT" if timed_out else "ERROR"), str(ex)[:150], perf_counter() - t0


def total(rows):
    return sum(int(r[1]) for r in rows)


def show_path():
    """One supporting 4-link path from Neo4j (first set that has one)."""
    q = """MATCH p = (a:Account {account_id:$account})-[:OWNS|USED_DEVICE*4]-(b:Account)
           WHERE b <> a RETURN p LIMIT 1"""
    for k, (acct, dest, day) in SETS.items():
        with neo().session(database="neo4j") as s:
            rec = s.run(q, {"account": acct}, timeout=TIMEOUT).single()
        if rec:
            p = rec["p"]
            parts = []
            for i, n in enumerate(p.nodes):
                label = next(iter(n.labels))
                key = {"Customer": "customer_id", "Account": "account_id", "Device": "device_id"}[label]
                parts.append(f"{label} {n[key]}")
                if i < len(p.relationships):
                    parts.append(f"-[{p.relationships[i].type}]-")
            print(f"\nSupporting path (set {k}, 4 links):")
            print("  " + " ".join(parts))
            return
    print("\nNo 4-link path found for any set.")


def plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = {}
    with open("q4_results.csv") as f:
        for r in csv.DictReader(f):
            if r["status"] == "OK" and r["accounts"] != "":
                key = (r["set"], int(r["depth"]), r["engine"])
                data[key] = data.get(key, 0) + int(r["accounts"])
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for k in SETS:
        pts = sorted((d, v) for (s, d, e), v in data.items() if s == k and e == "PostgreSQL")
        if pts:
            ax.plot(*zip(*pts), marker="o", label=f"Set {k} (PostgreSQL)")
        pts = sorted((d, v) for (s, d, e), v in data.items() if s == k and e == "Neo4j")
        if pts:
            ax.scatter(*zip(*pts), marker="x", s=80, color="black")
    ax.set_xlabel("Maximum links (depth)")
    ax.set_ylabel("Distinct accounts reached")
    ax.set_xticks([4, 6, 8, 10])
    ax.set_yscale("log")
    ax.set_title("Q4: accounts reached vs depth (x = Neo4j completed result)")
    ax.legend()
    fig.tight_layout()
    fig.savefig("q4_count_vs_depth.png", dpi=150)
    print("Saved q4_count_vs_depth.png")


if __name__ == "__main__":
    if sys.argv[1:] == ["plot"]:
        plot()
        sys.exit()

    depths = [int(x) for x in sys.argv[1:]] or [4, 6, 8, 10]
    new_file = not os.path.exists("q4_results.csv")
    out = open("q4_results.csv", "a", newline="")
    w = csv.writer(out)
    if new_file:
        w.writerow(["set", "account", "depth", "engine", "status", "seconds", "region", "accounts"])

    print(f"{'case':<9}{'PG total':>10}{'PG s':>8}{'Neo total':>11}{'Neo s':>8}  verdict")
    for depth in depths:
        for k, (acct, dest, day) in SETS.items():
            pg_status, pg_rows, pg_t = attempt(
                lambda: [tuple(r) for r in run_pg(SQL, {"account": acct, "depth": depth}, TIMEOUT)])
            neo_status, neo_rows, neo_t = attempt(
                lambda: [tuple(r) for r in run_neo(cypher(depth), {"account": acct}, TIMEOUT)])

            for eng, st, rows, t in (("PostgreSQL", pg_status, pg_rows, pg_t),
                                     ("Neo4j", neo_status, neo_rows, neo_t)):
                if st == "OK":
                    for region, n in rows:
                        w.writerow([k, acct, depth, eng, st, f"{t:.3f}", region, int(n)])
                    if not rows:
                        w.writerow([k, acct, depth, eng, st, f"{t:.3f}", "", 0])
                else:
                    w.writerow([k, acct, depth, eng, st, f"{t:.3f}", "", ""])
            out.flush()

            if pg_status == "OK" and neo_status == "OK":
                verdict = "OK" if norm(pg_rows) == norm(neo_rows) else "MISMATCH"
            elif pg_status == "OK":
                verdict = f"Neo4j {neo_status}"
            else:
                verdict = f"PG {pg_status}; Neo4j {neo_status}"
            pg_tot = total(pg_rows) if pg_status == "OK" else "-"
            neo_tot = total(neo_rows) if neo_status == "OK" else "-"
            print(f"{k} d={depth:<4}{pg_tot:>10}{pg_t:>8.1f}{neo_tot:>11}{neo_t:>8.1f}  {verdict}", flush=True)

    out.close()
    show_path()
    print("\nResults appended to q4_results.csv")
