"""
Routes module for ticket system
Handles all Flask route definitions organized by feature
"""
import os
import logging
from datetime import date
from flask import Blueprint, redirect, url_for, flash, request
from modules.db import generate_ticket_id
from modules.auth import require_auth
from modules.theme import render_with_theme
from modules.db import get_db, now_iso, normalize_tags, generate_ticket_id
from modules.dates import start_of_week, end_of_week, start_of_month, end_of_month
from modules.print import print_line, print_cut, print_ticket, print_flush

# Get default tags from .env
DEFAULT_TAGS = os.getenv("TICKETS_DEFAULT_TAGS", "work,personal")

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("routes", __name__)

# ==================================================
# HOME & NAVIGATION
# ==================================================

@bp.route("/")
@require_auth
def home():
    return redirect(url_for("routes.today"))


# ==================================================
# VIEW ROUTES (today, weekly, monthly)
# ==================================================

@bp.route("/today")
@require_auth
def today():
    db = get_db()

    outstanding = db.execute(
        """
        SELECT * FROM tickets
        WHERE status='open'
          AND (due_at IS NULL OR date(due_at) <= date('now'))
        ORDER BY priority DESC, due_at
        """
    ).fetchall()

    return render_with_theme("today.html", outstanding=outstanding)


@bp.route("/weekly")
@require_auth
def week_view():
    db = get_db()

    today = date.today()
    week_start = start_of_week(today)
    week_end = end_of_week(today)

    week_tasks = db.execute(
        """
        SELECT * FROM tickets
        WHERE status = 'open'
          AND due_at IS NOT NULL
          AND date(due_at) BETWEEN date(?) AND date(?)
        ORDER BY due_at, priority DESC
        """,
        (week_start.isoformat(), week_end.isoformat())
    ).fetchall()

    no_date_tasks = db.execute(
        """
        SELECT * FROM tickets
        WHERE status = 'open'
          AND due_at IS NULL
        ORDER BY priority DESC, created_at
        """
    ).fetchall()

    return render_with_theme(
        "weekly.html",
        week_start=week_start,
        week_end=week_end,
        week_tasks=week_tasks,
        no_date_tasks=no_date_tasks,
        today=today
    )


@bp.route("/monthly")
@require_auth
def month_view():
    db = get_db()

    today = date.today()
    month_start = start_of_month(today)
    month_end = end_of_month(today)

    rows = db.execute(
        """
        SELECT * FROM tickets
        WHERE status = 'open'
          AND due_at IS NOT NULL
          AND date(due_at) BETWEEN date(?) AND date(?)
        ORDER BY due_at, priority DESC
        """,
        (month_start.isoformat(), month_end.isoformat())
    ).fetchall()

    # Prepare calendar context for template
    month = month_start.strftime('%B')
    year = month_start.year
    first_day = month_start
    last_day = month_end
    tasks_by_day = {}
    for t in rows:
        try:
            d = date.fromisoformat(t["due_at"][:10])
            key = d.strftime('%Y-%m-%d')
            tasks_by_day.setdefault(key, []).append(t)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid due_at date format: {t['due_at']}: {e}")
            continue

    today_str = date.today().strftime('%Y-%m-%d')

    return render_with_theme(
        "monthly.html",
        month=month,
        year=year,
        first_day=first_day,
        last_day=last_day,
        tasks_by_day=tasks_by_day,
        today=today_str
    )


@bp.route("/tickets")
@require_auth
def all_tickets():
    db = get_db()

    tickets = db.execute(
        """
        SELECT * FROM tickets
        WHERE status='open'
        ORDER BY priority DESC, due_at
        """
    ).fetchall()

    return render_with_theme("tickets.html", tickets=tickets)


@bp.route("/history")
@require_auth
def history():
    db = get_db()

    tickets = db.execute(
        """
        SELECT * FROM tickets
        WHERE status='closed'
        ORDER BY closed_at DESC
        """
    ).fetchall()

    return render_with_theme("history.html", tickets=tickets)


# ==================================================
# TICKET MANAGEMENT
# ==================================================

@bp.route("/add", methods=["POST"])
@require_auth
def add_ticket():
    """Add a new ticket with validation"""
    try:
        # Validate required fields
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required", "error")
            return redirect(request.referrer or url_for("routes.today"))

        # Validate priority is an integer
        try:
            priority = int(request.form.get("priority", 2))
            if priority < 1 or priority > 5:
                flash("Priority must be between 1 and 5", "error")
                return redirect(request.referrer or url_for("routes.today"))
        except (ValueError, TypeError):
            flash("Invalid priority value", "error")
            return redirect(request.referrer or url_for("routes.today"))

        # Optional fields
        due_date = request.form.get("due_date", "").strip() or None
        tags_input = request.form.get("tags", "").strip()
        # Use provided tags or default to TICKETS_DEFAULT_TAGS
        tags = normalize_tags(tags_input) if tags_input else normalize_tags(DEFAULT_TAGS)

        # Insert ticket
        db = get_db()
        db.execute(
            """
            INSERT INTO tickets
            (id, title, priority, due_at, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (generate_ticket_id(), title, priority, due_date, tags, now_iso())
        )
        db.commit()
        flash(f"Ticket '{title}' created", "ok")
        return redirect(url_for("routes.today"))

    except Exception as e:
        logger.error(f"Error adding ticket: {e}")
        flash("Failed to create ticket", "error")
        return redirect(request.referrer or url_for("routes.today"))


# ==================================================
# PRINT ROUTES
# ==================================================

@bp.route("/print/test")
@require_auth
def print_test():
    print_line("HELLO FROM FLASK")
    print_cut()
    print_flush()
    return "OK"


@bp.route("/print/ticket/<ticket_id>", methods=["POST"])
@require_auth
def print_single(ticket_id):
    db = get_db()
    t = db.execute(
        "SELECT * FROM tickets WHERE id=?",
        (ticket_id,)
    ).fetchone()

    if not t:
        flash("Ticket not found", "error")
        return redirect(url_for("routes.today"))

    print_ticket(t)
    print_cut()
    print_flush()

    flash("Ticket printed", "ok")
    return redirect(url_for("routes.today"))


@bp.route("/print/weekly", methods=["POST"])
@require_auth
def print_weekly():
    """Print all tasks for the current week"""
    db = get_db()

    today = date.today()
    week_start = start_of_week(today)
    week_end = end_of_week(today)

    week_tasks = db.execute(
        """
        SELECT * FROM tickets
        WHERE status = 'open'
          AND due_at IS NOT NULL
          AND date(due_at) BETWEEN date(?) AND date(?)
        ORDER BY due_at, priority DESC
        """,
        (week_start.isoformat(), week_end.isoformat())
    ).fetchall()

    # Print header
    print_line("=" * 46)
    print_line(f"WEEK {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}".center(46))
    print_line("=" * 46)
    print_line("")

    # Print each ticket
    if week_tasks:
        for t in week_tasks:
            print_ticket(t)
    else:
        print_line("No tasks this week".center(46))
        print_line("")

    # Print footer
    print_line("=" * 46)
    print_cut()
    print_flush()

    flash("Week printed", "ok")
    return redirect(url_for("routes.week_view"))


@bp.route("/print/free", methods=["POST"])
@require_auth
def print_free():
    """Print free-form text without adding to database"""
    text = request.form.get("free_text", "").strip()
    
    if not text:
        flash("Please enter text to print", "error")
        return redirect(request.referrer or url_for("routes.today"))
    
    try:
        sep = "=" * 42
        print_line(sep)
        
        # Word wrap the text to fit the printer width
        words = text.split()
        line = ""
        for w in words:
            if len(line) + len(w) + 1 <= 42:
                line = f"{line} {w}".strip()
            else:
                print_line(line.center(42))
                line = w
        if line:
            print_line(line.center(42))
        
        print_line(sep)
        print_cut()
        print_flush()
        
        flash("Text printed", "ok")
    except Exception as e:
        logger.error(f"Error printing free text: {e}")
        flash("Failed to print text", "error")
    
    return redirect(request.referrer or url_for("routes.today"))


# ==================================================
# TICKET STATUS MANAGEMENT
# ==================================================

@bp.route("/done/<ticket_id>", methods=["POST"])
@require_auth
def mark_done(ticket_id):
    """Mark a ticket as done"""
    db = get_db()
    
    # Verify ticket exists
    t = db.execute(
        "SELECT id, title FROM tickets WHERE id=?",
        (ticket_id,)
    ).fetchone()

    if not t:
        flash("Ticket not found", "error")
        return redirect(request.referrer or url_for("routes.today"))

    # Update ticket status to closed
    db.execute(
        "UPDATE tickets SET status='closed', closed_at=? WHERE id=?",
        (now_iso(), ticket_id)
    )
    db.commit()
    
    flash(f"'{t['title']}' marked done", "ok")
    return redirect(request.referrer or url_for("routes.today"))


# ==================================================
# SETTINGS
# ==================================================

@bp.route("/theme/<mode>")
@require_auth
def set_theme(mode):
    if mode not in ("dark", "light"):
        return redirect(request.referrer or url_for("routes.today"))

    resp = redirect(request.referrer or url_for("routes.today"))
    resp.set_cookie("theme", mode, max_age=31536000, samesite="Lax")
    return resp
