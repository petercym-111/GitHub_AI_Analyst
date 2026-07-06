from sqlalchemy import create_engine
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
)

from app.configurations.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


#from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker, declarative_base
#from app.configurations.config import settings

#db_url = settings.DATABASE_URL

#engine = create_engine(db_url, echo=True)

#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#Base = declarative_base()