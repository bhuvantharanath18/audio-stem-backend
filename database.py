# backend/database.py

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base # NEW LINE ✅
from sqlalchemy.orm import sessionmaker

# Define the database file
DATABASE_URL = "sqlite:///./library.db"

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our database models
Base = declarative_base()

# --- Define the Song Table ---
class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    stems_path = Column(String, unique=True) # The unique path where stems are stored

# --- Function to create the database and table ---
def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
    
