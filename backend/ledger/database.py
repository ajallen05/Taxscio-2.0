import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = None
SessionLocal = None
Base = declarative_base()

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)

def init_db():
    if engine:
        Base.metadata.create_all(bind=engine)
