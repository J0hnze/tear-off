"""
Date utility functions for ticket scheduling
"""
from datetime import timedelta


def start_of_week(d):
    """Return Monday of the week for date d"""
    return d - timedelta(days=d.weekday())


def end_of_week(d):
    """Return Sunday of the week for date d"""
    return start_of_week(d) + timedelta(days=6)


def start_of_month(d):
    """Return the first day of the month for date d"""
    return d.replace(day=1)


def end_of_month(d):
    """Return the last day of the month for date d"""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)
