from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import config

# SQLite requires check_same_thread=False for multi-threaded FastAPI apps
connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(config.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
