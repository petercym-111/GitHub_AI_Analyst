from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from app.configurations.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

Base = declarative_base()


#from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker, declarative_base
#from app.configurations.config import settings

#db_url = settings.DATABASE_URL

#engine = create_engine(db_url, echo=True)

#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#Base = declarative_base()