# q2.py - Q2 daily activity (CAT days), reconciliation with capture totals, charts
# Needs:  pip install matplotlib
import csv
from time import perf_counter

from common import *

# Capture audit totals (verified in capture.py, PostgreSQL and Neo4j)
EXPECTED_COUNT = 20_003_300
EXPECTED_SUM = 231_482_327_870

SQL = """SELECT (to_timestamp(occurred_at) AT TIME ZONE 'Africa/Kigali')::date AS d,
                COUNT(*) AS n, SUM(amount_rwf) AS total
         FROM transfers
         GROUP BY 1
         ORDER BY 1"""

CYP = """MATCH ()-[t:TRANSFER]->()
         WITH date(datetime({epochSeconds: t.occurred_at, timezone: 'Africa/Kigali'})) AS d, t
         RETURN toString(d) AS d, count(t) AS n, sum(t.amount_rwf) AS total
         ORDER BY d"""

TIMEOUT = 900  # seconds; full-month scan, generous for the correctness run

if __name__ == "__main__":
    t0 = perf_counter()
    pg_rows = [(str(d), int(n), int(s)) for d, n, s in run_pg(SQL, timeout_s=TIMEOUT)]
    t_pg = perf_counter() - t0

    t0 = perf_counter()
    neo_rows = [(str(d), int(n), int(s)) for d, n, s in run_neo(CYP, timeout_s=TIMEOUT)]
    t_neo = perf_counter() - t0

    print(f"PostgreSQL: {len(pg_rows)} days in {t_pg:.1f} s")
    print(f"Neo4j     : {len(neo_rows)} days in {t_neo:.1f} s")
    print()
    print(f"{'date':<12}{'count':>12}{'total_rwf':>18}")
    for d, n, s in pg_rows:
        print(f"{d:<12}{n:>12,}{s:>18,}")

    sum_n = sum(r[1] for r in pg_rows)
    sum_s = sum(r[2] for r in pg_rows)
    print()
    print("30 days in both engines :", "OK" if len(pg_rows) == len(neo_rows) == 30 else "CHECK")
    print("PG == Neo4j             :", "OK" if pg_rows == neo_rows else "MISMATCH")
    print(f"Sum of counts           : {sum_n:,} (expected {EXPECTED_COUNT:,})",
          "OK" if sum_n == EXPECTED_COUNT else "MISMATCH")
    print(f"Sum of RWF              : {sum_s:,} (expected {EXPECTED_SUM:,})",
          "OK" if sum_s == EXPECTED_SUM else "MISMATCH")

    with open("q2_daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "count", "total_rwf"])
        w.writerows(pg_rows)

    # Charts: daily count and daily value
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    days = [r[0][-5:] for r in pg_rows]  # MM-DD
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    ax[0].bar(days, [r[1] for r in pg_rows], color="#2a6fb0")
    ax[0].set_ylabel("Transfers per day (count)")
    ax[0].set_title("Daily transfer activity, September 2026 (CAT days)")
    ax[1].bar(days, [r[2] / 1e9 for r in pg_rows], color="#d9822b")
    ax[1].set_ylabel("Value per day (billion RWF)")
    ax[1].set_xlabel("Date (2026-MM-DD, Africa/Kigali)")
    plt.setp(ax[1].get_xticklabels(), rotation=60)
    fig.tight_layout()
    fig.savefig("q2_daily_charts.png", dpi=150)
    print("\nSaved q2_daily.csv and q2_daily_charts.png")
