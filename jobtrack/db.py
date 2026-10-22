import json
import os
import sqlite3
from datetime import datetime, timedelta

DEFAULT_PATH = os.environ.get(
    "JOBTRACK_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jobtrack.db"))

STATUSES = ["saved", "applied", "interview", "offer", "rejected", "ghosted", "withdrawn"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    location TEXT,
    work_mode TEXT,
    skills TEXT NOT NULL,          -- JSON list
    deadline TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    url TEXT,
    posting TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'saved',
    issues TEXT NOT NULL,          -- JSON list from validate.check_extraction
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    score INTEGER NOT NULL,
    coverage INTEGER,
    summary TEXT,
    matched TEXT NOT NULL,
    missing TEXT NOT NULL,
    bullets TEXT NOT NULL,
    issues TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    status TEXT NOT NULL,
    note TEXT,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY,
    task TEXT NOT NULL,
    at TEXT NOT NULL,
    duration_ms INTEGER,
    cost_usd REAL,
    ok INTEGER NOT NULL,
    error TEXT,
    claims INTEGER,
    dropped INTEGER
);
"""

JSON_COLS = {"skills", "issues", "matched", "missing", "bullets"}


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect(path=DEFAULT_PATH):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for k in JSON_COLS & d.keys():
        d[k] = json.loads(d[k])
    return d


def add_job(conn, job, posting, url, issues):
    ts = now()
    cur = conn.execute(
        """INSERT INTO jobs (company, role, location, work_mode, skills, deadline,
           salary_min, salary_max, url, posting, issues, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job["company"], job["role"], job["location"], job["work_mode"],
         json.dumps(job["skills"]), job["deadline"], job["salary_min"], job["salary_max"],
         url, posting, json.dumps(issues), ts, ts))
    conn.execute("INSERT INTO events (job_id, status, note, at) VALUES (?,?,?,?)",
                 (cur.lastrowid, "saved", None, ts))
    conn.commit()
    return cur.lastrowid


def get_job(conn, job_id):
    return _row(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def list_jobs(conn, status=None):
    q = "SELECT * FROM jobs" + (" WHERE status = ?" if status else "") + " ORDER BY id"
    return [_row(r) for r in conn.execute(q, (status,) if status else ())]


def set_status(conn, job_id, status, note=None):
    ts = now()
    conn.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?", (status, ts, job_id))
    conn.execute("INSERT INTO events (job_id, status, note, at) VALUES (?,?,?,?)",
                 (job_id, status, note, ts))
    conn.commit()


def events(conn, job_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM events WHERE job_id = ? ORDER BY id", (job_id,))]


def add_match(conn, job_id, m, issues):
    conn.execute(
        """INSERT INTO matches (job_id, score, coverage, summary, matched, missing, bullets,
           issues, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (job_id, m["score"], m["coverage"], m["summary"], json.dumps(m["matched"]),
         json.dumps(m["missing"]), json.dumps(m["bullets"]), json.dumps(issues), now()))
    conn.commit()


def latest_match(conn, job_id):
    return _row(conn.execute(
        "SELECT * FROM matches WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,)).fetchone())


def stale(conn, days=14):
    """Applied jobs with no status change in `days` days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    return [_row(r) for r in conn.execute(
        "SELECT * FROM jobs WHERE status = 'applied' AND updated_at < ? ORDER BY updated_at",
        (cutoff,))]


def log_call(conn, task, ok, meta=None, error=None, claims=None, dropped=None):
    meta = meta or {}
    conn.execute(
        """INSERT INTO llm_calls (task, at, duration_ms, cost_usd, ok, error, claims, dropped)
           VALUES (?,?,?,?,?,?,?,?)""",
        (task, now(), meta.get("duration_ms"), meta.get("cost_usd"), int(ok), error,
         claims, dropped))
    conn.commit()


def call_stats(conn):
    return [dict(r) for r in conn.execute(
        """SELECT task, COUNT(*) AS calls, SUM(ok) AS ok,
                  ROUND(AVG(duration_ms) / 1000.0, 1) AS avg_s,
                  SUM(claims) AS claims, SUM(dropped) AS dropped
           FROM llm_calls GROUP BY task""")]
