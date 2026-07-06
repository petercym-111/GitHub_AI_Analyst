from app.database.db_session import SessionLocal

async def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()