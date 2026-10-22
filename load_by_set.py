# load_by_set.py - median latency (ms) per set A/B/C for the 1-client runs, per engine and workload
import csv
from statistics import median

groups = {}
with open("load_raw.csv", newline="") as f:
    for r in csv.DictReader(f):
        if r["clients"] == "1" and r["status"] == "OK":
            groups.setdefault((r["engine"], r["workload"], r["set"]), []).append(float(r["latency_s"]) * 1000)

print(f"{'engine':<8}{'workload':<10}{'set':<5}{'requests':>9}{'median ms':>11}")
for (eng, wl, k), v in sorted(groups.items()):
    print(f"{eng:<8}{wl:<10}{k:<5}{len(v):>9}{median(v):>11.1f}")
