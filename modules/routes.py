"""
Routes module for ticket system
Handles all Flask route definitions organized by feature
"""
import os
import logging
from datetime import date, timedelta
from flask import Blueprint, redirect, url_for, flash, request, jsonify
from modules.auth import require_auth
from modules.theme import render_with_theme
from modules.db import (
    get_db,
    now_iso,
    normalize_tags,
    generate_ticket_id,
    get_setting,
    set_setting,
)
from modules.dates import start_of_week, end_of_week, end_of_month
from modules.print import print_line, print_cut, print_ticket, print_flush, set_line_width

# Get default tags from .env
DEFAULT_TAGS = os.getenv("TICKETS_DEFAULT_TAGS", "work,personal")

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("routes", __name__)


def _build_due_at(due_date, due_time):
    """Build a single due_at value from date/time form fields."""
    if not due_date:
        return None
    if due_time:
        return f"{due_date}T{due_time}"
    return due_date


def _safe_format(template, default, **kwargs):
    """Format templates from settings without crashing on bad placeholders."""
    try:
        return template.format(**kwargs)
    except Exception:
        return default.format(**kwargs)


def _client_label(ticket):
    """Use first tag as client label for weekly summary print lines."""
    tags = (ticket["tags"] or "").split(",")
    first = tags[0].strip() if tags else ""
    return first.upper() if first else "GENERAL"


def _format_print_line(text, align="left", size="medium", width=46):
    """Apply simple alignment and size styling before printing."""
    if text is None:
        text = ""
    line = str(text)
    size = (size or "medium").lower()
    align = (align or "left").lower()

    if size == "large":
        line = line.upper()
    elif size == "small":
        line = line.lower()

    if align == "center":
        return line.center(width)
    if align == "right":
        return line.rjust(width)
    return line

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

    completed_today = db.execute(
        """
        SELECT * FROM tickets
        WHERE status IN ('closed', 'done')
          AND closed_at IS NOT NULL
          AND date(closed_at) = date('now')
        ORDER BY closed_at DESC
        """
    ).fetchall()

    return render_with_theme(
        "today.html",
        outstanding=outstanding,
        completed_today=completed_today
    )


@bp.route("/weekly")
@require_auth
def week_view():
    db = get_db()

    today = date.today()
    week_offset = request.args.get("week_offset", default=0, type=int) or 0
    target_date = today + timedelta(weeks=week_offset)
    week_start = start_of_week(target_date)
    week_end = end_of_week(target_date)

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

    # Build day schedule with tasks for each day
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_schedule = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_date_str = day_date.strftime('%Y-%m-%d')
        
        # Filter tasks for this day
        day_tasks = [t for t in week_tasks if t["due_at"][:10] == day_date_str]
        
        day_schedule.append({
            'name': days[i],
            'date_str': day_date_str,
            'tasks': day_tasks
        })

    return render_with_theme(
        "weekly.html",
        week_start=week_start,
        week_end=week_end,
        week_tasks=week_tasks,
        no_date_tasks=no_date_tasks,
        today=today,
        day_schedule=day_schedule,
        week_offset=week_offset
    )


@bp.route("/monthly")
@require_auth
def month_view():
    db = get_db()

    # Get month and year from query params, default to today
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    
    if year is None or month is None:
        today = date.today()
        year = today.year
        month = today.month
    
    # Create a date object for the requested month
    month_start = date(year, month, 1)
    month_end = end_of_month(month_start)
    today = date.today()

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
    month_name = month_start.strftime('%B')
    month_num = month_start.month
    year_num = month_start.year
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

    # Calculate previous and next month for navigation
    if month_num == 1:
        prev_month, prev_year = 12, year_num - 1
    else:
        prev_month, prev_year = month_num - 1, year_num
    
    if month_num == 12:
        next_month, next_year = 1, year_num + 1
    else:
        next_month, next_year = month_num + 1, year_num

    return render_with_theme(
        "monthly.html",
        month=month_name,
        year=year_num,
        first_day=month_start,
        last_day=month_end,
        tasks_by_day=tasks_by_day,
        today=today_str,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year
    )


@bp.route("/calendar")
@require_auth
def calendar_view():
    """Display FullCalendar with tasks"""
    db = get_db()
    
    # Get tag from query params
    tag = request.args.get("tag", "all").strip()
    
    # Get view type from query params
    initial_view = request.args.get("view", "dayGridMonth").strip()
    
    # Get all unique tags for the filter dropdown
    all_tags_result = db.execute(
        "SELECT DISTINCT tags FROM tickets WHERE status='open' AND tags IS NOT NULL"
    ).fetchall()
    
    all_tags = set()
    for row in all_tags_result:
        if row["tags"]:
            # Split comma-separated tags
            tags_list = [t.strip() for t in row["tags"].split(",")]
            all_tags.update(tags_list)
    
    all_tags = sorted(list(all_tags))
    
    return render_with_theme(
        "calendar.html",
        tag=tag,
        all_tags=all_tags,
        initial_view=initial_view
    )


@bp.route("/api/events")
@require_auth
def api_events():
    """API endpoint for FullCalendar to fetch events"""
    db = get_db()
    
    # Get query parameters from FullCalendar
    start_str = request.args.get("start", "").strip()
    end_str = request.args.get("end", "").strip()
    tag = request.args.get("tag", "all").strip()
    
    # Validate dates
    if not start_str or not end_str:
        return jsonify([])
    
    # Get tickets for the date range
    tickets = db.execute(
        """
        SELECT * FROM tickets
        WHERE status = 'open'
          AND due_at IS NOT NULL
          AND date(due_at) BETWEEN date(?) AND date(?)
        ORDER BY due_at, priority DESC
        """,
        (start_str, end_str)
    ).fetchall()
    
    # Convert to FullCalendar event format
    events = []
    for ticket in tickets:
        # Filter by tag if not "all"
        if tag != "all":
            ticket_tags = [t.strip() for t in (ticket["tags"] or "").split(",")]
            if tag not in ticket_tags:
                continue
        
        # Extract due_at date (remove time if present)
        due_date = ticket["due_at"][:10] if ticket["due_at"] else None
        if not due_date:
            continue
        
        # Determine color based on priority
        priority = ticket["priority"] if ticket["priority"] is not None else 2
        if priority <= 1:
            color = "#dc3545"  # red
        elif priority == 2:
            color = "#ffc107"  # yellow
        elif priority == 3:
            color = "#17a2b8"  # cyan
        else:
            color = "#28a745"  # green
        
        event = {
            "id": ticket["id"],
            "title": ticket["title"],
            "start": due_date,
            "backgroundColor": color,
            "borderColor": color,
            "extendedProps": {
                "priority": priority,
                "tags": ticket["tags"] or "",
                "kind": "ticket"
            }
        }
        events.append(event)
    
    return jsonify(events)


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
        WHERE status IN ('closed', 'done')
        ORDER BY closed_at DESC
        """
    ).fetchall()

    return render_with_theme("history.html", tickets=tickets)


# ==================================================
# TICKET MANAGEMENT
# ==================================================

@bp.route("/add", methods=["GET", "POST"])
@require_auth
def add_ticket():
    """Display add ticket form (GET) or add a new ticket (POST)"""
    if request.method == "GET":
        # Display the add ticket form
        db = get_db()
        
        # Get all unique tags
        all_tags_result = db.execute(
            "SELECT DISTINCT tags FROM tickets WHERE tags IS NOT NULL"
        ).fetchall()
        
        all_tags = set()
        for row in all_tags_result:
            if row["tags"]:
                tags_list = [t.strip() for t in row["tags"].split(",")]
                all_tags.update(tags_list)
        
        all_tags = sorted(list(all_tags))
        
        # Get due date from query params if provided
        due_prefill = request.args.get("due", "").strip() or None
        default_date = date.today().isoformat()
        
        return render_with_theme(
            "add.html",
            all_tags=all_tags,
            due_prefill=due_prefill,
            default_date=default_date
        )
    
    # Handle POST request - add a new ticket
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
        due_time = request.form.get("due_time", "").strip() or None
        due_at = _build_due_at(due_date, due_time)
        notes = request.form.get("notes", "").strip() or None
        start_at = request.form.get("start_at", "").strip() or None
        end_at = request.form.get("end_at", "").strip() or None
        all_day = 1 if request.form.get("all_day", "1").strip() == "1" else 0
        recurrence = request.form.get("recurrence", "none").strip() or "none"
        recurrence_time = request.form.get("recurrence_time", "09:00").strip() or "09:00"
        recurrence_start = request.form.get("recurrence_start", "").strip() or None
        if recurrence != "none" and not recurrence_start:
            recurrence_start = due_date or date.today().isoformat()
        tags_input = request.form.get("tags", "").strip()
        # Use provided tags or default to TICKETS_DEFAULT_TAGS
        tags = normalize_tags(tags_input) if tags_input else normalize_tags(DEFAULT_TAGS)

        # Insert ticket
        db = get_db()
        db.execute(
            """
            INSERT INTO tickets
            (
              id, title, notes, priority, due_at, start_at, end_at, all_day,
              recurrence, recurrence_time, recurrence_start, status, tags, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                generate_ticket_id(),
                title,
                notes,
                priority,
                due_at,
                start_at,
                end_at,
                all_day,
                recurrence,
                recurrence_time,
                recurrence_start,
                tags,
                now_iso(),
            )
        )
        db.commit()
        flash(f"Ticket '{title}' created", "ok")
        return redirect(url_for("routes.today"))

    except Exception as e:
        logger.error(f"Error adding ticket: {e}")
        flash("Failed to create ticket", "error")
        return redirect(request.referrer or url_for("routes.today"))


@bp.route("/quick-add", methods=["POST"])
@require_auth
def quick_add():
    """Quick add a single ticket from compact form."""
    try:
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required", "error")
            return redirect(request.referrer or url_for("routes.today"))

        try:
            priority = int(request.form.get("priority", 2))
        except (TypeError, ValueError):
            priority = 2
        priority = min(max(priority, 1), 5)

        due_date = request.form.get("due_date", "").strip() or None
        due_time = request.form.get("due_time", "").strip() or None
        due_at = _build_due_at(due_date, due_time)
        start_at = request.form.get("start_at", "").strip() or None
        end_at = request.form.get("end_at", "").strip() or None
        all_day = 1 if request.form.get("all_day", "1").strip() == "1" else 0
        recurrence = request.form.get("recurrence", "none").strip() or "none"
        recurrence_time = request.form.get("recurrence_time", "09:00").strip() or "09:00"
        recurrence_start = request.form.get("recurrence_start", "").strip() or None
        if recurrence != "none" and not recurrence_start:
            recurrence_start = due_date or date.today().isoformat()

        tags_input = request.form.get("tags", "").strip()
        tags = normalize_tags(tags_input) if tags_input else normalize_tags(DEFAULT_TAGS)

        db = get_db()
        db.execute(
            """
            INSERT INTO tickets
            (
              id, title, notes, priority, due_at, start_at, end_at, all_day,
              recurrence, recurrence_time, recurrence_start, status, tags, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                generate_ticket_id(),
                title,
                None,
                priority,
                due_at,
                start_at,
                end_at,
                all_day,
                recurrence,
                recurrence_time,
                recurrence_start,
                tags,
                now_iso(),
            )
        )
        db.commit()
        flash(f"Ticket '{title}' created", "ok")
    except Exception as e:
        logger.error(f"Error in quick add: {e}")
        flash("Failed to add ticket", "error")
    return redirect(request.referrer or url_for("routes.today"))


@bp.route("/quick-add-weekly", methods=["POST"])
@require_auth
def quick_add_weekly():
    """Quick add tasks for weekly view with duration"""
    try:
        # Get form data
        title = request.form.get("title", "").strip()
        tag = request.form.get("tag", "work").strip()
        duration = int(request.form.get("duration", 1))
        start_date_str = request.form.get("start_date", "").strip()
        
        if not title:
            flash("Title is required", "error")
            return redirect(request.referrer or url_for("routes.week_view"))
        
        if duration < 1 or duration > 5:
            flash("Duration must be between 1 and 5 days", "error")
            return redirect(request.referrer or url_for("routes.week_view"))
        
        # Parse start date
        try:
            start_date = date.fromisoformat(start_date_str)
        except (ValueError, TypeError):
            start_date = date.today()
        
        # Normalize the tag
        tags = normalize_tags(tag)
        
        db = get_db()
        
        # Create a task for each day of the duration
        for i in range(duration):
            task_date = start_date + timedelta(days=i)
            db.execute(
                """
                INSERT INTO tickets
                (id, title, priority, due_at, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (generate_ticket_id(), title, 3, task_date.isoformat(), tags, now_iso())
            )
        
        db.commit()
        flash(f"Task '{title}' added for {duration} day(s)", "ok")
        return redirect(url_for("routes.week_view"))

    except Exception as e:
        logger.error(f"Error in quick add weekly: {e}")
        flash("Failed to add task", "error")
        return redirect(request.referrer or url_for("routes.week_view"))


# ==================================================
# PRINT ROUTES
# ==================================================

@bp.route("/print/all", methods=["POST"])
@require_auth
def print_all():
    """Print all currently outstanding tasks."""
    db = get_db()
    outstanding = db.execute(
        """
        SELECT * FROM tickets
        WHERE status='open'
          AND (due_at IS NULL OR date(due_at) <= date('now'))
        ORDER BY priority DESC, due_at
        """
    ).fetchall()

    print_line("=" * 46)
    print_line("TODAY OUTSTANDING".center(46))
    print_line("=" * 46)
    print_line("")

    if outstanding:
        for t in outstanding:
            print_ticket(t)
    else:
        print_line("No outstanding tickets".center(46))
        print_line("")

    print_line("=" * 46)
    print_cut()
    print_flush()

    flash("Printed outstanding tickets", "ok")
    return redirect(request.referrer or url_for("routes.today"))

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

    print_cols = get_setting(db, "print_cols", "46")
    weekly_separator = get_setting(db, "weekly_separator", "---")
    weekly_header_template = get_setting(db, "weekly_header_template", "WEEK NUMBER {week}")
    weekly_line_template = get_setting(
        db,
        "weekly_line_template",
        "{day} - {title}"
    )
    weekly_align = get_setting(db, "weekly_align", "left")
    weekly_font_size = get_setting(db, "weekly_font_size", "medium")
    set_line_width(print_cols)
    try:
        print_width = int(print_cols)
    except (TypeError, ValueError):
        print_width = 46

    today = date.today()
    week_offset = request.form.get("week_offset", type=int, default=0) or 0
    target_date = today + timedelta(weeks=week_offset)
    week_start = start_of_week(target_date)
    week_end = end_of_week(target_date)

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

    week_number = target_date.isocalendar()[1]
    day_labels = ["MON", "TUES", "WEDS", "THURS", "FRI"]

    print_line(weekly_separator)
    print_line(
        _format_print_line(
            _safe_format(
                weekly_header_template,
                "WEEK NUMBER {week}",
                week=week_number
            ),
            align=weekly_align,
            size=weekly_font_size,
            width=print_width,
        )
    )
    print_line(weekly_separator)

    for i in range(5):
        day_date = week_start + timedelta(days=i)
        day_tasks = [t for t in week_tasks if t["due_at"] and t["due_at"][:10] == day_date.isoformat()]
        if day_tasks:
            for task in day_tasks:
                print_line(
                    _format_print_line(
                        _safe_format(
                            weekly_line_template,
                            "{day} - {title}",
                            day=day_labels[i],
                            client=_client_label(task),
                            title=task["title"],
                        ),
                        align=weekly_align,
                        size=weekly_font_size,
                        width=print_width,
                    )
                )
        else:
            print_line(
                _format_print_line(
                    _safe_format(
                        weekly_line_template,
                        "{day} - {title}",
                        day=day_labels[i],
                        client="-",
                        title="-",
                    ),
                    align=weekly_align,
                    size=weekly_font_size,
                    width=print_width,
                )
            )

    print_line(weekly_separator)
    print_cut()
    print_flush()

    flash("Week printed", "ok")
    return redirect(url_for("routes.week_view", week_offset=week_offset))


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
# COUNTERS (separate from tickets)
# ==================================================

@bp.route("/counters")
@require_auth
def counters_view():
    db = get_db()
    counters = db.execute(
        """
        SELECT id, description, count, created_at
        FROM counters
        ORDER BY created_at DESC
        """
    ).fetchall()
    return render_with_theme("counters.html", counters=counters)


@bp.route("/counters/add", methods=["POST"])
@require_auth
def add_counter():
    description = request.form.get("description", "").strip()
    if not description:
        flash("Counter description is required", "error")
        return redirect(url_for("routes.counters_view"))

    db = get_db()
    db.execute(
        """
        INSERT INTO counters (id, description, count, created_at)
        VALUES (?, ?, 0, ?)
        """,
        (generate_ticket_id(), description, now_iso())
    )
    db.commit()
    flash(f"Counter '{description}' created", "ok")
    return redirect(url_for("routes.counters_view"))


@bp.route("/counters/inc/<counter_id>", methods=["POST"])
@require_auth
def increment_counter(counter_id):
    db = get_db()
    cur = db.execute(
        "UPDATE counters SET count = count + 1 WHERE id = ?",
        (counter_id,)
    )
    db.commit()

    if cur.rowcount == 0:
        flash("Counter not found", "error")
    else:
        flash("Counter increased by 1", "ok")
    return redirect(url_for("routes.counters_view"))


@bp.route("/counters/print/<counter_id>", methods=["POST"])
@require_auth
def print_counter(counter_id):
    db = get_db()
    counter = db.execute(
        "SELECT id, description, count FROM counters WHERE id = ?",
        (counter_id,)
    ).fetchone()
    if not counter:
        flash("Counter not found", "error")
        return redirect(url_for("routes.counters_view"))

    set_line_width(get_setting(db, "print_cols", "46"))
    counter_separator = get_setting(db, "counter_separator", "---")
    counter_header_template = get_setting(db, "counter_header_template", "COUNTER")
    counter_description_template = get_setting(
        db,
        "counter_description_template",
        "{description}"
    )
    counter_count_template = get_setting(db, "counter_count_template", "COUNT: {count}")
    counter_align = get_setting(db, "counter_align", "left")
    counter_font_size = get_setting(db, "counter_font_size", "medium")
    try:
        print_width = int(get_setting(db, "print_cols", "46"))
    except (TypeError, ValueError):
        print_width = 46

    print_line(counter_separator)
    print_line(
        _format_print_line(
            _safe_format(
                counter_header_template,
                "COUNTER",
                description=counter["description"],
                count=counter["count"],
            ),
            align=counter_align,
            size=counter_font_size,
            width=print_width,
        )
    )
    print_line(counter_separator)
    print_line(
        _format_print_line(
            _safe_format(
                counter_description_template,
                "{description}",
                description=counter["description"],
                count=counter["count"],
            ),
            align=counter_align,
            size=counter_font_size,
            width=print_width,
        )
    )
    print_line("")
    print_line(
        _format_print_line(
            _safe_format(
                counter_count_template,
                "COUNT: {count}",
                description=counter["description"],
                count=counter["count"],
            ),
            align=counter_align,
            size=counter_font_size,
            width=print_width,
        )
    )
    print_line(counter_separator)
    print_cut()
    print_flush()

    flash("Counter printed", "ok")
    return redirect(url_for("routes.counters_view"))


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


@bp.route("/settings", methods=["GET", "POST"])
@require_auth
def settings_view():
    db = get_db()
    if request.method == "POST":
        try:
            print_cols = int(request.form.get("print_cols", "46"))
        except (TypeError, ValueError):
            print_cols = 46
        print_cols = min(max(print_cols, 16), 96)

        weekly_separator = request.form.get("weekly_separator", "---").strip() or "---"
        weekly_header_template = (
            request.form.get("weekly_header_template", "WEEK NUMBER {week}").strip()
            or "WEEK NUMBER {week}"
        )
        weekly_line_template = (
            request.form.get("weekly_line_template", "{day} - {title}").strip()
            or "{day} - {title}"
        )
        weekly_align = request.form.get("weekly_align", "left").strip().lower()
        if weekly_align not in ("left", "center", "right"):
            weekly_align = "left"
        weekly_font_size = request.form.get("weekly_font_size", "medium").strip().lower()
        if weekly_font_size not in ("small", "medium", "large"):
            weekly_font_size = "medium"
        counter_separator = request.form.get("counter_separator", "---").strip() or "---"
        counter_header_template = (
            request.form.get("counter_header_template", "COUNTER").strip()
            or "COUNTER"
        )
        counter_description_template = (
            request.form.get("counter_description_template", "{description}").strip()
            or "{description}"
        )
        counter_count_template = (
            request.form.get("counter_count_template", "COUNT: {count}").strip()
            or "COUNT: {count}"
        )
        counter_align = request.form.get("counter_align", "left").strip().lower()
        if counter_align not in ("left", "center", "right"):
            counter_align = "left"
        counter_font_size = request.form.get("counter_font_size", "medium").strip().lower()
        if counter_font_size not in ("small", "medium", "large"):
            counter_font_size = "medium"

        set_setting(db, "print_cols", str(print_cols))
        set_setting(db, "weekly_separator", weekly_separator)
        set_setting(db, "weekly_header_template", weekly_header_template)
        set_setting(db, "weekly_line_template", weekly_line_template)
        set_setting(db, "weekly_align", weekly_align)
        set_setting(db, "weekly_font_size", weekly_font_size)
        set_setting(db, "counter_separator", counter_separator)
        set_setting(db, "counter_header_template", counter_header_template)
        set_setting(db, "counter_description_template", counter_description_template)
        set_setting(db, "counter_count_template", counter_count_template)
        set_setting(db, "counter_align", counter_align)
        set_setting(db, "counter_font_size", counter_font_size)
        db.commit()
        flash("Print settings saved", "ok")
        return redirect(url_for("routes.settings_view"))

    return render_with_theme(
        "settings.html",
        print_cols=get_setting(db, "print_cols", "46"),
        weekly_separator=get_setting(db, "weekly_separator", "---"),
        weekly_header_template=get_setting(db, "weekly_header_template", "WEEK NUMBER {week}"),
        weekly_line_template=get_setting(
            db,
            "weekly_line_template",
            "{day} - {title}"
        ),
        weekly_align=get_setting(db, "weekly_align", "left"),
        weekly_font_size=get_setting(db, "weekly_font_size", "medium"),
        counter_separator=get_setting(db, "counter_separator", "---"),
        counter_header_template=get_setting(db, "counter_header_template", "COUNTER"),
        counter_description_template=get_setting(
            db,
            "counter_description_template",
            "{description}"
        ),
        counter_count_template=get_setting(db, "counter_count_template", "COUNT: {count}"),
        counter_align=get_setting(db, "counter_align", "left"),
        counter_font_size=get_setting(db, "counter_font_size", "medium"),
    )


@bp.route("/config")
@require_auth
def config_view():
    return redirect(url_for("routes.settings_view"))
