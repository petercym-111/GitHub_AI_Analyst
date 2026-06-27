from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db_session import AsyncSessionLocal

async def get_db():
    db = AsyncSessionLocal()

    try:
        yield db

    finally:
        await db.close()