from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.github_analysis import GitHubAnalysis


class GitHubAnalysisCRUD:

    @staticmethod # 因为这些methods都不依赖任何 instance 的 object state，因此不需要 self，所以它们算是utility function
    async def create(
        db: Session,
        *,
        github_username: str,
        repo_snapshot: list[dict],
        analysis: dict,
        model_name: str,
    ) -> GitHubAnalysis:

        obj = GitHubAnalysis(
            github_username=github_username,
            repo_snapshot=repo_snapshot,
            analysis=analysis,
            model_name=model_name,
        )

        db.add(obj)
        db.commit()
        db.refresh(obj)

        return obj

    @staticmethod
    async def get_by_username( # 从数据库找出某个 GitHub 用户最新的一笔分析记录。
        db: Session,
        username: str,
    ) -> GitHubAnalysis | None: # 这个function只会return GitHubAnalysis or None

        stmt = (
            select(GitHubAnalysis) # 不是SQL，这里是在建立SQL 例如：SELECT * FROM github_analysis
            .where(
                GitHubAnalysis.github_username == username # SQL example： WHERE github_username = 'torvalds'
            )
            .order_by(
                GitHubAnalysis.created_at.desc() # SQL example： ORDER BY created_at DESC
            )
            .limit(1) # 只需要第一个最新用户名
        )

        result = db.execute(stmt) # 发送且execute以上的SQL给database，用来获取最新一个用户名

        return result.scalar_one_or_none() # 因为“select(GitHubAnalysis)”查询的是整个model，所以“scalar_one_or_none” 只会 return 一个 GitHubAnalysis object 例如：
                                            # GitHubAnalysis(
                                            #     github_username="torvalds",
                                            #     analysis="..."
                                            # ）
                                            # 如果没有才return None， 超过一个object就会raise exception (MultipleResultsFound)

    @staticmethod
    async def delete( # not used yet
        db: Session,
        analysis: GitHubAnalysis,
    ) -> None:

        db.delete(analysis)
        db.commit()