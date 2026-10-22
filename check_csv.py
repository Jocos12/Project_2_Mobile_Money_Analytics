# check_csv.py - independent checks against the captured CSV files (no database used
# for the expected values). Run from the project folder where the CSVs are.
#   (a) Q3 device overlaps for all six sets, recomputed in Python
#   (b) one Q5 chain (set B) and one Q6 cycle (set A) re-validated from transfers.csv
import csv
from collections import defaultdict

from common import *
import q3, q5, q6


def check_q3():
    access = {}
    with open("devices.csv", newline="") as f:
        for r in csv.DictReader(f):
            access[int(r["device_id"])] = r["access_type"]
    by_dev = defaultdict(list)
    with open("account_devices.csv", newline="") as f:
        for r in csv.DictReader(f):
            by_dev[int(r["device_id"])].append(
                (int(r["account_id"]), int(r["first_day"]), int(r["last_day"])))

    print("(a) Q3 overlaps recomputed from account_devices.csv and devices.csv")
    example = None
    for k, (acct, dst, day) in SETS.items():
        expected = []
        for dev, lst in by_dev.items():
            mine = [(f1, l1) for a, f1, l1 in lst if a == acct]
            if not mine:
                continue
            f1, l1 = mine[0]
            for b, f2, l2 in lst:
                if b == acct:
                    continue
                s, e = max(f1, f2), min(l1, l2)
                if s <= e:
                    expected.append((b, dev, access[dev], s, e))
                    if example is None:
                        example = (k, acct, b, dev, (f1, l1), (f2, l2), (s, e))
        pg_rows = [tuple(r) for r in run_pg(q3.SQL, {"account": acct})]
        ok = norm(expected) == norm(pg_rows)
        print(f"  set {k} (account {acct}): CSV {len(expected)} rows, PostgreSQL {len(pg_rows)} rows -> "
              f"{'MATCH' if ok else 'DIFFERENT'}")
    if example:
        k, acct, b, dev, i1, i2, ov = example
        print(f"  Example (set {k}): account {acct} days {i1[0]}-{i1[1]} and account {b} "
              f"days {i2[0]}-{i2[1]} on device {dev} -> overlap days {ov[0]}-{ov[1]}")


def load_rows(ids):
    """Read the given transfer IDs from transfers.csv (streamed, one pass)."""
    want = {str(i) for i in ids}
    found = {}
    with open("transfers.csv", newline="") as f:
        rd = csv.reader(f)
        next(rd)
        for r in rd:
            if r[0] in want:
                found[int(r[0])] = tuple(int(x) for x in r)  # id, sender, receiver, time, amount
                if len(found) == len(want):
                    break
    return [found[i] for i in ids]


def report(title, checks):
    print(f"\n{title}")
    for text, ok in checks:
        print(f"  [{'x' if ok else ' '}] {text}")
    print("  RESULT:", "VALID" if all(ok for _, ok in checks) else "NOT VALID")


def amount_ok(a, b):
    return 90 * a <= 100 * b and 100 * b <= 105 * a


def check_chain():
    k = "B"
    acct, dst, day = SETS[k]
    s, e = hour_window(day)
    rows = run_pg(q5.SQL, {"account": acct, "start": s, "end": e})
    ids = list(rows[0][:3])
    t = load_rows(ids)
    accounts = [t[0][1], t[0][2], t[1][2], t[2][2]]
    report(f"(b1) Q5 chain, set {k}, transfers {ids}, re-read from transfers.csv: {t}", [
        ("starts at the review account", t[0][1] == acct),
        ("each transfer starts where the previous one ended", t[0][2] == t[1][1] and t[1][2] == t[2][1]),
        ("first transfer inside 09:45-10:45 CAT", s <= t[0][3] < e),
        ("gap 1 in (0, 600] s", 0 < t[1][3] - t[0][3] <= 600),
        ("gap 2 in (0, 600] s", 0 < t[2][3] - t[1][3] <= 600),
        ("amount 2 within 90%-105% of amount 1", amount_ok(t[0][4], t[1][4])),
        ("amount 3 within 90%-105% of amount 2", amount_ok(t[1][4], t[2][4])),
        ("four distinct accounts", len(set(accounts)) == 4),
    ])


def check_cycle():
    k = "A"
    acct, dst, day = SETS[k]
    s, e = hour_window(day)
    rows = run_pg(q6.SQL, {"account": acct, "start": s, "end": e})
    ids = list(rows[0][0])
    t = load_rows(ids)
    times = [x[3] for x in t]
    report(f"(b2) Q6 cycle, set {k}, transfers {ids}, re-read from transfers.csv: {t}", [
        ("3 to 8 transfers", 3 <= len(t) <= 8),
        ("starts at the review account", t[0][1] == acct),
        ("ends at the review account", t[-1][2] == acct),
        ("first return is the end (no earlier return)", all(x[2] != acct for x in t[:-1])),
        ("each transfer starts where the previous one ended", all(t[i][2] == t[i + 1][1] for i in range(len(t) - 1))),
        ("all inside 09:45-10:45 CAT", all(s <= x < e for x in times)),
        ("strictly increasing times", all(times[i] < times[i + 1] for i in range(len(times) - 1))),
        ("span <= 1800 s", times[-1] - times[0] <= 1800),
        ("amount rule on every step", all(amount_ok(t[i][4], t[i + 1][4]) for i in range(len(t) - 1))),
    ])


if __name__ == "__main__":
    check_q3()
    check_chain()
    check_cycle()
