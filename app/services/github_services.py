import httpx

class GitHubService:
    def __init__(self, github_token: str, client: httpx.AsyncClient):
        self.client = client
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
        }

    async def _get(self, url: str, **kwargs):
        res = await self.client.get(
            url,
            headers=self.headers,
            **kwargs
        )
        res.raise_for_status()
        return res.json()

    async def get_user(self):
        return await self._get("/user")

    async def get_user_repos(
        self,
        username: str,
        page: int = 1,
        per_page: int = 30
    ):
        return await self._get(
            f"/users/{username}/repos",
            params={
                "page": page,
                "per_page": per_page,
            }
        )