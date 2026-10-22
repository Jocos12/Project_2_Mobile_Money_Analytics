with open("load_reps_backup.csv", encoding="utf-8-sig", newline="") as f:
    lines = [l for l in f.read().splitlines() if not l.startswith("PostgreSQL,")]
with open("load_reps.csv", "w", encoding="utf-8", newline="") as f:
    f.write("\n".join(lines) + "\n")
print(len(lines), "lignes ecrites")