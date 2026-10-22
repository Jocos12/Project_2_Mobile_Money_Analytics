# bench.py - Section 6.2 timing of 21 fixed cases per engine (+ 6.3 revised Q7 cases)
#
# Run ONE database service at a time (stop the other one first):
#   python bench.py pg          -> PostgreSQL, 21 cases (Q7 uses the ORIGINAL SQL v1)
#   python bench.py pg-v3       -> PostgreSQL, the 4 revised Q7 cases (SQL v3)
#   python bench.py neo         -> Neo4j, 21 cases
#   python bench.py summary     -> median/min/max in ms and PostgreSQL/Neo4j ratio
#   python bench.py check       -> compare the saved answers of both engines (outside the timer)
#   python bench.py plans pg    -> EXPLAIN (ANALYZE, BUFFERS) for Q2, Q4 B d10, Q7 B b6 (v1, v2, v3)
#   python bench.py plans neo   -> PROFILE for Q2, Q4 B d10, Q7 B b6
#
# Per case: 3 untimed warm-ups (180 s limit), then 5 measured runs (60 s limit).
# If the FIRST warm-up already fails (timeout/error), the measured runs are recorded
# as not run, with a note (a 60 s query cannot succeed if it exceeded 180 s).
# Re-running a command resumes: cases that already have 5 measured rows are skipped.
# Delete bench_raw.csv and bench_answers.json to start from scratch.
import csv
import json
import os
import sys
from datetime import datetime
from statistics import median
from time import perf_counter

from common import *
import q1, q2, q3, q4, q5, q6, q7

WARMUPS, RUNS = 3, 5
WARM_TIMEOUT, RUN_TIMEOUT = 180, 60
RAW, ANSWERS, SUMMARY = "bench_raw.csv", "bench_answers.json", "bench_summary.csv"
SEL = ["B", "E"]
Q7_V1 = q7.SQL_TEMPLATE.replace("@@UNION@@", "UNION ALL")
Q7_V2 = q7.SQL_TEMPLATE.replace("@@UNION@@", "UNION")
Q7_V3 = q7.SQL_V3


def q2_rows(rows):
    return [(str(d), int(n), int(s)) for d, n, s in rows]


def q7_pg_rows(rows):
    return [] if rows[0][0] is None else [(int(rows[0][0]),)]


def build_cases(q7_sql):
    cs = []

    def add(q, label, params, pg, neo, post_pg=list, post_neo=list):
        cs.append(dict(id=f"{q}-{label}", q=q, label=label,
                       params=json.dumps(params, default=str),
                       pg=pg, neo=neo, post_pg=post_pg, post_neo=post_neo))

    for k in SEL:
        acct, dst, day = SETS[k]
        s, e = hour_window(day)
        p = {"set": k, "account": acct, "start": s, "end": e}
        add("Q1", k, p, lambda t, p=p: run_pg(q1.SQL, p, t), lambda t, p=p: run_neo(q1.CYP, p, t))
    add("Q2", "month", {}, lambda t: run_pg(q2.SQL, None, t), lambda t: run_neo(q2.CYP, None, t),
        q2_rows, q2_rows)
    for k in SEL:
        acct, dst, day = SETS[k]
        p = {"set": k, "account": acct}
        add("Q3", k, p, lambda t, p=p: run_pg(q3.SQL, p, t), lambda t, p=p: run_neo(q3.CYP, p, t))
    for k in SEL:
        acct, dst, day = SETS[k]
        for depth in (4, 6, 8, 10):
            p = {"set": k, "account": acct, "depth": depth}
            add("Q4", f"{k}-d{depth}", p,
                lambda t, p=p: run_pg(q4.SQL, p, t),
                lambda t, p=p: run_neo(q4.cypher(p["depth"]), {"account": p["account"]}, t))
    for qn, mod in (("Q5", q5), ("Q6", q6)):
        for k in SEL:
            acct, dst, day = SETS[k]
            s, e = hour_window(day)
            p = {"set": k, "account": acct, "start": s, "end": e}
            add(qn, k, p, lambda t, p=p, m=mod: run_pg(m.SQL, p, t),
                lambda t, p=p, m=mod: run_neo(m.CYP, p, t))
    for bound in (4, 6):
        for k in SEL:
            src, dst, day = SETS[k]
            p = {"set": k, "src": src, "dst": dst, "bound": bound}
            add("Q7", f"{k}-b{bound}", p,
                lambda t, p=p: run_pg(q7_sql, q7.pg_params(p["src"], p["dst"], p["bound"]), t),
                lambda t, p=p: run_neo(q7.neo_len(p["bound"]), {"src": p["src"], "dst": p["dst"]}, t),
                q7_pg_rows, list)
    return cs


def classify(ex):
    msg = str(ex).lower()
    timed_out = any(w in msg for w in ("timeout", "timed out", "canceling statement", "terminated"))
    return "TIMEOUT" if timed_out else "ERROR"


def now_cat():
    return datetime.now(KGL).strftime("%Y-%m-%d %H:%M:%S")


def done_counts():
    done = {}
    if os.path.exists(RAW):
        with open(RAW, newline="") as f:
            for r in csv.DictReader(f):
                if r["phase"] == "measured":
                    key = (r["case_id"], r["engine"])
                    done[key] = done.get(key, 0) + 1
    return done


def save_answer(case_id, engine, answer):
    data = {}
    if os.path.exists(ANSWERS):
        with open(ANSWERS) as f:
            data = json.load(f)
    data.setdefault(case_id, {})[engine] = answer
    with open(ANSWERS, "w") as f:
        json.dump(data, f)


def run_engine(engine, kind, q7_sql, only_q7=False):
    cases = build_cases(q7_sql)
    if not only_q7:
        assert len(cases) == 21, len(cases)
    cases = [c for c in cases if c["q"] == "Q7" or not only_q7]
    new = not os.path.exists(RAW)
    out = open(RAW, "a", newline="")
    w = csv.writer(out)
    if new:
        w.writerow(["case_id", "question", "case", "parameters", "engine", "phase", "run",
                    "cat_start", "seconds", "rows", "status", "note"])
    done = done_counts()

    for c in cases:
        if done.get((c["id"], engine), 0) >= RUNS:
            print(f"{c['id']:<10} {engine}: already done, skipped")
            continue
        fn = c[kind]
        post = c["post_" + kind]
        skip_note = ""
        for i in range(1, WARMUPS + 1):
            start = now_cat()
            t0 = perf_counter()
            try:
                rows = fn(WARM_TIMEOUT)
                st = "OK"
            except Exception as ex:
                rows, st = [], classify(ex)
            dur = perf_counter() - t0
            w.writerow([c["id"], c["q"], c["label"], c["params"], engine, "warmup", i,
                        start, f"{dur:.3f}", len(rows), st, ""])
            out.flush()
            if i == 1 and st != "OK":
                skip_note = f"not run: warm-up 1 ended with {st} after {dur:.0f} s"
                break

        durations, last_rows, statuses = [], None, []
        for r in range(1, RUNS + 1):
            if skip_note:
                w.writerow([c["id"], c["q"], c["label"], c["params"], engine, "measured", r,
                            now_cat(), "", 0, "TIMEOUT" if "TIMEOUT" in skip_note else "ERROR", skip_note])
                statuses.append("TIMEOUT" if "TIMEOUT" in skip_note else "ERROR")
                continue
            start = now_cat()
            t0 = perf_counter()
            try:
                rows = fn(RUN_TIMEOUT)          # consumes every row
                st = "OK"
            except Exception as ex:
                rows, st = [], classify(ex)
            dur = perf_counter() - t0
            w.writerow([c["id"], c["q"], c["label"], c["params"], engine, "measured", r,
                        start, f"{dur:.3f}", len(rows), st, ""])
            out.flush()
            statuses.append(st)
            if st == "OK":
                durations.append(dur)
                last_rows = rows

        if last_rows is not None:               # answers are compared outside the timer
            save_answer(c["id"], engine, json.dumps(norm(post(last_rows)), default=str))
        med = f"{median(durations) * 1000:,.0f} ms" if durations else "no completed run"
        print(f"{c['id']:<10} {engine:<14} median {med:<18} ok {len(durations)}/{RUNS}  "
              f"{[s for s in statuses if s != 'OK'][:1] or ''}", flush=True)
    out.close()
    print("\nRaw runs saved in", RAW)


def summary():
    stats = {}
    order = []
    with open(RAW, newline="") as f:
        for r in csv.DictReader(f):
            if r["phase"] != "measured":
                continue
            key = (r["case_id"], r["engine"])
            if r["case_id"] not in order:
                order.append(r["case_id"])
            s = stats.setdefault(key, {"ms": [], "TIMEOUT": 0, "ERROR": 0})
            if r["status"] == "OK":
                s["ms"].append(float(r["seconds"]) * 1000)
            else:
                s[r["status"]] += 1

    def cell(engine, cid):
        s = stats.get((cid, engine))
        if not s:
            return None
        return s

    def txt(s):
        if s is None:
            return "-", "-", "-", ""
        if not s["ms"]:
            return "T/O" if s["TIMEOUT"] else "ERR", "-", "-", f"0/{RUNS}"
        return (f"{median(s['ms']):,.0f}", f"{min(s['ms']):,.0f}", f"{max(s['ms']):,.0f}",
                "" if len(s["ms"]) == RUNS else f"{len(s['ms'])}/{RUNS}")

    rows_out = []
    print(f"{'case':<10}{'PG med':>9}{'min':>8}{'max':>8}  {'Neo med':>9}{'min':>8}{'max':>8}  {'PG/Neo':>8}")
    for cid in order:
        pg, neo = cell("PostgreSQL", cid), cell("Neo4j", cid)
        a, b = txt(pg), txt(neo)
        ratio = ""
        if pg and neo and pg["ms"] and neo["ms"]:
            ratio = f"{median(pg['ms']) / median(neo['ms']):.2f}"
        print(f"{cid:<10}{a[0]:>9}{a[1]:>8}{a[2]:>8}{a[3]:>3}{b[0]:>9}{b[1]:>8}{b[2]:>8}{b[3]:>3}{ratio:>8}")
        rows_out.append([cid, "PostgreSQL", *a[:3], pg["TIMEOUT"] if pg else "", pg["ERROR"] if pg else ""])
        rows_out.append([cid, "Neo4j", *b[:3], neo["TIMEOUT"] if neo else "", neo["ERROR"] if neo else ""])
        v3 = cell("PostgreSQL-v3", cid)
        if v3:
            c = txt(v3)
            ratio3 = f"{median(v3['ms']) / median(neo['ms']):.2f}" if v3["ms"] and neo and neo["ms"] else ""
            print(f"{'  (v3)':<10}{c[0]:>9}{c[1]:>8}{c[2]:>8}{c[3]:>3}{'':>26}{ratio3:>8}")
            rows_out.append([cid, "PostgreSQL-v3", *c[:3], v3["TIMEOUT"], v3["ERROR"]])
    with open(SUMMARY, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "engine", "median_ms", "min_ms", "max_ms", "timeouts", "errors"])
        w.writerows(rows_out)
    print("\nT/O = every measured run timed out (60 s). Values in milliseconds. Saved", SUMMARY)


def check():
    with open(ANSWERS) as f:
        data = json.load(f)
    ok = bad = 0
    for cid, ans in data.items():
        neo = ans.get("Neo4j")
        for eng, val in ans.items():
            if eng == "Neo4j" or neo is None:
                continue
            same = val == neo
            ok += same
            bad += not same
            print(f"{cid:<10} {eng:<14} vs Neo4j: {'SAME' if same else 'DIFFERENT'}")
    print(f"\n{ok} same, {bad} different")


def plans(which):
    if which == "pg":
        from psycopg import ClientCursor
        b = SETS["B"]
        p7 = q7.pg_params(b[0], b[1], 6)
        items = [("Q2 full month", q2.SQL, None),
                 ("Q4 set B depth 10", q4.SQL, {"account": b[0], "depth": 10}),
                 ("Q7 set B bound 6 - v1 (UNION ALL)", Q7_V1, p7),
                 ("Q7 set B bound 6 - v2 (UNION)", Q7_V2, p7),
                 ("Q7 set B bound 6 - v3 (both ends)", Q7_V3, p7)]
        with open("plans_pg.txt", "w") as f:
            for name, sql, params in items:
                note = "EXPLAIN (ANALYZE, BUFFERS)"
                cur = ClientCursor(pg())
                try:
                    cur.execute("SET statement_timeout = 900000")
                    cur.execute(f"{note} {sql}", params)
                except Exception as ex:
                    note = f"EXPLAIN only (ANALYZE failed: {classify(ex)})"
                    cur = ClientCursor(pg())
                    cur.execute("SET statement_timeout = 60000")
                    cur.execute(f"EXPLAIN {sql}", params)
                lines = [r[0] for r in cur.fetchall()]
                text = f"=== {name} [{note}] ===\n" + "\n".join(lines) + "\n"
                f.write(text + "\n")
                print(text)
        print("Saved plans_pg.txt")
    else:
        b = SETS["B"]
        items = [("Q2 full month", q2.CYP, {}),
                 ("Q4 set B depth 10", q4.cypher(10), {"account": b[0]}),
                 ("Q7 set B bound 6", q7.neo_len(6), {"src": b[0], "dst": b[1]})]

        def tree(p, indent, out):
            out.append(f"{'  ' * indent}{p.get('operatorType')}  rows={p.get('rows')}  "
                       f"dbHits={p.get('dbHits')}")
            for ch in p.get("children", []):
                tree(ch, indent + 1, out)

        with open("plans_neo.txt", "w") as f:
            for name, q, params in items:
                with neo().session(database="neo4j") as s:
                    summ = s.run("PROFILE " + q, params, timeout=900).consume()
                lines = []
                tree(summ.profile, 0, lines)
                text = f"=== {name} [PROFILE] ===\n" + "\n".join(lines) + "\n"
                f.write(text + "\n")
                print(text)
        print("Saved plans_neo.txt")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["pg"]:
        run_engine("PostgreSQL", "pg", Q7_V1)
    elif a[:1] == ["pg-v3"]:
        run_engine("PostgreSQL-v3", "pg", Q7_V3, only_q7=True)
    elif a[:1] == ["neo"]:
        run_engine("Neo4j", "neo", None)
    elif a[:1] == ["summary"]:
        summary()
    elif a[:1] == ["check"]:
        check()
    elif a[:1] == ["plans"] and len(a) > 1 and a[1] in ("pg", "neo"):
        plans(a[1])
    else:
        print("Usage: python bench.py pg | pg-v3 | neo | summary | check | plans pg | plans neo")
