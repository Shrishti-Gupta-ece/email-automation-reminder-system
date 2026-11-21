"""SQLite layer (standard library). Times are stored in UTC as 'YYYY-MM-DD HH:MM:SS'."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FMT = "%Y-%m-%d %H:%M:%S"


def db_path() -> Path:
    return Path(os.getenv("EMAIL_DB_PATH", BASE_DIR / "db" / "email.db"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  department TEXT DEFAULT '',
  unsubscribed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS templates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  subject TEXT NOT NULL,
  body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  template_id INTEGER NOT NULL REFERENCES templates(id),
  event_date TEXT DEFAULT '',
  event_time TEXT DEFAULT '',
  send_at TEXT NOT NULL,              -- first fire, UTC
  recurrence TEXT DEFAULT 'once',     -- once | daily | weekly
  rrule TEXT,                         -- optional RFC 5545 rule, overrides recurrence
  active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reminder_id INTEGER NOT NULL,
  occurrence TEXT NOT NULL,           -- which firing of the reminder
  to_email TEXT, to_name TEXT,
  subject TEXT, body TEXT,
  status TEXT NOT NULL,               -- queued | sent | dry_run | failed | skipped
  attempts INTEGER DEFAULT 0,
  error TEXT, mode TEXT,
  created_at TEXT, sent_at TEXT,
  UNIQUE(reminder_id, occurrence)     -- idempotency: one message per firing
);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def parse_dt(value: str) -> datetime:
    """Accept ISO strings (with or without Z / offset) and return naive UTC."""
    d = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if d.tzinfo:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d.replace(microsecond=0)


def from_db(value: str) -> datetime:
    return datetime.strptime(value, FMT)


def iso(value):
    """DB string -> ISO string with Z so the browser converts to local time."""
    return value.replace(" ", "T") + "Z" if value else None


@contextmanager
def get_conn():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
