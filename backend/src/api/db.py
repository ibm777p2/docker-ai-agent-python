import os
import sqlmodel
from sqlmodel import Session, SQLModel
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL == "":
    raise NotImplementedError("No database implemented, `DATABASE_URL` needs to be set.")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

engine = sqlmodel.create_engine(DATABASE_URL)
#database models
# does not create db migration
def init_db():
    print("creating database tables...")
    SQLModel.metadata.create_all(engine)

#api routes
def get_session():
    with Session(engine) as session:
        yield session