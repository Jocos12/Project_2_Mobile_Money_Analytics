import time, q7
from common import run_pg, SETS

for k in ("A", "B", "C"):
    acct, dst, _ = SETS[k]
    for i in range(6):
        t = time.perf_counter()
        run_pg(q7.SQL_V3, q7.pg_params(acct, dst, 6), 60)
        print(k, i, round((time.perf_counter() - t) * 1000, 1), "ms")