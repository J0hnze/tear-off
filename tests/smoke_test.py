import base64
import os
import sqlite3
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app
from modules.db import DB_PATH


def _auth_header():
    user = os.getenv("TICKETS_USER", "admin")
    password = os.getenv("TICKETS_PASS", "admin")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _cleanup_titles(titles):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM tickets WHERE title IN ({','.join(['?'] * len(titles))})",
        tuple(titles),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


def _cleanup_counters(descriptions):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM counters WHERE description IN ({','.join(['?'] * len(descriptions))})",
        tuple(descriptions),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


def main():
    run_id = uuid.uuid4().hex[:8]
    add_title = f"smoke-add-{run_id}"
    quick_title = f"smoke-quick-{run_id}"
    quick_single_title = f"smoke-quick-single-{run_id}"
    counter_desc = f"smoke-counter-{run_id}"

    checks = []
    headers = _auth_header()
    created_titles = []
    created_counters = []

    try:
        with app.test_client() as client:
            checks.append(("weekly_no_auth", client.get("/weekly").status_code == 401))
            checks.append(
                ("weekly_with_auth", client.get("/weekly", headers=headers).status_code == 200)
            )
            checks.append(("weekly_session", client.get("/weekly").status_code == 200))

            add_resp = client.post(
                "/add",
                headers=headers,
                follow_redirects=False,
                data={
                    "title": add_title,
                    "priority": "2",
                    "due_date": "2026-03-06",
                    "due_time": "10:00",
                    "tags": "work",
                    "notes": "smoke",
                    "recurrence": "none",
                    "all_day": "1",
                },
            )
            checks.append(("add_post_redirect", add_resp.status_code == 302))
            created_titles.append(add_title)

            quick_resp = client.post(
                "/quick-add-weekly",
                headers=headers,
                follow_redirects=False,
                data={
                    "title": quick_title,
                    "tag": "work",
                    "duration": "2",
                    "start_date": "2026-03-02",
                },
            )
            checks.append(("quick_add_post_redirect", quick_resp.status_code == 302))
            created_titles.append(quick_title)

            quick_single_resp = client.post(
                "/quick-add",
                headers=headers,
                follow_redirects=False,
                data={
                    "title": quick_single_title,
                    "priority": "3",
                    "due_date": "2026-03-08",
                    "due_time": "09:15",
                    "tags": "personal",
                    "all_day": "1",
                    "recurrence": "none",
                },
            )
            checks.append(("quick_add_single_redirect", quick_single_resp.status_code == 302))
            created_titles.append(quick_single_title)

            events_resp = client.get(
                "/api/events?start=2026-01-01&end=2026-12-31", headers=headers
            )
            checks.append(("api_events_ok", events_resp.status_code == 200))
            checks.append(("api_events_is_list", isinstance(events_resp.get_json(), list)))

            counters_page = client.get("/counters", headers=headers)
            checks.append(("counters_page_ok", counters_page.status_code == 200))

            settings_page = client.get("/settings", headers=headers)
            checks.append(("settings_page_ok", settings_page.status_code == 200))

            settings_save_resp = client.post(
                "/settings",
                headers=headers,
                follow_redirects=False,
                data={
                    "print_cols": "46",
                    "weekly_separator": "---",
                    "weekly_header_template": "WEEK NUMBER {week}",
                    "weekly_line_template": "{day} - {title}",
                    "weekly_align": "left",
                    "weekly_font_size": "medium",
                    "counter_separator": "---",
                    "counter_header_template": "COUNTER",
                    "counter_description_template": "{description}",
                    "counter_count_template": "COUNT: {count}",
                    "counter_align": "left",
                    "counter_font_size": "medium",
                },
            )
            checks.append(("settings_save_redirect", settings_save_resp.status_code == 302))

            counter_add_resp = client.post(
                "/counters/add",
                headers=headers,
                follow_redirects=False,
                data={"description": counter_desc},
            )
            checks.append(("counter_add_redirect", counter_add_resp.status_code == 302))
            created_counters.append(counter_desc)

            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                "SELECT id, count FROM counters WHERE description = ?",
                (counter_desc,),
            ).fetchone()
            conn.close()
            checks.append(("counter_created", row is not None and row[0] is not None))

            if row:
                counter_id = row[0]
                inc_resp = client.post(
                    f"/counters/inc/{counter_id}",
                    headers=headers,
                    follow_redirects=False,
                )
                checks.append(("counter_inc_redirect", inc_resp.status_code == 302))
    finally:
        if created_titles:
            _cleanup_titles(created_titles)
        if created_counters:
            _cleanup_counters(created_counters)

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'}")

    if failed:
        print("\nFailed checks:")
        for name in failed:
            print(f"- {name}")
        raise SystemExit(1)

    print("\nSmoke test passed.")


if __name__ == "__main__":
    main()
