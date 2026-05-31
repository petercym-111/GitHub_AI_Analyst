from fastapi import APIRouter, Depends, HTTPException, Query
# APIRouter → modular route grouping
# HTTPException → controlled API errors
# Query → query validation (pagination rules)
import httpx # In this file that used only for exception type handling

from app.services.github_services import GitHubService
from app.configurations.config import settings
from app.configurations.http import get_http_client

# This is a 3-layer dependency pipeline:
# HTTP Client → GitHubService → API Routes
# -----------------------------------------------
# app.state.http_client
#         ↓ (Depends)
# get_http_client
#         ↓
# GitHubService
#         ↓
# endpoint (/me, /repos)

router = APIRouter() # creates isolated route module, later attached in main.py

# Dependency factory (service layer construction)
# Request → client → service → endpoint

# lifespan → creates AsyncClient
# app.state → stores it
# get_http_client → retrieves it
# Depends → injects it
# type hint → describes it

def get_github_service(
    client: httpx.AsyncClient = Depends(get_http_client), # client: httpx.AsyncClient , Type hint for the injected object. **Type hint is not limited to int, str, bool. They can be custom classes(GitHubService) or third-party types(httpx.AsyncClient)
                                                          # Why httpx.AsyncClient is used as a type hint here. This does NOT create the client.
                                                          # It only declares: client must be an instance of AsyncClient. It still needed to describe what kind of object is being injected
                                                          # FastAPI first resolves get_http_client then inject the client
):
    return GitHubService(settings.github_token, client) # builds GitHubService and returns it to endpoint


@router.get("/me") # Attached later via include_router in main.py
async def get_me(
    service: GitHubService = Depends(get_github_service)
):
    try:
        return await service.get_user()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "message": "GitHub API error",
                "status": e.response.status_code
            }
        )


@router.get("/users/{username}/repos")
async def get_repos( # get the info of any public("private": false) repositories on the GitHub by searching username
    username: str,
    # --------------------------------------
    # Pagination is a technique to split a large dataset into smaller chunks (pages) and retrieve them incrementally.
    # Use it whenever a response can grow beyond a small, fixed size:
        # - database queries (users, orders, logs)
        # - external APIs (GitHub, Stripe, OpenAI, etc.)
        # - search results
        # - event streams / activity feeds
    # If a single request could return hundreds or thousands of items, you need pagination.
    # Full dataset → divided into pages → fetched piece by piece

        # Instead of:
        # GET /repos → returns 10,000 items

        # You do:
        # GET /repos?page=1&per_page=30
        # GET /repos?page=2&per_page=30

    # *pagination parameters controlling how data is sliced. The below is the offset-based
    # Example: '?page=1&per_page=30' , means return up to 30 repositories from the first page(the first slice of the dataset), depending on how many repositories exist.
    # It does not  guarantee 30 items(repositories), if

        # The data is enough:
        # total = 100 repos
        # page=1 → 30 items
        # page=2 → 30 items
        # page=3 → 30 items
        # page=4 → 10 items (remaining)

        # Small dataset:
        # total = 12 repos
        # page=1 → 12 items (not 30)

        # Out of range:
        # page=10
        # → empty list []

    page: int = Query(1, ge=1), # (which slice) query param = Default: 1 and Constraint must be: >= 1
    per_page: int = Query(30, ge=1, le=100), # (max items per slice) Default: 30, Constraints range: minimum is 1 and maximum is 100
    # Example:
        # page = 2
        # per_page = 1
        # total_items(repositories) = 2
        # get 1 item into page 2
    # --------------------------------------
    service: GitHubService = Depends(get_github_service)
):
    try:
        return await service.get_user_repos(username, page, per_page)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "message": "GitHub API error",
                "status": e.response.status_code
            }
        )

# Full execution flow:

# HTTP request
#   ↓
# FastAPI parses path + query
#   ↓
# resolve get_http_client
#   ↓
# resolve get_github_service
#   ↓
# inject GitHubService
#   ↓
# call endpoint function
#   ↓
# service calls GitHub API
#   ↓
# return response