from fastapi import FastAPI
from app.api.routes import cards
from app.api.routes import cards, groups
import app.models
from app.api.routes import auth
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import decks

app = FastAPI(title="Flashcards API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 👈 фронт
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router, prefix="/cards", tags=["cards"])
app.include_router(groups.router, prefix="/groups", tags=["groups"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(decks.router, prefix="/decks", tags=["decks"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
