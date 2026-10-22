"""capture.py - stream the generator into five CSV files and record audit totals.

Usage:
    python capture.py preview     # 10 records per stream (screenshot this)
    python capture.py             # full capture (screenshot the totals)
"""
import csv
import itertools
import json
import os
import sys
from time import perf_counter

import mobile_money_generator as g

STREAMS = ["customers", "accounts", "devices", "account_devices", "transfers"]
EXPECTED = {
    "customers": 228_000,
    "accounts": 248_000,
    "devices": 228_600,
    "account_devices": 285_600,
    "transfers": 20_003_300,
}


def preview():
    print("dataset_info:", g.dataset_info())
    for name in STREAMS:
        print(f"\n== {name}  fields={g.FIELDS[name]}")
        # fresh iterator each time restarts the stream
        for row in itertools.islice(getattr(g, f"iter_{name}")(), 10):
            print(row)


def capture_stream(name):
    fields = g.FIELDS[name]
    path = f"{name}.csv"
    consumed = written = 0
    # audit totals (meaningful for transfers, harmless for others)
    min_t = max_t = None
    sum_amount = 0
    t0 = perf_counter()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in getattr(g, f"iter_{name}")():
            consumed += 1
            writer.writerow(row)
            written += 1
            if name == "transfers":
                ts = int(row["occurred_at"])
                min_t = ts if min_t is None or ts < min_t else min_t
                max_t = ts if max_t is None or ts > max_t else max_t
                sum_amount += int(row["amount_rwf"])
                if written % 1_000_000 == 0:
                    print(f"  transfers: {written:,} rows "
                          f"({perf_counter() - t0:.0f}s)", flush=True)
    secs = perf_counter() - t0
    audit = {
        "stream": name,
        "consumed": consumed,
        "written": written,
        "expected": EXPECTED[name],
        "count_matches": written == EXPECTED[name],
        "seconds": round(secs, 2),
        "csv_bytes": os.path.getsize(path),
        "csv_gb": round(os.path.getsize(path) / 1e9, 4),
    }
    if name == "transfers":
        audit.update(
            transfer_count=written,
            min_occurred_at=min_t,
            max_occurred_at=max_t,
            sum_amount_rwf=sum_amount,
        )
    print(f"{name}: consumed={consumed:,} written={written:,} "
          f"expected={EXPECTED[name]:,} ok={audit['count_matches']} "
          f"{secs:.1f}s {audit['csv_gb']} GB", flush=True)
    return audit


def main():
    total_start = perf_counter()
    audits = {name: capture_stream(name) for name in STREAMS}
    audits["total_seconds"] = round(perf_counter() - total_start, 2)
    audits["total_rows"] = sum(audits[n]["written"] for n in STREAMS)
    with open("audit.json", "w") as f:
        json.dump(audits, f, indent=2)
    print(f"\nTOTAL rows={audits['total_rows']:,} (expected 20,993,500) "
          f"in {audits['total_seconds']}s")
    t = audits["transfers"]
    print(f"transfers: count={t['transfer_count']:,} "
          f"min={t['min_occurred_at']} max={t['max_occurred_at']} "
          f"sum_amount_rwf={t['sum_amount_rwf']:,}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        preview()
    else:
        main()