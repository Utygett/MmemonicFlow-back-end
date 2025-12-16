from fastapi import FastAPI
from app.api.routes import cards
from app.api.routes import cards, groups
import app.models
from app.api.routes import auth


app = FastAPI(title="Flashcards API")



app.include_router(cards.router, prefix="/cards", tags=["cards"])
app.include_router(groups.router, prefix="/groups", tags=["groups"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
