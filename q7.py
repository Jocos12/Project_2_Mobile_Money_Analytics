# q7.py - Q7 shortest directed transfer route, every account on the route has role 'person'
#
# Usage:
#   python q7.py v1   -> baseline recursive SQL (UNION ALL, enumerates every walk)
#   python q7.py v2   -> improved SQL (UNION: deduplicates (account, depth) states)
#   python q7.py v3   -> v2 idea + search from both ends (meet in the middle)
# Both compare with Neo4j SHORTEST 1 (person filter applied DURING the search),
# for all 6 sets at bounds 4 and 6 (12 cases), then verify one Neo4j path per success.
# Results go to q7_results_<version>.csv
import csv
import sys
from time import perf_counter

from common import *

VERSION = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("v1", "v2", "v3") else "v1"
TIMEOUT = 60
BOUNDS = [4, 6]

SQL_TEMPLATE = """
WITH RECURSIVE walk(id, depth) AS (
  SELECT account_id, 0 FROM accounts
  WHERE account_id = %(src)s AND role = 'person'
  @@UNION@@
  SELECT t.receiver_id, w.depth + 1
  FROM walk w
  JOIN transfers t ON t.sender_id = w.id
  JOIN accounts a ON a.account_id = t.receiver_id AND a.role = 'person'
  WHERE w.depth < %(bound)s
)
SELECT MIN(depth) FROM walk WHERE id = %(dst)s
"""
# v3: search from BOTH ends (forward from src, backward from dst), each with
# deduplicated (account, depth) states, then join the two frontiers.
# forward depth = ceil(bound/2), backward depth = floor(bound/2)
SQL_V3 = """
WITH RECURSIVE fwd(id, depth) AS (
  SELECT account_id, 0 FROM accounts
  WHERE account_id = %(src)s AND role = 'person'
  UNION
  SELECT t.receiver_id, f.depth + 1
  FROM fwd f
  JOIN transfers t ON t.sender_id = f.id
  JOIN accounts a ON a.account_id = t.receiver_id AND a.role = 'person'
  WHERE f.depth < %(fd)s
), bwd(id, depth) AS (
  SELECT account_id, 0 FROM accounts
  WHERE account_id = %(dst)s AND role = 'person'
  UNION
  SELECT t.sender_id, b.depth + 1
  FROM bwd b
  JOIN transfers t ON t.receiver_id = b.id
  JOIN accounts a ON a.account_id = t.sender_id AND a.role = 'person'
  WHERE b.depth < %(bd)s
)
SELECT MIN(f.depth + b.depth) FROM fwd f JOIN bwd b ON b.id = f.id
"""

SQL = {
    "v1": SQL_TEMPLATE.replace("@@UNION@@", "UNION ALL"),
    "v2": SQL_TEMPLATE.replace("@@UNION@@", "UNION"),
    "v3": SQL_V3,
}[VERSION]


def pg_params(src, dst, bound):
    """Parameters accepted by all three SQL versions."""
    return {"src": src, "dst": dst, "bound": bound,
            "fd": (bound + 1) // 2, "bd": bound // 2}


def neo_len(bound):
    return f"""
    MATCH p = SHORTEST 1
      (a:Account {{account_id:$src, role:'person'}})
      ((:Account)-[:TRANSFER]->(m:Account WHERE m.role = 'person')){{1,{bound}}}
      (b:Account {{account_id:$dst}})
    RETURN length(p) AS len
    """


def neo_path(bound):
    return f"""
    MATCH p = SHORTEST 1
      (a:Account {{account_id:$src, role:'person'}})
      ((:Account)-[:TRANSFER]->(m:Account WHERE m.role = 'person')){{1,{bound}}}
      (b:Account {{account_id:$dst}})
    RETURN length(p) AS len, [n IN nodes(p) | n.account_id] AS ids
    """


def attempt(fn):
    t0 = perf_counter()
    try:
        return "OK", fn(), perf_counter() - t0
    except Exception as ex:
        msg = str(ex).lower()
        timed_out = any(w in msg for w in ("timeout", "timed out", "canceling statement", "terminated"))
        return ("TIMEOUT" if timed_out else "ERROR"), str(ex)[:150], perf_counter() - t0


def verify_path(ids, length):
    """Check roles, direction (stored transfers u->v) and length against PostgreSQL."""
    roles = dict(run_pg("SELECT account_id, role FROM accounts WHERE account_id = ANY(%(ids)s)",
                        {"ids": list(ids)}))
    all_person = all(roles.get(i) == "person" for i in ids)
    hops = []
    for u, v in zip(ids, ids[1:]):
        r = run_pg("SELECT transfer_id FROM transfers WHERE sender_id=%(u)s AND receiver_id=%(v)s LIMIT 1",
                   {"u": u, "v": v})
        hops.append(r[0][0] if r else None)
    return all_person, hops, (len(ids) - 1 == length)


if __name__ == "__main__":
    print(f"SQL version: {VERSION}")
    print(f"{'case':<10}{'PG len':>8}{'PG s':>8}{'Neo len':>9}{'Neo s':>8}  verdict")
    out = open(f"q7_results_{VERSION}.csv", "w", newline="")
    w = csv.writer(out)
    w.writerow(["version", "set", "src", "dst", "bound", "engine", "status", "seconds", "length"])
    successes = []

    for bound in BOUNDS:
        for k, (src, dst, day) in SETS.items():
            p = pg_params(src, dst, bound)
            pg_st, pg_rows, pg_t = attempt(lambda: run_pg(SQL, p, TIMEOUT))
            neo_st, neo_rows, neo_t = attempt(
                lambda: run_neo(neo_len(bound), {"src": src, "dst": dst}, TIMEOUT))
            pg_len = pg_rows[0][0] if pg_st == "OK" else None
            neo_len_v = neo_rows[0][0] if (neo_st == "OK" and neo_rows) else None

            w.writerow([VERSION, k, src, dst, bound, "PostgreSQL", pg_st, f"{pg_t:.3f}", pg_len])
            w.writerow([VERSION, k, src, dst, bound, "Neo4j", neo_st, f"{neo_t:.3f}", neo_len_v])
            out.flush()

            if pg_st == "OK" and neo_st == "OK":
                verdict = "OK" if pg_len == neo_len_v else "MISMATCH"
            else:
                verdict = f"PG {pg_st}, Neo4j {neo_st}"
            show = lambda v, st: ("none" if v is None else v) if st == "OK" else st
            print(f"{k} b={bound:<5}{show(pg_len, pg_st):>8}{pg_t:>8.1f}"
                  f"{show(neo_len_v, neo_st):>9}{neo_t:>8.1f}  {verdict}", flush=True)
            if neo_st == "OK" and neo_len_v is not None:
                successes.append((k, src, dst, bound))
    out.close()

    print("\nPath checks (one Neo4j path per successful case):")
    for k, src, dst, bound in successes:
        rows = run_neo(neo_path(bound), {"src": src, "dst": dst}, TIMEOUT)
        length, ids = rows[0]
        all_person, hops, len_ok = verify_path(ids, length)
        print(f"  {k} b={bound}: {' -> '.join(map(str, ids))}  (length {length})")
        print(f"      all person: {all_person} | transfer per hop: {hops} | length matches: {len_ok}")
    print(f"\nSaved q7_results_{VERSION}.csv")
