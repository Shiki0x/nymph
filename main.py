# FastAPI is the web framework that lets us build APIs
from fastapi import FastAPI

# This middleware allows a browser-based frontend (our UI)
# to talk to the backend even though they run on different ports
from fastapi.middleware.cors import CORSMiddleware

# sqlite3 is built into Python — no install required
# It lets us create and interact with a lightweight database file
import sqlite3

# Used to attach timestamps to habit logs
from datetime import datetime

# Create the FastAPI application instance
# Think of this as "the server"
app = FastAPI()

# -----------------------------
# CORS CONFIGURATION
# -----------------------------
# Browsers block requests between different origins by default.
# Since our frontend runs on :5500 and backend on :8000,
# we must explicitly allow this communication.
# This is safe for development. We'll lock it down later for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Allow requests from any origin (dev only)
    allow_credentials=True,
    allow_methods=["*"],      # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],      # Allow all headers
)

# -----------------------------
# DATABASE SETUP
# -----------------------------

# This is the SQLite database file.
# If it does not exist, SQLite will create it automatically.
DB_FILE = "nymph.db"


def init_db():
    """
    Create database tables if they do not already exist.

    This function runs once when the app starts.
    """
    # Connect to the SQLite database file
    # 'with' ensures the connection closes automatically
    with sqlite3.connect(DB_FILE) as conn:

        # Execute a SQL command to create the habit_logs table
        # IF NOT EXISTS prevents crashing if the table already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit TEXT NOT NULL,
                completed INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Commit ensures the changes are saved to disk
        conn.commit()


# -----------------------------
# APP STARTUP EVENT
# -----------------------------

@app.on_event("startup")
def on_startup():
    """
    FastAPI calls this automatically when the server starts.

    We use it to initialize the database so tables exist
    before handling any requests.
    """
    init_db()


# -----------------------------
# API ENDPOINTS
# -----------------------------

@app.post("/log-habit")
def log_habit(habit: str, completed: bool):
    """
    Store a habit log in the database.

    Parameters:
    - habit: name of the habit (string)
    - completed: whether the habit was completed (boolean)
    """

    # Capture the current time in a standard format
    created_at = datetime.utcnow().isoformat()

    # SQLite does not have a boolean type
    # Convention is to store booleans as integers:
    # 1 = True, 0 = False
    completed_int = 1 if completed else 0

    # Open a connection to the database
    with sqlite3.connect(DB_FILE) as conn:

        # Insert a new row into the habit_logs table
        # '?' placeholders prevent SQL injection
        conn.execute(
            """
            INSERT INTO habit_logs (habit, completed, created_at)
            VALUES (?, ?, ?)
            """,
            (habit, completed_int, created_at)
        )

        # Save the change
        conn.commit()

    # Send a response back to the frontend
    return {
        "message": "Saved!",
        "entry": {
            "habit": habit,
            "completed": completed,
            "created_at": created_at
        }
    }


@app.get("/habits")
def get_habits():
    """
    Retrieve all habit logs from the database.

    Returns:
    - A list of habit entries (most recent first)
    """

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            """
            SELECT habit, completed, created_at
            FROM habit_logs
            ORDER BY id DESC
            """
        )

        # Fetch all rows returned by the query
        rows = cursor.fetchall()

    # Convert database rows into JSON-friendly dictionaries
    habits = []
    for habit, completed_int, created_at in rows:
        habits.append({
            "habit": habit,
            "completed": bool(completed_int),  # convert 0/1 back to True/False
            "created_at": created_at
        })

    return habits
