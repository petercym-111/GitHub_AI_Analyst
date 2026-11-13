from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db_session import SessionLocal

# 用来注入session给endpoint，一个request/endpoint 一个 session
# session就是与database的一次crud交互，类似数据库工作上下文，这个上下文就是 AsyncSession

async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as db: # 离开 async with 时会自动关闭 session 并释放连接资源，因此不需要再写 db.close()
        yield db

# 用 async with SessionLocal() as db 创建 session，并把它通过 yield 提供给 endpoint。
# request 完成、依赖退出时，Python 会离开 async with，SQLAlchemy 随后关闭 session、释放它持有的连接资源。