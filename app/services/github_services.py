import httpx

class GitHubService:
    # Responsibilities:
    # - communicate with GitHub API
    # - hide HTTP details from endpoints
    # - provide reusable business operations
    def __init__(self, github_token: str, client: httpx.AsyncClient):
        self.client = client # Stores the injected client inside the service.
                             # After this: "self.client.get(...)"
                             # can be used anywhere in the class.
        self.headers = { # Creates default headers. (metadata/information about the request. The context of the data)
                         # Example: {
                         #            "name": "John"
                         #          }
                         # Questions:
                                # Who sent this?
                                # What format is it?
                                # What response format is expected?
                         # Headers answer those questions.

            "Authorization": f"Bearer {github_token}", # GitHub uses this to identify you.
            "Accept": "application/vnd.github+json", # Tells GitHub to return JSON using GitHub's API format
        }

    # Private helper method (This is an internal reusable GET method. Without it that you need to write repeated code for both the public method)
    async def _get(self, url: str, **kwargs): # **kwargs = accept any extra keyword arguments if any
        res = await self.client.get( # Send HTTP request by using the shared AsyncClient.
            url, # Example: "/user" . Because base_url was configured earlier: "https://api.github.com" . Final URL becomes: "https://api.github.com/user"
            headers=self.headers, # Adds authentication.
            **kwargs
        )
        res.raise_for_status() # Error handling for the http error like 200, 404
        return res.json() # return JSON and convert JSON into python object

    # Public method (retrieve current authenticated GitHub user)
    async def get_user(self):
        return await self._get("/user") # call the helper method, equivalent to "GET https://api.github.com/user"

# The working flow until here "get_user" -------------------
    # get_user()
    #     ↓
    # _get("/user")
    #     ↓
    # client.get(...)
    #     ↓
    # GitHub API
#  --------------- --------------- ---------------

    # retrieve repositories for a GitHub user
    async def get_user_repos(
        self,
        username: str,
        page: int = 1,
        per_page: int = 30 # maximum 30 repositories
    ):
        return await self._get( # call helper (Delegates to the reusable GET function.)
            f"/users/{username}/repos", # build URL to tells GitHub which resource you want (Example:"/users/octocat/repos")
            params={ # using query parameters here Because httpx.AsyncClient.get() supports it. httpx automatically builds: (Example:"/users/octocat/repos?page=2&per_page=30")
                "page": page,
                "per_page": per_page
            }
        )

# - Full execution flow -
# Endpoint
#     ↓
# GitHubService.get_user_repos()
#     ↓
# GitHubService._get()
#     ↓
# httpx.AsyncClient.get()
#     ↓
# GitHub API
#     ↓
# Response
#     ↓
# JSON
#     ↓
# Endpoint