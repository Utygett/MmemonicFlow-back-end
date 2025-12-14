from fastapi import FastAPI
from app.api.routes import cards
import app.models

app = FastAPI(title="Flashcards API")

app.include_router(cards.router, prefix="/cards", tags=["cards"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
