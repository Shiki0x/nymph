from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime, date

app = FastAPI()

# -----------------------------
# CORS (dev settings)
# -----------------------------
# This allows your frontend (http.server on port 5500) to call your backend (uvicorn on 8000).
# In production you would lock allow_origins down to your real domain(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "nymph.db"


def init_db():
    """
    Create tables if they don't exist.

    IMPORTANT:
    SQLite will NOT automatically add new columns to existing tables.
    If you changed schema and get 500 errors, delete nymph.db during early dev.
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                bio TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                habit TEXT NOT NULL,
                completed INTEGER NOT NULL,
                category TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.commit()


@app.on_event("startup")
def on_startup():
    init_db()


# -----------------------------
# USERS
# -----------------------------

@app.post("/users")
def create_user(username: str):
    """
    Create a user (no auth yet).
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


@app.patch("/users/profile")
def update_profile(user_id: int, display_name: str | None = None, bio: str | None = None):
    """
    Update a user's public profile fields.
    """
    with sqlite3.connect(DB_FILE) as conn:
        if display_name is not None:
            conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
        if bio is not None:
            conn.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, user_id))
        conn.commit()

    return {"message": "Profile updated", "user_id": user_id, "display_name": display_name, "bio": bio}


# -----------------------------
# HABITS
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

    return {"message": "Saved!"}


@app.get("/habits")
def get_habits(user_id: int):
    """
    Return all habit logs for a user (newest first).
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


# -----------------------------
# STREAKS
# -----------------------------

@app.get("/streaks")
def get_streaks(user_id: int):
    """
    Current daily streak per habit.

    Rules:
    - Only completed=True counts
    - Multiple completions in the same day count as ONE day
    - Count consecutive days backwards (today, or yesterday if not done today)
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

    # Build: habit -> set of dates where completed=True
    habit_days: dict[str, set[date]] = {}

    for habit, completed_int, created_at in rows:
        if not bool(completed_int):
            continue

        # created_at is ISO string, get YYYY-MM-DD part
        day_str = created_at.split("T")[0]
        d = date.fromisoformat(day_str)

        habit_days.setdefault(habit, set()).add(d)

    today = date.today()
    results = []

    for habit, days_set in habit_days.items():
        streak = 0

        # Start from today if completed today, otherwise from yesterday
        cursor_day = today if today in days_set else date.fromordinal(today.toordinal() - 1)

        while cursor_day in days_set:
            streak += 1
            cursor_day = date.fromordinal(cursor_day.toordinal() - 1)

        results.append({"habit": habit, "streak": streak})

    return results


# -----------------------------
# PUBLIC PROFILES
# -----------------------------

@app.get("/u/{username}")
def public_profile(username: str):
    """
    Public profile JSON (shareable).
    """
    with sqlite3.connect(DB_FILE) as conn:
        user_cur = conn.execute(
            """
            SELECT id, username, display_name, bio, created_at
            FROM users
            WHERE username = ?
            """,
            (username,)
        )
        user = user_cur.fetchone()

        if not user:
            return {"error": "User not found"}

        user_id, uname, display_name, bio, created_at = user

        total_logs = conn.execute(
            "SELECT COUNT(*) FROM habit_logs WHERE user_id = ?",
            (user_id,)
        ).fetchone()[0]

        completed_logs = conn.execute(
            "SELECT COUNT(*) FROM habit_logs WHERE user_id = ? AND completed = 1",
            (user_id,)
        ).fetchone()[0]

    return {
        "id": user_id,
        "username": uname,
        "display_name": display_name or uname,
        "bio": bio or "",
        "created_at": created_at,
        "stats": {
            "total_logs": total_logs,
            "completed_logs": completed_logs
        }
    }


@app.get("/u/{username}/summary")
def public_profile_summary(username: str):
    """
    Smaller profile payload for embedding on a profile page.
    """
    profile = public_profile(username)
    if "error" in profile:
        return profile

    return {
        "username": profile["username"],
        "display_name": profile["display_name"],
        "bio": profile["bio"],
        "stats": profile["stats"]
    }
