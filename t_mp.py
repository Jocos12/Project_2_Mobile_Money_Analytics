import time, statistics, multiprocessing as mp
import q7
from common import run_pg, SETS

def loop(label, q=None, secs=10):
    for k in "ABC":                       # échauffement
        a, d, _ = SETS[k]
        run_pg(q7.SQL_V3, q7.pg_params(a, d, 6), 60)
    lat = []
    end = time.time() + secs
    while time.time() < end:
        for k in "ABC":
            a, d, _ = SETS[k]
            t = time.perf_counter()
            run_pg(q7.SQL_V3, q7.pg_params(a, d, 6), 60)
            lat.append((time.perf_counter() - t) * 1000)
    res = (label, len(lat), round(statistics.median(lat), 1))
    if q: q.put(res)
    else: print(res)

if __name__ == "__main__":
    loop("main process, ABC alternating")
    q = mp.Queue()
    p = mp.Process(target=loop, args=("child process, ABC alternating", q))
    p.start(); print(q.get()); p.join()