from app.db.base import Base
from app.db.session import engine
import app.models  # чтобы все модели были зарегистрированы

def init_db():
    """Создаёт все таблицы в БД"""
    Base.metadata.create_all(bind=engine)
