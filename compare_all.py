# compare_all.py - the 61-case correctness comparison (Q1..Q7), PostgreSQL vs Neo4j
# Cases: Q1 6, Q2 1, Q3 6, Q4 24, Q5 6, Q6 6, Q7 12 = 61
# Needs q1.py ... q7.py in the same folder. Q7 uses the selected SQL (v3, both ends).
# Run:  python compare_all.py     (takes several minutes because of Q2)
import csv
from time import perf_counter

from common import *
import q1, q2, q3, q4, q5, q6, q7

TIMEOUT = 180
Q7_SQL = q7.SQL_V3  # selected SQL version for Q7 (meet in the middle)


def q2_rows(rows):
    return [(str(d), int(n), int(s)) for d, n, s in rows]


def q7_pg_rows(rows):
    return [] if rows[0][0] is None else [(int(rows[0][0]),)]


def build_cases():
    cases = []  # (question, label, pg_fn, neo_fn)
    for k, (acct, dst, day) in SETS.items():
        s, e = hour_window(day)
        p = {"account": acct, "start": s, "end": e}
        cases.append(("Q1", k, lambda p=p: run_pg(q1.SQL, p, TIMEOUT),
                      lambda p=p: run_neo(q1.CYP, p, TIMEOUT)))
    cases.append(("Q2", "month",
                  lambda: q2_rows(run_pg(q2.SQL, None, TIMEOUT)),
                  lambda: q2_rows(run_neo(q2.CYP, None, TIMEOUT))))
    for k, (acct, dst, day) in SETS.items():
        p = {"account": acct}
        cases.append(("Q3", k, lambda p=p: run_pg(q3.SQL, p, TIMEOUT),
                      lambda p=p: run_neo(q3.CYP, p, TIMEOUT)))
    for depth in (4, 6, 8, 10):
        for k, (acct, dst, day) in SETS.items():
            cases.append(("Q4", f"{k} d={depth}",
                          lambda a=acct, d=depth: run_pg(q4.SQL, {"account": a, "depth": d}, TIMEOUT),
                          lambda a=acct, d=depth: run_neo(q4.cypher(d), {"account": a}, TIMEOUT)))
    for qname, mod in (("Q5", q5), ("Q6", q6)):
        for k, (acct, dst, day) in SETS.items():
            s, e = hour_window(day)
            p = {"account": acct, "start": s, "end": e}
            cases.append((qname, k, lambda p=p, m=mod: run_pg(m.SQL, p, TIMEOUT),
                          lambda p=p, m=mod: run_neo(m.CYP, p, TIMEOUT)))
    for bound in (4, 6):
        for k, (src, dst, day) in SETS.items():
            cases.append(("Q7", f"{k} b={bound}",
                          lambda s=src, d=dst, b=bound: q7_pg_rows(
                              run_pg(Q7_SQL, q7.pg_params(s, d, b), TIMEOUT)),
                          lambda s=src, d=dst, b=bound: run_neo(
                              q7.neo_len(b), {"src": s, "dst": d}, TIMEOUT)))
    return cases


def attempt(fn):
    t0 = perf_counter()
    try:
        return "OK", [tuple(r) for r in fn()], perf_counter() - t0
    except Exception as ex:
        msg = str(ex).lower()
        timed_out = any(w in msg for w in ("timeout", "timed out", "canceling statement", "terminated"))
        return ("TIMEOUT" if timed_out else "ERROR"), [], perf_counter() - t0


if __name__ == "__main__":
    cases = build_cases()
    assert len(cases) == 61, len(cases)
    summary = {}
    out = open("compare_status.csv", "w", newline="")
    w = csv.writer(out)
    w.writerow(["n", "question", "case", "pg_status", "neo_status", "pg_rows", "neo_rows",
                "pg_seconds", "neo_seconds", "result"])
    mismatches = []

    print(f"{'#':>2} {'Q':<3} {'case':<9}{'PG rows':>8}{'Neo rows':>9}  result")
    for n, (q, label, pg_fn, neo_fn) in enumerate(cases, 1):
        pg_st, pg_rows, pg_t = attempt(pg_fn)
        neo_st, neo_rows, neo_t = attempt(neo_fn)
        if pg_st == "OK" and neo_st == "OK":
            result = "OK" if norm(pg_rows) == norm(neo_rows) else "MISMATCH"
        else:
            result = f"PG {pg_st} / Neo4j {neo_st}"
        if result != "OK":
            mismatches.append((q, label, result, pg_rows, neo_rows))
        s = summary.setdefault(q, [0, 0])
        s[0] += 1
        s[1] += result == "OK"
        w.writerow([n, q, label, pg_st, neo_st, len(pg_rows), len(neo_rows),
                    f"{pg_t:.3f}", f"{neo_t:.3f}", result])
        out.flush()
        print(f"{n:>2} {q:<3} {label:<9}{len(pg_rows):>8}{len(neo_rows):>9}  {result}", flush=True)
    out.close()

    print("\nSummary by question (matching / total):")
    for q, (total, ok) in summary.items():
        print(f"  {q}: {ok}/{total}")
    total_ok = sum(v[1] for v in summary.values())
    print(f"  ALL: {total_ok}/61")

    if mismatches:
        print("\nProblems:")
        for q, label, result, pg_rows, neo_rows in mismatches:
            print(f"  {q} {label}: {result}")
            print(f"     PG   : {pg_rows[:3]}")
            print(f"     Neo4j: {neo_rows[:3]}")

    # Q7: lengths were compared above; now validate one Neo4j path per successful case
    print("\nQ7 supporting paths (roles, stored transfer per hop, length):")
    valid = checked = 0
    for bound in (4, 6):
        for k, (src, dst, day) in SETS.items():
            rows = run_neo(q7.neo_path(bound), {"src": src, "dst": dst}, TIMEOUT)
            if not rows:
                continue
            length, ids = rows[0]
            all_person, hops, len_ok = q7.verify_path(ids, length)
            ok = all_person and all(h is not None for h in hops) and len_ok
            checked += 1
            valid += ok
            print(f"  {k} b={bound}: length {length}, {'valid' if ok else 'INVALID'}")
    print(f"  {valid}/{checked} paths valid")
    print("\nSaved compare_status.csv")
