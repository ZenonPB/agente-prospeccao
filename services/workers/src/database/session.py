from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config.settings import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Função utilitária para obter uma sessão no banco de dados.
    Deve ser usada com 'with' para garantir que a sessão seja fechada corretamente.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()