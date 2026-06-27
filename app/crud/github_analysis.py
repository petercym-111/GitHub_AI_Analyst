from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GitHubAnalysis


class GitHubAnalysisCRUD:

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        github_username: str,
        repo_snapshot: list[dict],
        analysis: str,
        model_name: str,
    ) -> GitHubAnalysis:

        obj = GitHubAnalysis(
            github_username=github_username,
            repo_snapshot=repo_snapshot,
            analysis=analysis,
            model_name=model_name,
        )

        db.add(obj)
        await db.commit()
        await db.refresh(obj)

        return obj

    @staticmethod
    async def get_by_username(
        db: AsyncSession,
        username: str,
    ) -> GitHubAnalysis | None:

        stmt = (
            select(GitHubAnalysis)
            .where(
                GitHubAnalysis.github_username == username
            )
            .order_by(
                GitHubAnalysis.created_at.desc()
            )
            .limit(1)
        )

        result = await db.execute(stmt)

        return result.scalar_one_or_none()

    @staticmethod
    async def delete(
        db: AsyncSession,
        analysis: GitHubAnalysis,
    ) -> None:

        await db.delete(analysis)
        await db.commit()