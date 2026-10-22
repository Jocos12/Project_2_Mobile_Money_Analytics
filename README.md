# Project 2 – Mobile Money Investigations with PostgreSQL and Neo4j

Advanced Big Data Analytics · Master's in Big Data
Issued 12 October 2026 · Due 26 October 2026, 11:59 PM CAT

**Group members**

| Name | ID |
|---|---|
| HITAYEZU James | 101381 |
| Joseph Courbon | 101493 |
| Mylene MANIRAKIZA | 101403 |

Repository: <https://github.com/Jocos12/Project_2_Mobile_Money_Analytics>

---

## 1. Overview

A mobile money provider in Rwanda wants analysts to explain payment activity and to identify accounts that need closer review. This project loads the same September 2026 records (20,993,500 source records) into **PostgreSQL 18.6** and **Neo4j Community**, then builds seven investigations (Q1 to Q7) in both systems and compares them on correctness, speed and behaviour under concurrent load.

| Data set | Rows / elements |
|---|---|
| customers | 228,000 |
| accounts | 248,000 (240,000 person, 6,000 merchant, 2,000 agent) |
| devices | 228,600 |
| account_devices | 285,600 |
| transfers | 20,003,300 (sum 231,482,327,870 RWF) |
| Neo4j graph | 704,600 nodes, 20,536,900 relationships |

The questions:

| Q | Topic |
|---|---|
| Q1 | Outgoing activity of an account in a one-hour window |
| Q2 | Daily activity (30 CAT days) |
| Q3 | Accounts sharing a device in overlapping periods |
| Q4 | Ownership and device network within 4, 6, 8, 10 links |
| Q5 | Rapid onward payments (3 transfers, 4 distinct accounts) |
| Q6 | Circular payments (3 to 8 transfers returning to the start) |
| Q7 | Shortest directed transfer route through person accounts |

## 2. Key results

| Finding | Evidence |
|---|---|
| Both engines answer identically | All 61 comparison cases match; Q7 v3 re-verified on 12 cases |
| Reporting suits PostgreSQL | Q2: 2.7 s in PostgreSQL (EXPLAIN ANALYZE) vs 123 s median in Neo4j |
| Fixed-length patterns suit PostgreSQL | Q5/Q6: 1 to 3 ms vs 7 to 9 ms |
| Q7 gap was largely implementation | Set B, bound 6: v2 87,337 ms, v3 192 ms (plan), 31 ms timed vs 16 ms Neo4j |
| Concurrency favours Neo4j | 16 clients: about 11x (Q4) and 17x (Q7) the PostgreSQL throughput; PostgreSQL at 91% CPU |
| Import / load | Neo4j import 38 s; PostgreSQL COPY about 78 s |

## 3. Repository layout

```
.
├── mobile_money_generator.py   # supplied generator, NOT modified
├── common.py                   # connections, run_pg / run_neo helpers
├── capture.py                  # 1.2  streams -> CSV, audit totals
├── schema.sql                  # 2.1  tables, keys, constraints
├── load.sql                    # 2.2  \copy loads (timed) and indexes
├── checks.sql                  # 2.2  counts, audit, roles, constraints
├── prepare_import.py           # 3.2  typed-header copies, owns.csv, clean
├── trace_account.sql           # 3.3  SQL JOIN trace of one account
├── trace_account.cypher        # 3.3  Cypher trace of one account
├── q1.py ... q7.py             # 4-5  SQL + Cypher pair per question
├── compare_61.py               # 6.1  61-case correctness comparison
├── check_csv.py                # 6.1  independent checks against CSV rows
├── bench.py                    # 6.2  timing (pg, neo, pg-v3, check)
├── load_test.py                # 7.1  multiprocessing load test
├── t_mp.py                     # 7.1  control test (main vs child process)
├── results/                    # raw results and plans (CSV / TXT)
├── screenshots/                # evidence used in the report
└── build_report.py             # regenerates the PDF report
```

Large CSV files and database stores are **not** committed; they stay local.

## 4. Requirements

| Component | Version used |
|---|---|
| OS | Windows 11 Pro |
| Hardware | Intel Core i7-1355U (10 cores, 12 logical), 16 GB RAM, NVMe SSD |
| PostgreSQL | 18.6 (time zone `Africa/Kigali`) |
| Neo4j | Community 2026.10.0, default `neo4j` database |
| Python | 3.12 |
| Drivers | `psycopg` 3, `neo4j` 6.4.1 |
| Other | `matplotlib`, `reportlab`, `pillow` |
| Disk | up to 10 GB free |

```bash
pip install psycopg[binary] neo4j matplotlib reportlab pillow
```

## 5. Configuration (placeholder secrets)

Never commit real passwords. Set them in the shell before running:

```bat
set PGPASSWORD=<your_postgres_password>
set NEO4J_PASSWORD=<your_neo4j_password>
```

`common.py` reads the PostgreSQL DSN (`dbname=momo host=localhost`) and the Neo4j URI (`bolt://localhost:7687`, user `neo4j`) from these variables.

## 6. Execution order

All commands are run from the project folder in `cmd`.

### 6.1 Workspace (section 1.1)

```bat
psql -U postgres -c "CREATE DATABASE momo"
psql -U postgres -d momo -c "ALTER DATABASE momo SET timezone TO 'Africa/Kigali'"
psql -U postgres -d momo -c "SHOW timezone"
```

### 6.2 Capture the data (section 1.2)

```bat
python capture.py
```

Expected audit: 20,993,500 rows in total; transfers: count 20,003,300, min `occurred_at` 1788235200, max 1790798399, sum 231,482,327,870 RWF.

### 6.3 Build PostgreSQL (section 2)

```bat
psql -U postgres -d momo -f schema.sql
psql -U postgres -d momo -f load.sql
psql -U postgres -d momo -f checks.sql
```

`checks.sql` must show 228,000 / 248,000 / 228,600 / 285,600 / 20,003,300 rows, the audit totals, 240,000 person / 6,000 merchant / 2,000 agent accounts, and every constraint with `convalidated = t`.

### 6.4 Build Neo4j (section 3)

```bat
python prepare_import.py --out J:\momo_import
neo4j stop
neo4j-admin database import full neo4j --overwrite-destination ^
  --id-type=integer ^
  --nodes=Customer=J:\momo_import\customers.csv ^
  --nodes=Account=J:\momo_import\accounts.csv ^
  --nodes=Device=J:\momo_import\devices.csv ^
  --relationships=OWNS=J:\momo_import\owns.csv ^
  --relationships=USED_DEVICE=J:\momo_import\account_devices.csv ^
  --relationships=TRANSFER=J:\momo_import\transfers.csv
neo4j start
```

Then create the constraints and the index (cypher-shell):

```cypher
CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE;
CREATE CONSTRAINT account_id  IF NOT EXISTS FOR (a:Account)  REQUIRE a.account_id  IS UNIQUE;
CREATE CONSTRAINT device_id   IF NOT EXISTS FOR (d:Device)   REQUIRE d.device_id   IS UNIQUE;
CREATE RANGE INDEX transfer_time IF NOT EXISTS FOR ()-[t:TRANSFER]-() ON (t.occurred_at);
SHOW INDEXES;
```

Expected import: 704,600 nodes, 20,536,900 relationships, 62,275,900 properties. After verification, remove the temporary copies:

```bat
python prepare_import.py clean --out J:\momo_import
```

### 6.5 Inspect one account in both models (section 3.3)

```bat
psql -U postgres -d momo -v acct=998 -f trace_account.sql
cypher-shell -u neo4j -p %NEO4J_PASSWORD% --param "acct => 998" -f trace_account.cypher
```

### 6.6 Investigations (sections 4 and 5)

Each script runs the SQL and Cypher versions for sets A to F and compares the answers.

```bat
python q1.py
python q2.py          &:: also writes q2_daily.csv and q2_daily_charts.png
python q3.py          &:: writes q3_results.csv
python q4.py          &:: all 24 depth/set comparisons, q4 plot
python q5.py          &:: writes q5_results.csv
python q6.py          &:: writes q6_results.csv
python q7.py v3       &:: SQL version v1, v2 or v3; writes q7_results_v3.csv
```

Q7 SQL versions: `v1` baseline, `v2` deduplicated account-depth states, `v3` search from both ends. v3 is the selected version.

### 6.7 Correctness and performance (section 6)

```bat
python compare_61.py        &:: 61 cases, status table
python check_csv.py         &:: independent device-overlap and chain/cycle checks
python bench.py pg          &:: baseline SQL, 21 cases x (3 warm-ups + 5 runs)
python bench.py pg-v3       &:: Q7 with the improved SQL
python bench.py neo
python bench.py check       &:: PostgreSQL vs Neo4j answers (22 same, 0 different)
```

Results go to `bench_raw.csv` and `bench_summary.csv`; plans (`EXPLAIN (ANALYZE, BUFFERS)` and `PROFILE`) go to `plans_pg.txt`.

### 6.8 Concurrency (section 7)

Run one database service at a time (stop Neo4j when testing PostgreSQL and the reverse).

```bat
python t_mp.py              &:: control: main vs child process
python load_test.py pg
python load_test.py neo
```

Each client warms up A-B-C once, a barrier releases all clients, and each runs cycles until a 15 s deadline (a started cycle is always finished; 60 s query timeout). Every engine / workload / client-count test (1, 4, 8, 16 clients; Q4 depth 10 and Q7 bound 6) is repeated three times. Output: `load_raw.csv` and `load_reps.csv`.

### 6.9 Report

```bat
python build_report.py
```

Reads the screenshots from `screenshots/` and writes `Project_2_Mobile_Money_Analytics_Report.pdf`.

## 7. Verification

Generator unchanged:

```bat
git diff --exit-code mobile_money_generator.py
certutil -hashfile mobile_money_generator.py SHA256
```

Compare the SHA-256 value with the one of the file supplied with the assignment.

Rerun the 61-case comparison and confirm `61 OK`:

```bat
python compare_61.py
```

Stop the database services when finished and keep the stores:

```bat
neo4j stop
net stop postgresql-x64-18
```

(The PostgreSQL service name may differ; check `services.msc`.)

## 8. Reproducibility notes

- All dates and times in the questions use CAT (`Africa/Kigali`); boundaries are converted to epoch seconds in Python.
- Timings use `perf_counter` from query submission to receipt of the final row; completed runs and timeouts are stored separately.
- A first PostgreSQL load-test run at one client (Q7 median about 120 ms) was discarded after the control test `t_mp.py` showed that neither the child process nor the A-B-C alternation was responsible; the original file is kept as `load_reps_backup.csv` and the test was rerun on a quiet machine.
- Results hold for this machine, these sets (A to F) and these workloads.

## 9. Submission contents

| Deliverable | Content |
|---|---|
| PDF report | Sections 1 to 8 in milestone order, with evidence and individual notes |
| GitHub URL | This repository |
| ZIP | Matches the repository: generator, capture/import programs, definitions, queries, checks, benchmarks, raw results and plans |

## 10. Authors

HITAYEZU James (101381) · Joseph Courbon (101493) · Mylene MANIRAKIZA (101403)
