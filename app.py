import os
import logging
from dotenv import load_dotenv

# Load environment variables FIRST, before importing modules
load_dotenv()

from flask import Flask, render_template

from modules.db import get_db, close_db, DB_PATH
from modules.routes import bp

# ==================================================
# LOGGING SETUP
# ==================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================================================
# CONFIG
# ==================================================

HOST = os.getenv("TICKETS_HOST", "127.0.0.1")
PORT = int(os.getenv("TICKETS_PORT", "5000"))

app = Flask(__name__)
app.secret_key = os.getenv("TICKETS_SECRET", "dev-secret")

logger.info(f"DB: {DB_PATH}")

# ==================================================
# APP SETUP
# ==================================================
app.teardown_appcontext(close_db)
app.register_blueprint(bp)


# ==================================================
# ERROR HANDLERS
# ==================================================
@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        status_code=404,
        message="Page not found"
    ), 404


@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return render_template(
        "error.html",
        status_code=500,
        message="Internal server error",
        details=str(error)
    ), 500


@app.errorhandler(Exception)
def handle_exception(error):
    logger.error(f"Unhandled exception: {error}")
    return render_template(
        "error.html",
        status_code=500,
        message="Something went wrong",
        details=str(error)
    ), 500


# ==================================================
if __name__ == "__main__":
    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        use_reloader=False
    )
