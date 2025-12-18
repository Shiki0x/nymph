from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime, date

app = FastAPI()

# -----------------------------
# CORS CONFIGURATION (dev-friendly)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production you'll lock this to your real domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "nymph.db"


def init_db():
    """
    Initializes the database schema.
    We create tables if they do not exist.
    """
    with sqlite3.connect(DB_FILE) as conn:
        # Users table (identity only for now; auth comes later)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Habit logs table
        # NEW: category + notes are added as optional columns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                habit TEXT NOT NULL,
                completed INTEGER NOT NULL,
                category TEXT,        -- optional (can be NULL)
                notes TEXT,           -- optional (can be NULL)
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
    Create a user (no passwords/auth yet).
    Returns an id that we can attach habits to.
    """
    created_at = datetime.utcnow().isoformat()

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, created_at) VALUES (?, ?)",
                (username, created_at)
            )
            conn.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return {"error": "Username already exists"}

    return {"id": user_id, "username": username, "created_at": created_at}


# -----------------------------
# HABIT ENDPOINTS
# -----------------------------

@app.post("/log-habit")
def log_habit(
    user_id: int,
    habit: str,
    completed: bool,
    category: str | None = None,
    notes: str | None = None
):
    """
    Log a habit for a user.

    NEW:
    - category: optional label (ex: "fitness", "study")
    - notes: optional text for context (ex: "leg day", "read 20 pages")
    """
    created_at = datetime.utcnow().isoformat()
    completed_int = 1 if completed else 0

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO habit_logs (user_id, habit, completed, category, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, habit, completed_int, category, notes, created_at)
        )
        conn.commit()

    return {
        "message": "Saved!",
        "entry": {
            "user_id": user_id,
            "habit": habit,
            "completed": completed,
            "category": category,
            "notes": notes,
            "created_at": created_at
        }
    }


@app.get("/habits")
def get_habits(user_id: int):
    """
    Get all habit logs for a user (most recent first).
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            """
            SELECT habit, completed, category, notes, created_at
            FROM habit_logs
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()

    results = []
    for habit, completed_int, category, notes, created_at in rows:
        results.append({
            "habit": habit,
            "completed": bool(completed_int),
            "category": category,
            "notes": notes,
            "created_at": created_at
        })

    return results

@app.get("/streaks")
def get_streaks(user_id: int):
    """
    Calculate current daily streak for each habit for a user.

    Rule:
    - Count consecutive days ending today (or yesterday if not completed today)
    - Only days where completed=True count
    - Multiple logs in one day count as one day
    """

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            """
            SELECT habit, completed, created_at
            FROM habit_logs
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()

    # Step 1: Build a map of habit -> set of completion dates
    # We only care about days where completed=True
    habit_days = {}

    for habit, completed_int, created_at in rows:
        if not bool(completed_int):
            continue

        # created_at is stored as ISO string; parse date portion
        # Example: "2025-12-18T12:34:56.123456"
        day_str = created_at.split("T")[0]
        day = date.fromisoformat(day_str)

        habit_days.setdefault(habit, set()).add(day)

    # Step 2: For each habit, count consecutive days backward
    today = date.today()
    results = []

    for habit, days_set in habit_days.items():
        streak = 0

        # If habit done today, start counting from today.
        # If not, we allow streak to start from yesterday (common habit app behavior).
        if today in days_set:
            cursor_day = today
        else:
            cursor_day = today.replace(day=today.day)  # no-op, for clarity
            cursor_day = today.fromordinal(today.toordinal() - 1)  # yesterday

        # Count backward until we hit a missing day
        while cursor_day in days_set:
            streak += 1
            cursor_day = cursor_day.fromordinal(cursor_day.toordinal() - 1)

        results.append({"habit": habit, "streak": streak})

    # Optional: include habits with 0 streak if they exist but no completions
    # (We'll add that later when we normalize habits into their own table.)

    return results
