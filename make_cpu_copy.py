import csv

# 1. copie du script avec d'autres fichiers de sortie
src = open("load_test.py", encoding="utf-8").read()
for name in ("load_raw", "load_reps", "load_summary"):
    src = src.replace(f'"{name}.csv"', f'"{name}_cpu.csv"')
open("load_test_cpu.py", "w", encoding="utf-8").write(src)

# 2. fichier reps de la copie : tout sauf PostgreSQL / Q7b6 / 16 clients
with open("load_reps.csv", encoding="utf-8-sig", newline="") as f:
    rd = csv.DictReader(f)
    cols = rd.fieldnames
    rows = [r for r in rd
            if not (r["engine"] == "Neo4j" and r["workload"] == "Q7b6" and r["clients"] == "16")]
with open("load_reps_cpu.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
print(len(rows), "lignes dans load_reps_cpu.csv (attendu : 45)")