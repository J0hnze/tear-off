"""
Authentication module for ticket system
Handles basic HTTP authentication and authorization
"""
import os
import base64
from functools import wraps
from flask import Response, request

# ==================================================
# CONFIG
# ==================================================
USER = os.getenv("TICKETS_USER", "admin")
PASS = os.getenv("TICKETS_PASS", "admin")


# ==================================================
# BASIC AUTH
# ==================================================

def _unauthorized():
    """Return 401 Unauthorized response"""
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Tickets"'}
    )


def _check_auth(header):
    """Verify Basic auth header credentials"""
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode()
        u, p = decoded.split(":", 1)
        return u == USER and p == PASS
    except Exception:
        return False


def require_auth(fn):
    """Decorator to require authentication on a route"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _check_auth(request.headers.get("Authorization")):
            return _unauthorized()
        return fn(*args, **kwargs)
    return wrapper
