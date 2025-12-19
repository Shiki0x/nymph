# NYMPH 🌱
**NYMPH** is a personal growth profile platform that combines habit tracking, identity building, and shareable profile pages into one system.

Unlike traditional habit trackers that focus only on task completion, NYMPH emphasizes **who a person is becoming** — blending habits, interests, and self-expression into a single customizable profile.

---

## ✨ Core Vision
NYMPH is designed to be:
- A **habit tracker**
- A **profile hub**
- A **shareable growth page**

Users can track habits, display interests, and curate profile “cards” that represent their identity, progress, and personality — all in one place.

---

## 🧩 Current Features (Phase 2)
- ⚙️ **FastAPI backend**
- 🗄️ **SQLite persistence**
- 📈 **Habit logging** (completed / not completed)
- 🔗 **Shareable public profiles** (`/profile.html?username=...`)
- 🧠 **Profile cards system**
  - Quotes
  - Lists (hobbies, anime, interests)
  - Custom text cards
- 🌐 **Public links section**
- 🎨 Clean, dark-themed UI

---

## 🏗️ Architecture
- **Backend:** FastAPI (Python)
- **Database:** SQLite
- **Frontend:** HTML + CSS + Vanilla JavaScript
- **API Style:** REST
- **Local Dev Server:** Uvicorn + Python HTTP server

---

## 🚀 Running Locally

### Backend
```bash
python -m uvicorn main:app --reload
