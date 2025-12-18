from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime

app = FastAPI()

# -----------------------------
# CORS CONFIGURATION
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "nymph.db"

# -----------------------------
# DATABASE INITIALIZATION
# -----------------------------

def init_db():
    """
    Create database tables if they do not already exist.
    This runs once when the server starts.
    """
    with sqlite3.connect(DB_FILE) as conn:

        # Users table
        # In the future this will support auth, profiles, etc.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Habit logs now belong to a user
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                habit TEXT NOT NULL,
                completed INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.commit()


@app.on_event("startup")
def on_startup():
    init_db()


# -----------------------------
# USER ENDPOINTS
# -----------------------------

@app.post("/users")
def create_user(username: str):
    """
    Create a new user.

    This is NOT authentication.
    Think of it as identity registration.
    """
    created_at = datetime.utcnow().isoformat()

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, created_at)
                VALUES (?, ?)
                """,
                (username, created_at)
            )
            conn.commit()

            user_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        return {"error": "Username already exists"}

    return {
        "id": user_id,
        "username": username,
        "created_at": created_at
    }


# -----------------------------
# HABIT ENDPOINTS (OWNED)
# -----------------------------

@app.post("/log-habit")
def log_habit(user_id: int, habit: str, completed: bool):
    """
    Store a habit log for a specific user.
    """

    created_at = datetime.utcnow().isoformat()
    completed_int = 1 if completed else 0

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO habit_logs (user_id, habit, completed, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, habit, completed_int, created_at)
        )
        conn.commit()

    return {
        "message": "Saved!",
        "habit": habit,
        "completed": completed,
        "user_id": user_id,
        "created_at": created_at
    }


@app.get("/habits")
def get_habits(user_id: int):
    """
    Retrieve all habits for a specific user.
    """

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            """
            SELECT habit, completed, created_at
            FROM habit_logs
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()

    habits = []
    for habit, completed_int, created_at in rows:
        habits.append({
            "habit": habit,
            "completed": bool(completed_int),
            "created_at": created_at
        })

    return habits
