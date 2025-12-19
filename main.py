from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import json
from datetime import datetime
from typing import Optional

app = FastAPI()

# Allow your frontend (running on port 5500) to call your backend (port 8000)
# In production you would restrict allow_origins to your real domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "nymph.db"


# ----------------------------
# Helpers
# ----------------------------

def now_iso() -> str:
    """Return a UTC timestamp as an ISO string."""
    return datetime.utcnow().isoformat()


def guess_icon_from_url(url: str) -> str:
    """
    Guess an icon key based on a URL's domain.
    This is a simple auto-detect helper for profile links.
    """
    u = (url or "").lower()

    if "github.com" in u:
        return "github"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "x.com" in u or "twitter.com" in u:
        return "x"
    if "instagram.com" in u:
        return "instagram"
    if "tiktok.com" in u:
        return "tiktok"
    if "twitch.tv" in u:
        return "twitch"
    if "discord.gg" in u or "discord.com" in u:
        return "discord"

    if u.startswith("http://") or u.startswith("https://"):
        return "website"

    return "link"


def init_db() -> None:
    """
    Create DB tables if they don't exist.
    Safe to run on every start.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          display_name TEXT NOT NULL,
          bio TEXT DEFAULT '',
          created_at TEXT NOT NULL
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          habit TEXT NOT NULL,
          category TEXT DEFAULT '',
          notes TEXT DEFAULT '',
          completed INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS profile_links (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          label TEXT NOT NULL,
          url TEXT NOT NULL,
          icon TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)

        # Phase 2: Flexible profile cards
        cur.execute("""
        CREATE TABLE IF NOT EXISTS profile_cards (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          type TEXT NOT NULL,
          title TEXT NOT NULL,
          content_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)

        conn.commit()


@app.on_event("startup")
def on_startup():
    init_db()


def get_user_by_username(username: str) -> Optional[dict]:
    """Return user row as dict, or None."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None


# ----------------------------
# Request Models (Pydantic)
# ----------------------------

class CardCreate(BaseModel):
    user_id: int
    type: str
    title: str
    content: dict  # This is the JSON body for the card


# ----------------------------
# Root
# ----------------------------

@app.get("/")
def root():
    return {"message": "NYMPH backend is running"}


# ----------------------------
# Users
# ----------------------------

@app.post("/users")
def create_user(username: str, display_name: str, bio: str = ""):
    """
    Create a new user profile.
    """
    username_clean = username.strip().lower()

    with sqlite3.connect(DB_FILE) as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, display_name, bio, created_at) VALUES (?, ?, ?, ?)",
                (username_clean, display_name.strip(), bio.strip(), now_iso())
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return {"error": "Username already exists"}

    return {"message": "User created", "username": username_clean}


@app.get("/users/by-username")
def get_user(username: str):
    """
    Fetch a user profile by username.
    """
    user = get_user_by_username(username)
    if not user:
        return {"error": "User not found"}
    return user


# ----------------------------
# Habits
# ----------------------------

@app.post("/log-habit")
def log_habit(
    user_id: int,
    habit: str,
    completed: bool,
    category: str = "",
    notes: str = ""
):
    """
    Log a habit event for a user.
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO habit_logs (user_id, habit, category, notes, completed, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, habit.strip(), category.strip(), notes.strip(), int(completed), now_iso())
        )
        conn.commit()

    return {"message": "Habit logged"}


@app.get("/habits")
def list_habits(user_id: int):
    """
    Return all habit logs for a user (latest first).
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, habit, category, notes, completed, created_at
            FROM habit_logs
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ----------------------------
# Links
# ----------------------------

@app.post("/links")
def add_link(user_id: int, label: str, url: str, icon: str = "auto"):
    """
    Add a link to a user's profile.
    icon = "auto" will guess based on URL.
    """
    icon_key = (icon or "auto").strip().lower()
    if icon_key == "auto":
        icon_key = guess_icon_from_url(url)

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO profile_links (user_id, label, url, icon, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, label.strip(), url.strip(), icon_key, now_iso())
        )
        conn.commit()

    return {"message": "Link added", "icon": icon_key}


@app.get("/links")
def list_links(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, label, url, icon, created_at
            FROM profile_links
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


@app.delete("/links")
def delete_link(id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM profile_links WHERE id = ?", (id,))
        conn.commit()
    return {"message": "Link deleted"}


# ----------------------------
# Profile Cards (Phase 2) - JSON Body version (IMPORTANT)
# ----------------------------

@app.post("/cards")
def create_card(payload: CardCreate = Body(...)):
    """
    Create a profile card using JSON in request body.
    This avoids URL encoding / length issues.
    """
    type_clean = payload.type.strip().lower()
    content_obj = payload.content

    # Basic validation per type
    if type_clean == "quote":
        if not isinstance(content_obj, dict) or "text" not in content_obj:
            return {"error": "quote card requires content like {\"text\":\"...\",\"author\":\"...\"}"}

    if type_clean == "list":
        if not isinstance(content_obj, dict) or "items" not in content_obj or not isinstance(content_obj["items"], list):
            return {"error": "list card requires content like {\"items\":[\"a\",\"b\"]}"}

    if type_clean == "anime_grid":
        if not isinstance(content_obj, dict) or "items" not in content_obj or not isinstance(content_obj["items"], list):
            return {"error": "anime_grid requires content like {\"items\":[{\"name\":\"JJK\"}]}"}

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO profile_cards (user_id, type, title, content_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.user_id, type_clean, payload.title.strip(), json.dumps(content_obj), now_iso())
        )
        conn.commit()

    return {"message": "Card created"}


@app.get("/cards")
def list_cards(username: str):
    """
    Public endpoint: list profile cards by username.
    Used by profile.html.
    """
    user = get_user_by_username(username)
    if not user:
        return {"error": "User not found"}

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, type, title, content_json, created_at
            FROM profile_cards
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user["id"],)
        ).fetchall()

        cards = []
        for r in rows:
            d = dict(r)
            d["content"] = json.loads(d["content_json"])
            del d["content_json"]
            cards.append(d)

        return cards


@app.delete("/cards")
def delete_card(id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM profile_cards WHERE id = ?", (id,))
        conn.commit()
    return {"message": "Card deleted"}
