# load_test.py - Section 7: concurrent load test (Barrier, 1/4/8/16 clients, 3 repetitions)
#
# Run ONE database service at a time:
#   python load_test.py pg        -> PostgreSQL (Q4 depth 10 + Q7 bound 6 with the selected SQL v3)
#   python load_test.py neo       -> Neo4j
#   python load_test.py summary   -> 16 combination summaries (median of the 3 repetitions)
#   python load_test.py plots     -> load_plots.png (throughput and p95 versus clients)
#
# Workloads: Q4 depth 10 and Q7 length-only bound 6, cycling sets A-B-C.
# Each client: one connection, one untimed A-B-C warm-up, Barrier release, common start time,
# deadline = start + 15 s. A cycle (A,B,C) is started only before the deadline and always
# finished. Next request is sent immediately after the previous one completes.
# Query timeout 60 s. Answers are checked after timing against a reference answer.
# Re-running resumes: combinations already in load_reps.csv are skipped.
import csv
import json
import math
import multiprocessing as mp
import os
import sys
import time
from datetime import datetime
from statistics import median
from time import perf_counter

from common import *
import q4, q7

DURATION = float(os.environ.get("LOAD_SECONDS", 15))
QUERY_TIMEOUT, WARM_TIMEOUT = 60, 180
CLIENTS = (1, 4, 8, 16)
REPS = 3
WORKLOADS = ("Q4d10", "Q7b6")
ENGINES = {"pg": "PostgreSQL", "neo": "Neo4j"}
RAW, REPS_CSV, SUMMARY = "load_raw.csv", "load_reps.csv", "load_summary.csv"


def request(engine, wl, k, timeout):
    acct, dst, _day = SETS[k]
    if wl == "Q4d10":
        if engine == "pg":
            return run_pg(q4.SQL, {"account": acct, "depth": 10}, timeout)
        return run_neo(q4.cypher(10), {"account": acct}, timeout)
    if engine == "pg":
        return run_pg(q7.SQL_V3, q7.pg_params(acct, dst, 6), timeout)
    return run_neo(q7.neo_len(6), {"src": acct, "dst": dst}, timeout)


def answer(engine, wl, rows):
    if wl == "Q7b6" and engine == "pg":
        rows = [] if rows[0][0] is None else [(int(rows[0][0]),)]
    return json.dumps(norm(rows), default=str)


def classify(ex):
    msg = str(ex).lower()
    return "TIMEOUT" if any(w in msg for w in ("timeout", "timed out", "canceling statement",
                                               "terminated")) else "ERROR"


def worker(idx, engine, wl, b1, b2, start_val, out_q):
    recs = []
    try:
        for k in "ABC":                                   # untimed warm-up, once
            try:
                request(engine, wl, k, WARM_TIMEOUT)
            except Exception:
                pass
        if b1.wait() == 0:                                # barrier release; one client fixes
            start_val.value = time.time()                 # the common start time
        b2.wait()
        t0 = start_val.value
        deadline = t0 + DURATION
        cyc = 0
        while time.time() < deadline:                     # start a cycle only before deadline
            cyc += 1
            for k in "ABC":                               # a started cycle is always finished
                s = time.time()
                p = perf_counter()
                try:
                    rows = request(engine, wl, k, QUERY_TIMEOUT)
                    st, ans = "OK", answer(engine, wl, rows)
                except Exception as ex:
                    st, ans = classify(ex), ""
                lat = perf_counter() - p
                if st == "OK" and lat > QUERY_TIMEOUT:    # over the 60 s limit = timeout
                    st = "TIMEOUT"
                recs.append((idx, cyc, k, s - t0, lat, st, ans))
    except Exception as ex:
        recs.append((idx, 0, "-", 0.0, 0.0, "ERROR", f"worker failed: {ex}"))
    out_q.put(recs)


def reference(engine, wl):
    return {k: answer(engine, wl, request(engine, wl, k, WARM_TIMEOUT)) for k in "ABC"}


def p95(lat):
    s = sorted(lat)
    return s[math.ceil(0.95 * len(s)) - 1] if s else None


def run_combo(engine, wl, n, rep, ref):
    ctx = mp.get_context("spawn")
    b1, b2 = ctx.Barrier(n, timeout=900), ctx.Barrier(n, timeout=900)
    start_val = ctx.Value("d", 0.0)
    q = ctx.Queue()
    procs = [ctx.Process(target=worker, args=(i, engine, wl, b1, b2, start_val, q))
             for i in range(n)]
    for p in procs:
        p.start()
    while start_val.value == 0.0 and any(p.is_alive() for p in procs):
        time.sleep(0.2)
    time.sleep(min(5, DURATION / 3))
    alive = sum(p.is_alive() for p in procs)
    print(f"    active clients at {datetime.now(KGL):%H:%M:%S} CAT: {alive}/{n}", flush=True)
    recs = []
    for _ in range(n):
        recs.extend(q.get())
    for p in procs:
        p.join()

    t0 = start_val.value
    ok_lat, errors, timeouts, wrong, correct = [], 0, 0, 0, 0
    last_end, rows_out = 0.0, []
    for idx, cyc, k, off, lat, st, ans in recs:
        last_end = max(last_end, off + lat)
        good = st == "OK" and ans == ref[k]
        if st == "OK":
            ok_lat.append(lat)
            if good:
                correct += 1
            else:
                wrong += 1
        elif st == "TIMEOUT":
            timeouts += 1
        else:
            errors += 1
        rows_out.append([engine, wl, n, rep, idx, cyc, k, f"{off:.3f}", f"{lat:.4f}", st,
                         int(good)])
    elapsed = last_end
    thr = correct / elapsed if elapsed > 0 else 0.0
    med = median(ok_lat) * 1000 if ok_lat else None
    p = p95(ok_lat)
    return rows_out, [ENGINES[engine], wl, n, rep, len(recs), correct, wrong, errors, timeouts,
                      f"{elapsed:.3f}", f"{thr:.3f}",
                      "" if med is None else f"{med:.1f}", "" if p is None else f"{p * 1000:.1f}"]


def done_keys():
    done = set()
    if os.path.exists(REPS_CSV):
        with open(REPS_CSV, newline="") as f:
            for r in csv.DictReader(f):
                done.add((r["engine"], r["workload"], int(r["clients"]), int(r["rep"])))
    return done


def run(engine):
    name = ENGINES[engine]
    new_raw, new_reps = not os.path.exists(RAW), not os.path.exists(REPS_CSV)
    raw = open(RAW, "a", newline="")
    reps = open(REPS_CSV, "a", newline="")
    wr, wp = csv.writer(raw), csv.writer(reps)
    if new_raw:
        wr.writerow(["engine", "workload", "clients", "rep", "client", "cycle", "set",
                     "offset_s", "latency_s", "status", "correct"])
    if new_reps:
        wp.writerow(["engine", "workload", "clients", "rep", "requests", "correct", "wrong",
                     "errors", "timeouts", "elapsed_s", "throughput_per_s", "median_ms",
                     "p95_ms"])
    done = done_keys()
    for wl in WORKLOADS:
        print(f"\n{name} - {wl}: computing reference answers", flush=True)
        ref = reference(engine, wl)
        for n in CLIENTS:
            for rep in range(1, REPS + 1):
                if (name, wl, n, rep) in done:
                    print(f"  {wl} clients={n} rep={rep}: already done, skipped")
                    continue
                print(f"  {wl} clients={n} rep={rep} start {datetime.now(KGL):%H:%M:%S} CAT",
                      flush=True)
                rows_out, rep_row = run_combo(engine, wl, n, rep, ref)
                wr.writerows(rows_out)
                wp.writerow(rep_row)
                raw.flush()
                reps.flush()
                print(f"    requests={rep_row[4]} correct={rep_row[5]} wrong={rep_row[6]} "
                      f"err={rep_row[7]} timeout={rep_row[8]} thr={rep_row[10]}/s "
                      f"median={rep_row[11]} ms p95={rep_row[12]} ms", flush=True)
    raw.close()
    reps.close()
    print("\nSaved", RAW, "and", REPS_CSV)


def load_reps():
    groups = {}
    with open(REPS_CSV, newline="") as f:
        for r in csv.DictReader(f):
            groups.setdefault((r["engine"], r["workload"], int(r["clients"])), []).append(r)
    return groups


def num(rows, col):
    vals = [float(r[col]) for r in rows if r[col] != ""]
    return median(vals) if vals else None


def summary():
    groups = load_reps()
    out = []
    print(f"{'engine':<11}{'workload':<8}{'clients':>8}{'reps':>5}{'thr/s':>9}{'med ms':>9}"
          f"{'p95 ms':>9}{'errors':>8}{'timeouts':>9}{'wrong':>7}")
    for eng in ("PostgreSQL", "Neo4j"):
        for wl in WORKLOADS:
            for n in CLIENTS:
                rows = groups.get((eng, wl, n))
                if not rows:
                    continue
                thr, med, p = (num(rows, "throughput_per_s"), num(rows, "median_ms"),
                               num(rows, "p95_ms"))
                err = sum(int(r["errors"]) for r in rows)
                to = sum(int(r["timeouts"]) for r in rows)
                wr = sum(int(r["wrong"]) for r in rows)
                f = lambda v: "-" if v is None else f"{v:,.1f}"
                print(f"{eng:<11}{wl:<8}{n:>8}{len(rows):>5}{f(thr):>9}{f(med):>9}{f(p):>9}"
                      f"{err:>8}{to:>9}{wr:>7}")
                out.append([eng, wl, n, len(rows), thr, med, p, err, to, wr])
    with open(SUMMARY, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["engine", "workload", "clients", "reps", "median_throughput_per_s",
                    "median_latency_ms", "median_p95_ms", "errors", "timeouts", "wrong"])
        w.writerows(out)
    print("\nMedian of the repetitions. Errors/timeouts/wrong are totals over the repetitions.")
    print("Saved", SUMMARY)


def plots():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups = load_reps()
    fig, ax = plt.subplots(2, 2, figsize=(11, 7))
    titles = {"Q4d10": "Q4 depth 10", "Q7b6": "Q7 length-only, bound 6 (SQL v3)"}
    for c, wl in enumerate(WORKLOADS):
        for eng, style in (("PostgreSQL", "o-"), ("Neo4j", "s--")):
            xs, thr, p = [], [], []
            for n in CLIENTS:
                rows = groups.get((eng, wl, n))
                if rows:
                    xs.append(n)
                    thr.append(num(rows, "throughput_per_s"))
                    p.append(num(rows, "p95_ms"))
            if xs:
                ax[0][c].plot(xs, thr, style, label=eng)
                ax[1][c].plot(xs, p, style, label=eng)
        ax[0][c].set_title(titles[wl])
        ax[0][c].set_ylabel("Throughput (correct requests/s)")
        ax[1][c].set_ylabel("p95 latency (ms)")
        ax[1][c].set_xlabel("Clients")
        for r in (0, 1):
            ax[r][c].set_xticks(CLIENTS)
            ax[r][c].grid(alpha=.3)
            ax[r][c].legend()
    fig.tight_layout()
    fig.savefig("load_plots.png", dpi=150)
    print("Saved load_plots.png")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] in (["pg"], ["neo"]):
        run(a[0])
    elif a[:1] == ["summary"]:
        summary()
    elif a[:1] == ["plots"]:
        plots()
    else:
        print("Usage: python load_test.py pg | neo | summary | plots")
