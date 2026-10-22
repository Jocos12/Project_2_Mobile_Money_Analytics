import csv, statistics as s
rows = list(csv.DictReader(open("load_raw.csv", encoding="utf-8-sig")))

# garder les blocs (pg, Q7b6, 1 client, rep) et prendre le DERNIER bloc de chaque rep
blocks = {}
prev = None
for r in rows:
    key = (r["engine"], r["workload"], r["clients"], r["rep"])
    if key != prev:
        blocks.setdefault(key, []).append([])
        prev = key
    blocks[key][-1].append(r)

for rep in ("1", "2", "3"):
    key = ("pg", "Q7b6", "1", rep)
    if key not in blocks:
        print("rep", rep, "| absent")
        continue
    last = blocks[key][-1]          # dernier run
    line = []
    for k in "ABC":
        v = [float(r["latency_s"]) * 1000 for r in last
             if r["set"] == k and r["status"] == "OK"]
        if v:
            line.append(f"{k}: n={len(v)} med={s.median(v):.1f} min={min(v):.1f} max={max(v):.1f}")
    print("rep", rep, f"({len(blocks[key])} bloc(s) trouve(s)) |", " | ".join(line))