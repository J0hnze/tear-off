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
  id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
  title TEXT NOT NULL,
  notes TEXT,
  priority INTEGER NOT NULL DEFAULT 2,
  due_at TEXT,
  start_at TEXT,
  end_at TEXT,
  all_day INTEGER DEFAULT 1,
  recurrence TEXT DEFAULT 'none',
  recurrence_time TEXT DEFAULT '09:00',
  recurrence_start TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  closed_at TEXT,
  tags TEXT
);
"""

TARGET_COLUMNS = (
    "id",
    "title",
    "notes",
    "priority",
    "due_at",
    "start_at",
    "end_at",
    "all_day",
    "recurrence",
    "recurrence_time",
    "recurrence_start",
    "status",
    "created_at",
    "closed_at",
    "tags",
)

def generate_ticket_id():
    """Generate a new UUID for a ticket"""
    return str(uuid.uuid4())


def _ticket_columns(conn):
    rows = conn.execute("PRAGMA table_info(tickets)").fetchall()
    return {
        row[1]: {"type": (row[2] or "").upper(), "pk": row[5], "notnull": row[3]}
        for row in rows
    }


def _rebuild_tickets_table(conn):
    cols = _ticket_columns(conn)
    conn.execute("ALTER TABLE tickets RENAME TO tickets_legacy")
    conn.executescript(SCHEMA)

    expressions = {
        "id": (
            "CASE WHEN id IS NULL OR trim(CAST(id AS TEXT))='' "
            "THEN lower(hex(randomblob(16))) ELSE CAST(id AS TEXT) END"
            if "id" in cols
            else "lower(hex(randomblob(16)))"
        ),
        "title": "title" if "title" in cols else "''",
        "notes": "notes" if "notes" in cols else "NULL",
        "priority": "COALESCE(priority, 2)" if "priority" in cols else "2",
        "due_at": "due_at" if "due_at" in cols else "NULL",
        "start_at": "start_at" if "start_at" in cols else "NULL",
        "end_at": "end_at" if "end_at" in cols else "NULL",
        "all_day": "COALESCE(all_day, 1)" if "all_day" in cols else "1",
        "recurrence": "COALESCE(recurrence, 'none')" if "recurrence" in cols else "'none'",
        "recurrence_time": (
            "COALESCE(recurrence_time, '09:00')" if "recurrence_time" in cols else "'09:00'"
        ),
        "recurrence_start": "recurrence_start" if "recurrence_start" in cols else "NULL",
        "status": (
            "CASE WHEN status='done' THEN 'closed' "
            "WHEN status IS NULL THEN 'open' ELSE status END"
            if "status" in cols
            else "'open'"
        ),
        "created_at": (
            "COALESCE(created_at, datetime('now'))" if "created_at" in cols else "datetime('now')"
        ),
        "closed_at": "closed_at" if "closed_at" in cols else "NULL",
        "tags": "tags" if "tags" in cols else "NULL",
    }

    select_expr = ", ".join(expressions[col] for col in TARGET_COLUMNS)
    conn.execute(
        f"""
        INSERT INTO tickets ({", ".join(TARGET_COLUMNS)})
        SELECT {select_expr}
        FROM tickets_legacy
        """
    )
    conn.execute("DROP TABLE tickets_legacy")


def _ensure_schema(conn):
    conn.executescript(SCHEMA)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS counters (
          id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
          description TEXT NOT NULL,
          count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("print_cols", os.getenv("TICKETS_PRINT_COLS", "46"))
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("weekly_separator", "---")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("weekly_header_template", "WEEK NUMBER {week}")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("weekly_line_template", "{day} - {title}")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("weekly_align", "left")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("weekly_font_size", "medium")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("counter_separator", "---")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("counter_header_template", "COUNTER")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("counter_description_template", "{description}")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("counter_count_template", "COUNT: {count}")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("counter_align", "left")
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
        ("counter_font_size", "medium")
    )
    # Migrate previous default format that included client/tag.
    conn.execute(
        """
        UPDATE app_settings
        SET value = ?
        WHERE key = 'weekly_line_template'
          AND value = ?
        """,
        ("{day} - {title}", "{day} - {client} - {title}")
    )
    cols = _ticket_columns(conn)
    if not cols:
        return

    id_col = cols.get("id", {})
    missing_cols = [col for col in TARGET_COLUMNS if col not in cols]
    id_is_compatible = (
        id_col.get("type") == "TEXT"
        and id_col.get("pk") == 1
        and id_col.get("notnull") == 1
    )

    if missing_cols or not id_is_compatible:
        _rebuild_tickets_table(conn)
    else:
        # Legacy CLI used status='done'; keep web history views consistent.
        conn.execute("UPDATE tickets SET status='closed' WHERE status='done'")


def get_setting(conn, key, default=None):
    """Get an app setting value by key."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    """Set or replace an app setting value."""
    conn.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value)
    )


# ==================================================
# DATABASE HELPERS
# ==================================================

def get_db():
    """Get database connection, create schema if needed"""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        _ensure_schema(g.db)
        g.db.commit()
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
