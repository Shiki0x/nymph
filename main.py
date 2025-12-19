from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import sqlite3
import json
from datetime import datetime

# -----------------------------
# App setup
# -----------------------------
app = FastAPI()

# CORS lets your frontend (running on port 5500) call your backend (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev this is fine. Later we'll lock this down.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "nymph.db"

# -----------------------------
# Database helpers
# -----------------------------
def get_conn():
    """
    Opens a connection to SQLite.
    check_same_thread=False allows FastAPI to access the DB from multiple threads during dev.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # This allows dict-like access to columns
    return conn


def init_db():
    """
    Creates tables if they don't exist.
    This keeps your project "plug and play" on fresh clones.
    """
    conn = get_conn()
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        bio TEXT DEFAULT ''
    )
    """)

    # Habits table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        habit TEXT NOT NULL,
        category TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        completed INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Links table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        url TEXT NOT NULL,
        icon TEXT DEFAULT 'link',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Cards table (Profile Cards)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        content_json TEXT NOT NULL,
        is_public INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


# Run DB init once when the app starts
init_db()


# -----------------------------
# Utility: user fetching / creation
# -----------------------------
def get_or_create_user(username: str, display_name: str = None, bio: str = ""):
    """
    If the user exists, return it.
    If not, create it.
    This keeps your dev workflow smooth (no separate "register" step needed yet).
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()

    if row:
        conn.close()
        return dict(row)

    # If user doesn't exist, create them
    if not display_name:
        display_name = username.upper()

    cur.execute(
        "INSERT INTO users (username, display_name, bio) VALUES (?, ?, ?)",
        (username, display_name, bio)
    )
    conn.commit()

    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    return dict(row)


# -----------------------------
# Users endpoints
# -----------------------------
@app.get("/users/by-username")
def get_user_by_username(username: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"error": "User not found"}

    return dict(row)


@app.post("/users/upsert")
def upsert_user(username: str, display_name: str = None, bio: str = ""):
    """
    Dev-friendly: ensures a user exists and can update basic fields.
    """
    user = get_or_create_user(username=username, display_name=display_name, bio=bio)

    # Update if display_name or bio passed
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET display_name = ?, bio = ? WHERE id = ?",
        (display_name or user["display_name"], bio or user["bio"], user["id"])
    )
    conn.commit()
    conn.close()

    # Return latest
    return get_user_by_username(username)


# -----------------------------
# Habits endpoints
# -----------------------------
@app.post("/log-habit")
def log_habit(user_id: int, habit: str, completed: bool, category: str = "", notes: str = ""):
    """
    Creates a habit log row.
    We store completed as 1/0 because SQLite doesn't have a native boolean type.
    """
    conn = get_conn()
    cur = conn.cursor()

    created_at = datetime.utcnow().isoformat()

    cur.execute("""
        INSERT INTO habits (user_id, habit, category, notes, completed, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, habit, category, notes, 1 if completed else 0, created_at))

    conn.commit()
    conn.close()

    return {"ok": True}


@app.get("/habits")
def get_habits(user_id: int):
    """
    Returns habits newest-first.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, habit, category, notes, completed, created_at
        FROM habits
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    # Convert completed integer back into boolean for the frontend
    result = []
    for r in rows:
        d = dict(r)
        d["completed"] = bool(d["completed"])
        result.append(d)

    return result


# -----------------------------
# Links endpoints
# -----------------------------
@app.post("/links/add")
def add_link(user_id: int, label: str, url: str, icon: str = "link"):
    """
    Adds a link to the user's profile.
    icon is a short key like: github, youtube, website, etc.
    """
    conn = get_conn()
    cur = conn.cursor()

    created_at = datetime.utcnow().isoformat()

    cur.execute("""
        INSERT INTO links (user_id, label, url, icon, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, label, url, icon, created_at))

    conn.commit()
    conn.close()

    return {"ok": True}


@app.get("/links")
def get_links(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, label, url, icon, created_at
        FROM links
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]


# -----------------------------
# Cards endpoints (Phase 2)
# -----------------------------
@app.post("/cards/add")
def add_card(user_id: int, type: str, title: str, content_json: str, is_public: bool = True):
    """
    Adds a profile card.
    - type: "quote" | "list" | "anime_grid" | "text"
    - title: card title
    - content_json: JSON string (we validate it is valid JSON)
    """
    # Validate JSON so we don't store broken content
    try:
        json.loads(content_json)
    except Exception:
        raise HTTPException(status_code=400, detail="content_json must be valid JSON")

    conn = get_conn()
    cur = conn.cursor()

    created_at = datetime.utcnow().isoformat()

    cur.execute("""
        INSERT INTO cards (user_id, type, title, content_json, is_public, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, type, title, content_json, 1 if is_public else 0, created_at))

    conn.commit()
    conn.close()

    return {"ok": True}


@app.get("/cards/by-user")
def get_cards_by_user(user_id: int):
    """
    Returns all cards for a user (dev view).
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, type, title, content_json, is_public, created_at
        FROM cards
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    cards = []
    for r in rows:
        d = dict(r)
        d["is_public"] = bool(d["is_public"])
        d["content"] = json.loads(d.pop("content_json"))
        cards.append(d)
    return cards


@app.get("/cards")
def get_public_cards(username: str):
    """
    Public profile endpoint: returns public cards by username.
    This is what profile.html uses.
    """
    user = get_user_by_username(username)
    if "error" in user:
        return []

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, type, title, content_json, is_public, created_at
        FROM cards
        WHERE user_id = ? AND is_public = 1
        ORDER BY id DESC
    """, (user["id"],))

    rows = cur.fetchall()
    conn.close()

    cards = []
    for r in rows:
        d = dict(r)
        d["is_public"] = bool(d["is_public"])
        d["content"] = json.loads(d.pop("content_json"))
        cards.append(d)
    return cards


@app.delete("/cards/delete")
def delete_card(user_id: int, card_id: int):
    """
    Deletes a card owned by the user.
    We check user_id so you can't delete other people's cards.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM cards WHERE id = ? AND user_id = ?", (card_id, user_id))
    conn.commit()

    deleted = cur.rowcount  # how many rows were removed
    conn.close()

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Card not found (or not owned by user)")

    return {"ok": True}
