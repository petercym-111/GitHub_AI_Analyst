from datetime import datetime
from uuid import uuid4
from typing import Any

from sqlalchemy import Text, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db_session import Base


class GitHubAnalysis(Base):
    __tablename__ = "github_analysis"

    id: Mapped[str] = mapped_column( # 'uuid' 会在数据库里会自动生成类似“085e9f89-e49e-498e-842a-fe9ee0c83ac5”的乱码id，而不是普通的integer1，2，3，4...
        UUID(as_uuid=True),          # 使用‘uuid’就不容易被hacker猜到，因为不可预测且全球唯一，但是缺点就是非常长，indexing比较差
        primary_key=True,            # 不过也有方法可以兼顾安全与性能，等项目大了后可以用以下这种方式：
        default=uuid4,               # Internal PK: BIGINT   例如： id = 12345   ，自己的database可以用这个
    )                                # Public ID  : UUID     例如： public_id = 085e9f89-e49e-498e-842a-fe9ee0c83ac5   ，API return可以用这个

    github_username: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    repo_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB
    )

    analysis: Mapped[str] = mapped_column(
        Text
    )

    model_name: Mapped[str] = mapped_column(
        String(100)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    requests: Mapped[list["AnalysisRequestLog"]] = relationship(
        back_populates="analysis"
    )