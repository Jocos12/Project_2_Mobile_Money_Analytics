"""prepare_import.py - build temporary Neo4j import copies of the CSVs (section 3.2).

The source CSVs are NEVER modified. Typed-header copies go into an output
folder (pick a path WITHOUT spaces, e.g. J:\\momo_import).

Usage:
    python prepare_import.py prepare --out J:\\momo_import
    python prepare_import.py clean   --out J:\\momo_import
"""
import argparse
import csv
import os
import shutil
import time

# expected header of each source CSV -> typed header for neo4j-admin import
JOBS = {
    # source file          : (expected source header,                                   import file,      typed header)
    "customers.csv": ("customer_id,region",
                      "customers.csv",
                      "customer_id:ID(Customer),region:string"),
    "accounts.csv": ("account_id,customer_id,role",
                     "accounts.csv",
                     "account_id:ID(Account),:IGNORE,role:string"),
    "devices.csv": ("device_id,access_type",
                    "devices.csv",
                    "device_id:ID(Device),access_type:string"),
    "account_devices.csv": ("account_id,device_id,first_day,last_day,observations",
                            "used_device.csv",
                            ":START_ID(Account),:END_ID(Device),first_day:int,last_day:int,observations:int"),
    "transfers.csv": ("transfer_id,sender_id,receiver_id,occurred_at,amount_rwf",
                      "transfers.csv",
                      "transfer_id:long,:START_ID(Account),:END_ID(Account),occurred_at:long,amount_rwf:int"),
}
OWNS_HEADER = ":START_ID(Customer),:END_ID(Account)"


def copy_with_header(src, dst, expected, typed):
    """Replace only the first line; stream the rest as bytes (transfers.csv is ~780 MB)."""
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        first = fin.readline()
        eol = b"\r\n" if first.endswith(b"\r\n") else b"\n"
        got = first.rstrip(b"\r\n").decode()
        if got != expected:
            raise SystemExit(f"{src}: unexpected header {got!r}, wanted {expected!r}")
        fout.write(typed.encode() + eol)
        shutil.copyfileobj(fin, fout, 16 * 1024 * 1024)


def derive_owns(src, dst):
    """owns.csv: (customer_id, account_id) sorted by customer_id then account_id."""
    pairs = []
    with open(src, newline="") as f:
        for row in csv.DictReader(f):
            pairs.append((int(row["customer_id"]), int(row["account_id"])))
    pairs.sort()
    with open(dst, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(OWNS_HEADER.split(","))
        w.writerows(pairs)
    return len(pairs)


def prepare(out):
    os.makedirs(out, exist_ok=True)
    t0 = time.perf_counter()
    for src, (expected, dst_name, typed) in JOBS.items():
        s = time.perf_counter()
        copy_with_header(src, os.path.join(out, dst_name), expected, typed)
        print(f"{src:22s} -> {dst_name:18s} {time.perf_counter() - s:6.1f}s")
    n = derive_owns("accounts.csv", os.path.join(out, "owns.csv"))
    print(f"{'(derived)':22s} -> {'owns.csv':18s} {n:,} rows (expected 248,000)")
    print(f"prepare_import done in {time.perf_counter() - t0:.1f}s -> {out}")


def clean(out):
    if os.path.isdir(out):
        shutil.rmtree(out)
        print(f"removed {out}")
    else:
        print(f"{out} does not exist")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", default="prepare", choices=["prepare", "clean"])
    ap.add_argument("--out", default="neo4j_import")
    a = ap.parse_args()
    prepare(a.out) if a.action == "prepare" else clean(a.out)
