"""
Theme management for ticket system
Handles dark/light theme preferences via cookies
"""
import os
from flask import request, render_template

# Get default theme from .env
DEFAULT_THEME = os.getenv("TICKETS_THEME", "dark").lower()
if DEFAULT_THEME not in ("dark", "light"):
    DEFAULT_THEME = "dark"


def get_theme():
    """Get current theme from cookies or default from .env"""
    t = (request.cookies.get("theme") or "").lower()
    return t if t in ("dark", "light") else DEFAULT_THEME


def render_with_theme(template, **ctx):
    """Render template with theme context"""
    ctx["theme"] = get_theme()
    return render_template(template, **ctx)
