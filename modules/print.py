"""
Printer module for BIXOLON SRP-E300 thermal printer
Handles all printing operations and Windows printer integration
"""
import os
import logging

# ==================================================
# CONFIG
# ==================================================
NO_PRINTER = os.getenv("NO_PRINTER", "false").strip().lower() == "true"
LINE_WIDTH = int(os.getenv("TICKETS_PRINT_COLS", "32"))
PRINTER_NAME = os.getenv("TICKETS_PRINTER_NAME", "BIXOLON SRP-E300")
DEBUG_PRINT = os.getenv("DEBUG_PRINT", "false").strip().lower() == "true"

logger = logging.getLogger(__name__)

# ==================================================
# PRINTER SETUP (WINDOWS / BIXOLON)
# ==================================================
printer = None  # <-- MUST exist unconditionally

if not NO_PRINTER:
    try:
        from escpos.printer import Win32Raw
        printer = Win32Raw(PRINTER_NAME)
        logger.info(f"Printer initialised: {PRINTER_NAME}")
    except Exception as e:
        logger.error(f"Printer init failed: {e}")
        printer = None
else:
    logger.info("NO_PRINTER enabled → console output only")

# ==================================================
# PRINT HELPERS
# ==================================================

def print_line(text=""):
    """Print a line of text to printer or console"""
    if DEBUG_PRINT:
        logger.debug(f"NO_PRINTER={NO_PRINTER}, printer={printer}")
    
    if NO_PRINTER or printer is None:
        print(text)
    else:
        try:
            printer.text(text + "\n")
        except Exception as e:
            logger.error(f"Print failed: {e}")
            print(text)


def print_cut():
    """Cut the paper (or print dashes in console mode)"""
    if NO_PRINTER or printer is None:
        print("-" * LINE_WIDTH)
    else:
        try:
            printer.cut()
        except Exception as e:
            logger.error(f"Cut failed: {e}")


def print_ticket(t):
    """Print a formatted ticket"""
    sep = "*" * (LINE_WIDTH - 4)

    def center(s):
        return s.center(LINE_WIDTH - 4)

    print_line(sep)

    header = f"P{t['priority']}"
    if t["tags"]:
        header += f" [{t['tags'].upper()}]"
    print_line(center(header))
    print_line("")

    title = t["title"].upper()
    words = title.split()
    line = ""

    for w in words:
        if len(line) + len(w) + 1 <= LINE_WIDTH:
            line = f"{line} {w}".strip()
        else:
            print_line(center(line))
            line = w
    if line:
        print_line(center(line))

    print_line("")

    if t["due_at"]:
        print_line(center(f"DUE {t['due_at'][:10]}"))

    print_line(sep)
    print_line("")


def print_flush():
    """Force Windows spooler to flush print buffer by closing connection"""
    global printer
    if NO_PRINTER or printer is None:
        return
    try:
        if hasattr(printer, "close"):
            printer.close()
            logger.info("Printer closed - job sent to spooler")
        else:
            logger.debug("Printer has no close method")
    except Exception as e:
        logger.warning(f"Printer close failed: {e}")
