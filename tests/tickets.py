import argparse
import sqlite3
from datetime import datetime, date
import os
import sys
import textwrap
import tempfile

DB_PATH = os.path.join(os.path.dirname(__file__), "tickets.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  notes TEXT,
  priority INTEGER DEFAULT 2,
  due_at TEXT,
  status TEXT DEFAULT 'open',
  created_at TEXT NOT NULL
);
"""

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(SCHEMA)
    return conn

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def parse_due(due: str | None) -> str | None:
    if not due:
        return None
    # Accept: "2026-02-06" or "2026-02-06 14:30"
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(due, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=9, minute=0)  # sensible default
            return dt.isoformat(timespec="minutes")
        except ValueError:
            pass
    raise SystemExit("Invalid --due format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM")

def cmd_add(args):
    conn = db()
    due = parse_due(args.due)
    conn.execute(
        "INSERT INTO tickets(title, notes, priority, due_at, status, created_at) VALUES(?,?,?,?,?,?)",
        (args.title, args.notes, args.priority, due, "open", now_iso())
    )
    conn.commit()
    print("Added.")

def cmd_list(args):
    conn = db()
    rows = conn.execute(
        "SELECT id, title, priority, due_at, status FROM tickets WHERE status='open' ORDER BY priority DESC, due_at IS NULL, due_at"
    ).fetchall()
    if not rows:
        print("No open tickets.")
        return
    for tid, title, prio, due_at, status in rows:
        due_str = due_at.replace("T", " ") if due_at else "-"
        print(f"#{tid} [P{prio}] due: {due_str}  {title}")

def cmd_done(args):
    conn = db()
    cur = conn.execute("UPDATE tickets SET status='done' WHERE id=? AND status!='done'", (args.id,))
    conn.commit()
    print("Done." if cur.rowcount else "No change (id not found or already done).")

def today_range():
    start = datetime.combine(date.today(), datetime.min.time()).isoformat(timespec="seconds")
    end = datetime.combine(date.today(), datetime.max.time()).isoformat(timespec="seconds")
    return start, end

def build_today_sheet():
    conn = db()
    start, end = today_range()
    rows = conn.execute(
        """
        SELECT id, title, notes, priority, due_at
        FROM tickets
        WHERE status='open'
          AND (due_at BETWEEN ? AND ? OR due_at IS NULL)
        ORDER BY priority DESC, due_at IS NULL, due_at
        """,
        (start, end),
    ).fetchall()

    lines = []
    lines.append("TODAY - TICKETS")
    lines.append(datetime.now().strftime("%A %d %b %Y %H:%M"))
    lines.append("=" * 40)
    if not rows:
        lines.append("No open tickets for today.")
    else:
        for tid, title, notes, prio, due_at in rows[:20]:
            due_str = (due_at.replace("T", " ") if due_at else "no due time")
            lines.append(f"#{tid}  [P{prio}]  ({due_str})")
            lines.append(f"  {title}")
            if notes:
                wrapped = textwrap.wrap(notes, width=38)
                for w in wrapped[:4]:
                    lines.append(f"  - {w}")
            lines.append("  [ ] next action: ______________________")
            lines.append("-" * 40)

    lines.append("\nNOTES / BRAIN DUMP:")
    lines.append("_" * 40)
    lines.append("_" * 40)
    return "\n".join(lines)

def print_text_windows(text: str):
    # Writes to temp file and uses the default "print" verb (works on many Windows setups)
    fd, path = tempfile.mkstemp(suffix=".txt", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.startfile(path, "print")  # type: ignore[attr-defined]

def cmd_print_today(args):
    sheet = build_today_sheet()
    if args.preview:
        print(sheet)
        return

    if os.name == "nt":
        print_text_windows(sheet)
        print("Sent to default printer.")
    else:
        # On Linux/macOS, you’d typically use lp/lpr
        # Example: echo "..." | lp
        print("Non-Windows printing not configured in this starter. Use --preview for now.")
        print(sheet)

def main():
    p = argparse.ArgumentParser(prog="tickets", description="Tiny ticket system with printable daily sheet")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="Add a ticket")
    pa.add_argument("title")
    pa.add_argument("--notes", default=None)
    pa.add_argument("--priority", type=int, default=2, choices=[1,2,3,4])
    pa.add_argument("--due", default=None, help="YYYY-MM-DD or YYYY-MM-DD HH:MM")
    pa.set_defaults(func=cmd_add)

    pl = sub.add_parser("list", help="List open tickets")
    pl.set_defaults(func=cmd_list)

    pd = sub.add_parser("done", help="Mark ticket done")
    pd.add_argument("id", type=int)
    pd.set_defaults(func=cmd_done)

    ppt = sub.add_parser("print-today", help="Print today's sheet")
    ppt.add_argument("--preview", action="store_true", help="Print to console instead of printer")
    ppt.set_defaults(func=cmd_print_today)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
