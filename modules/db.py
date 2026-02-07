"""
Database module for ticket system
Handles SQLite setup, queries, and schema
"""
import os
import sqlite3
import uuid
from datetime import datetime
from flask import g

DB_NAME = os.getenv("TICKETS_DB", "tickets.db")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = DB_NAME if os.path.isabs(DB_NAME) else os.path.join(APP_DIR, "..", DB_NAME)

# ==================================================
# SCHEMA
# ==================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  notes TEXT,
  priority INTEGER NOT NULL DEFAULT 2,
  due_at TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  closed_at TEXT,
  tags TEXT
);
"""

def generate_ticket_id():
    """Generate a new UUID for a ticket"""
    return str(uuid.uuid4())


# ==================================================
# DATABASE HELPERS
# ==================================================

def get_db():
    """Get database connection, create schema if needed"""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.executescript(SCHEMA)
    return g.db


def close_db(_):
    """Close database connection (teardown handler)"""
    db = g.pop("db", None)
    if db:
        db.close()


def now_iso():
    """Return current datetime in ISO format"""
    return datetime.now().isoformat(timespec="seconds")


def normalize_tags(raw):
    """Normalize and deduplicate tags"""
    if not raw:
        return None
    return ",".join(
        dict.fromkeys(
            t.strip().lower().replace(" ", "-")
            for t in raw.split(",") if t.strip()
        )
    )
