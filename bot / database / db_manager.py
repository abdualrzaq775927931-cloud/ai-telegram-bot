from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import Base
import os

# Get DB URL from env or use SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///poll_bot.db")

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

def init_db():
    """Initialize the database and create all tables."""
    Base.metadata.create_all(engine)

def get_session():
    """Return a new database session."""
    return Session()
