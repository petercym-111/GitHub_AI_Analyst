from datetime import datetime
from uuid import uuid4
from typing import Any, TYPE_CHECKING

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db_session import Base

if TYPE_CHECKING: # 因为IDE 有类型提示。所以Python 运行时不会真的 import。就不容易发生 circular import。
    from app.models.analysis_request_log import AnalysisRequestLog

# 以下是SQLAlchemy 2.0， 旧版的是“Column(...)”
class GitHubAnalysis(Base):
    __tablename__ = "github_analysis"

    id: Mapped[str] = mapped_column( # 'uuid' 会在数据库里会自动生成类似“085e9f89-e49e-498e-842a-fe9ee0c83ac5”的乱码id，而不是普通的integer1，2，3，4...
        UUID(as_uuid=True),          # 使用‘uuid’就不容易被hacker猜到，因为不可预测且全球唯一，但是缺点就是非常长，indexing比较差
        primary_key=True,            # 不过也有方法可以兼顾安全与性能，等项目大了后可以用以下这种方式：
        default=uuid4,               # Internal PK: BIGINT   例如： id = 12345   ，自己的database可以用这个
    )                                # Public ID  : UUID     例如： public_id = 085e9f89-e49e-498e-842a-fe9ee0c83ac5   ，API return可以用这个

    github_username: Mapped[str] = mapped_column(
        String(255), #database的VARCHAR(255)
        index=True,
    )

    repo_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB # 让database 知道，这是存的json而不是单纯的text
    )

    analysis: Mapped[dict] = mapped_column( # 代表 Python: analysis 是 str
        JSONB # 代表 Database: analysis 是 json。 分析结果要确保是json
    ) # JSONB 存的是：dict和list，不是str。 所以这里Mapped[dict]也必须要跟着

    model_name: Mapped[str] = mapped_column(
        String(100)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow, # 当前时间
    )

    requests: Mapped[list["AnalysisRequestLog"]] = relationship(
        back_populates="analysis"
    )