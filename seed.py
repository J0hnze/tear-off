import os
import sqlite3
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
import random

load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.getenv("TICKETS_DB", "tickets.db")
DB_PATH = DB_NAME if os.path.isabs(DB_NAME) else os.path.join(APP_DIR, DB_NAME)

print(f"[INFO] Seeding database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

now = datetime.now()

def add(title, days_offset, priority=2, tags=None):
    due = (date.today() + timedelta(days=days_offset)).isoformat()
    cur.execute(
        """
        INSERT INTO tickets
        (title, priority, due_at, tags, status, created_at)
        VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (
            title,
            priority,
            due,
            tags,
            now.isoformat(timespec="seconds")
        )
    )

# -----------------------------
# Overdue tasks
# -----------------------------
add("Submit expense report", -5, 1, "work")
add("Book dentist appointment", -3, 2, "personal")
add("Renew SSL certificate", -2, 1, "work")

# -----------------------------
# Due today
# -----------------------------
add("Finish quarterly review", 0, 1, "work")
add("Wash the sheets", 0, 3, "personal")
add("Reply to Sam’s email", 0, 2, "work")

# -----------------------------
# This week
# -----------------------------
add("Prepare sprint demo", 1, 1, "work")
add("Buy groceries", 2, 3, "personal")
add("Update project roadmap", 3, 2, "work")
add("Gym session", 4, 3, "personal")

# -----------------------------
# Later this month
# -----------------------------
add("Plan holiday itinerary", 7, 3, "personal")
add("Refactor auth middleware", 10, 1, "work")
add("Car service booking", 12, 2, "personal")
add("Team 1:1 prep notes", 14, 2, "work")

conn.commit()
conn.close()

print("[INFO] Test tickets added.")
