
=====================================
             TEAR-OFF
=====================================
   A PRINTABLE TASK & TICKET SYSTEM

   • See the task
   • Print the task
   • Tear it off
   • Do the work

   If it isn't printed,
   it doesn't exist.
=====================================

## Features

- **Web-based ticket management** - Add, view, and manage tasks through a clean Flask interface
- **Multiple views** - Today, Weekly, Monthly, and Calendar views
- **Thermal printer support** - Print individual tickets or entire weeks with one click
- **Basic authentication** - Secure access with HTTP Basic Auth
- **Tag-based organization** - Filter and organize tasks by custom tags
- **Priority levels** - 5-level priority system (1=highest, 5=lowest)
- **Due date tracking** - Set deadlines for tickets
- **SQLite database** - Lightweight local storage
- **UUID-based ticket IDs** - Unique identifiers for all tickets

## Installation

### 1. Clone and setup

```bash
git clone <repo>
cd tear-off
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure printer (Windows only)

Check your printer name:
```bash
python tests/list-printers.py
```

Copy `example.env` to `.env` and update:
```env
TICKETS_USER=john
TICKETS_PASS=your-secure-password
NO_PRINTER=false
TICKETS_PRINTER_NAME=BIXOLON SRP-E300
TICKETS_PRINT_COLS=46
TICKETS_HOST=0.0.0.0
TICKETS_PORT=5000
```

### 3. Run the app

```bash
python app.py
```

Visit: `http://localhost:5000`

## Usage

### Web Interface

- **Home** (`/`) - Redirects to Today view
- **Today** (`/today`) - Tasks due today or overdue
- **Weekly** (`/weekly`) - Tasks due this week + undated tasks
- **Monthly** (`/monthly`) - Calendar view of all tasks due this month
- **Add ticket** - Form appears on each view

### Printing

- **Individual ticket** - Click print button on any ticket card
- **Full week** - Click "Print All" button on Weekly view
- **Test printer** - Visit `/print/test` to test connection

### Mark Done

Click "✓ Mark done" button to complete a ticket.

## Database

Tickets are stored in SQLite with UUID-based IDs:

| Field | Type | Notes |
|-------|------|-------|
| `id` | TEXT | UUID (Primary Key) |
| `title` | TEXT | Required |
| `notes` | TEXT | Optional detailed notes |
| `priority` | INT | 1-5 (default: 2) |
| `due_at` | TEXT | ISO datetime (optional) |
| `status` | TEXT | 'open' or 'closed' |
| `created_at` | TEXT | ISO datetime |
| `closed_at` | TEXT | ISO datetime (when marked done) |
| `tags` | TEXT | Comma-separated tags |

## Recent Changes (v1.1.0)

- ✨ **UUID-based ticket IDs** - Replaced integer IDs with UUIDs for better uniqueness
- 🖨️ **Print weekly button** - Added "Print All" button to Weekly view
- ✓ **Mark done functionality** - Implemented ticket completion workflow
- 🔧 **Improved printer handling** - Fixed buffer flushing for reliable thermal printing

## Configuration

All settings via environment variables (`.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `TICKETS_USER` | admin | Basic auth username |
| `TICKETS_PASS` | admin | Basic auth password |
| `NO_PRINTER` | false | Set `true` for console-only testing |
| `TICKETS_PRINTER_NAME` | BIXOLON SRP-E300 | Windows printer queue name |
| `TICKETS_PRINT_COLS` | 46 | Paper width in characters |
| `TICKETS_HOST` | 127.0.0.1 | Flask bind address |
| `TICKETS_PORT` | 5000 | Flask port |
| `TICKETS_DB` | tickets.db | Database file path |
| `TICKETS_SECRET` | dev-secret | Flask session secret |
| `TICKETS_DEFAULT_TAGS` | work,personal | Default tags for new tickets |
| `TICKETS_THEME` | dark | UI theme (dark/light) |

## Supported Platforms

- **Windows** - Full printer support (tested with BIXOLON SRP-E300)
- **macOS/Linux** - Web UI works, printer requires manual setup with escpos library

## Dependencies

- `flask` - Web framework
- `python-escpos` - Thermal printer driver
- `pywin32` - Windows printer integration  
- `python-dotenv` - Environment configuration

## Library References

- [python-escpos Documentation](https://python-escpos.readthedocs.io/en/latest/)
- [escpos Printer API](https://python-escpos.readthedocs.io/en/latest/api/escpos.html)



---

todo 
## TODO / Future Integrations
- [ ] add support for linux
- [ ] iCal export / subscription
  - [ ] Generate an `.ics` file for Today/Weekly/Monthly
  - [ ] Optional: publish a read-only URL protected by Basic Auth
- [ ] Telegram notifications
  - [ ] Send “Today at 09:00” summary to a Telegram chat via bot token
  - [ ] Send only filtered tags (e.g. work)
- [ ] Signal notifications
  - [ ] Send daily/weekly summary via signal-cli (self-hosted)
- [ ] Email reminders
  - [ ] SMTP support to email Today/Weekly tickets
- [ ] Webhooks
  - [ ] Generic webhook POST (for Home Assistant / n8n / Zapier / Make)
- [ ] Push notifications
  - [ ] ntfy.sh topic publish
- [ ] iOS/Android widgets (later)
  - [ ] Simple “Today count” endpoint for a widget consumer


  ===
  *note this was vibe coded late on a friday night with bailieys, so it probly full oh holes if you find somethign add it to an issue and ill fix it :) thanks
