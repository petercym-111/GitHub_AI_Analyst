from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GitHubAnalysis


class GitHubAnalysisCRUD:

    @staticmethod # 因为这些methods都不依赖任何 instance 的 object state，因此不需要 self，所以它们算是utility function
    async def create(
        db: AsyncSession,
        *,
        github_username: str,
        repo_snapshot: list[dict],
        analysis: dict,
        model_name: str,
        analysis_version: str,
    ) -> GitHubAnalysis:

        obj = GitHubAnalysis(
            github_username=github_username,
            repo_snapshot=repo_snapshot,
            analysis=analysis,
            model_name=model_name,
            analysis_version=analysis_version,
        )

        db.add(obj)
        await db.commit()
        await db.refresh(obj)

        return obj

    @staticmethod
    async def get_by_username( # 从数据库找出某个 GitHub 用户最新的一笔分析记录。
        db: AsyncSession,
        username: str,
        *,
        created_after: datetime,
        analysis_version: str,
    ) -> GitHubAnalysis | None: # 这个function只会return GitHubAnalysis or None

        stmt = (
            select(GitHubAnalysis) # 不是SQL，这里是在建立SQL 例如：SELECT * FROM github_analysis
            .where( # 数据库查询要求同一条记录同时满足以下三个条件才能复用缓存
                GitHubAnalysis.github_username == username,
                GitHubAnalysis.created_at >= created_after,
                GitHubAnalysis.analysis_version == analysis_version,
            )
            .order_by(
                GitHubAnalysis.created_at.desc() # SQL example： ORDER BY created_at DESC
            )
            .limit(1) # 只需要第一个最新用户名
        )

        result = await db.execute(stmt)

        return result.scalar_one_or_none() # 因为“select(GitHubAnalysis)”查询的是整个model，所以“scalar_one_or_none” 只会 return 一个 GitHubAnalysis object 例如：
                                            # GitHubAnalysis(
                                            #     github_username="torvalds",
                                            #     analysis="..."
                                            # ）
                                            # 如果没有才return None， 超过一个object就会raise exception (MultipleResultsFound)

    @staticmethod
    async def delete(db: AsyncSession, analysis: GitHubAnalysis) -> None:
        await db.delete(analysis)
        await db.commit()
