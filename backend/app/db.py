import json
import sqlite3
import threading
import time

from .config import DB_PATH

_lock = threading.Lock()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  relation TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL,
  message TEXT NOT NULL,
  claimed_sender TEXT NOT NULL DEFAULT '',
  analysis TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER NOT NULL,
  contact_id INTEGER NOT NULL,
  to_phone TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'sent',
  note TEXT NOT NULL DEFAULT '',
  sent_at REAL NOT NULL,
  responded_at REAL
);
"""

with _lock:
    _conn.executescript(SCHEMA)
    _conn.commit()


def now() -> float:
    return time.time()


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def query(sql: str, params=(), one=False):
    with _lock:
        cur = _conn.execute(sql, params)
        rows = cur.fetchall()
    rows = [dict(r) for r in rows]
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql: str, params=()) -> int:
    with _lock:
        cur = _conn.execute(sql, params)
        _conn.commit()
        return cur.lastrowid


def load_case(case_id: int):
    row = query("SELECT * FROM cases WHERE id=?", (case_id,), one=True)
    if row:
        row["analysis"] = json.loads(row["analysis"])
    return row
