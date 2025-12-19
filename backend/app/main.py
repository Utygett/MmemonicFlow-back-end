from fastapi import FastAPI, APIRouter
from app.api.routes import cards
from app.api.routes import cards, groups
import app.models
from app.api.routes import auth
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import decks

from app.db.init_db import init_db

app = FastAPI(title="Flashcards API")

@app.on_event("startup")
def on_startup():
    init_db()

origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")

api.include_router(cards.router,  prefix="/cards",  tags=["cards"])
api.include_router(groups.router, prefix="/groups", tags=["groups"])
api.include_router(auth.router,   prefix="/auth",   tags=["auth"])
api.include_router(decks.router,  prefix="/decks",  tags=["decks"])

app.include_router(api)

@app.get("/health")
def health_check():
    return {"status": "ok"}
