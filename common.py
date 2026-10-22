# common.py
import os, itertools
from datetime import datetime
from zoneinfo import ZoneInfo          # pip install tzdata (Windows)
import psycopg
from neo4j import GraphDatabase

KGL = ZoneInfo("Africa/Kigali")

# set: (review account, destination, September day)
SETS = {
    "A": (998,    24755,  6),
    "B": (147228, 186823, 13),
    "C": (206978, 6573,   8),
    "D": (237998, 21755,  6),
    "E": (144228, 183823, 13),
    "F": (203978, 3573,   8),
}

def hour_window(day):
    start = int(datetime(2026, 9, day, 9, 45, tzinfo=KGL).timestamp())
    return start, start + 3600          # 09:45 inclusive, 10:45 exclusive

PG_DSN = f"host=localhost port=5432 dbname=momo user=postgres password={os.environ.get('PGPASSWORD','')}"
NEO_URI, NEO_AUTH = "bolt://localhost:7687", ("neo4j", os.environ.get("NEO4J_PASSWORD", "12345678"))

_pg = None
_driver = None

def pg():
    global _pg
    if _pg is None or _pg.closed:
        _pg = psycopg.connect(PG_DSN, autocommit=True)
    return _pg

def neo():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(*[NEO_URI], auth=NEO_AUTH)
    return _driver

def norm(rows):
    return sorted(tuple(int(x) if isinstance(x, (int, bool)) or hasattr(x, "__int__") and not isinstance(x, str) else x
                        for x in r) for r in rows)

def run_pg(query, params=None, timeout_s=60):
    c = pg()
    with c.cursor() as cur:
        cur.execute(f"SET statement_timeout = {int(timeout_s*1000)}")
        cur.execute(query, params or {})
        return cur.fetchall()

def run_neo(query, params=None, timeout_s=60):
    with neo().session(database="neo4j") as s:
        res = s.run(query, params or {}, timeout=timeout_s)
        return [tuple(r.values()) for r in res]