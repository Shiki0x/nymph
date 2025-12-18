from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HABIT_LOGS = []

@app.post("/log-habit")
def log_habit(habit: str, completed: bool):
    entry = {"habit": habit, "completed": completed}
    HABIT_LOGS.append(entry)
    return {"message": "Saved!", "entry": entry}

@app.get("/habits")
def get_habits():
    return HABIT_LOGS
