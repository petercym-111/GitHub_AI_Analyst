from fastapi import FastAPI
import httpx
from contextlib import asynccontextmanager
from groq import AsyncGroq

from app.configurations.config import settings
from app.routes import endpoints as github
from app.routes import github_analysis_endpoint as analysis

# In production standard, always keep main.py as minimal code as possible
# If it grows beyond wiring/config → move code out

# Full execution flow for this file:
# 1. App starts
#    ↓
# 2. lifespan() runs
#    ↓
# 3. startup code executes (create http client)
#    ↓
# 4. yield → app is now serving requests
#    ↓
# 5. app stops
#    ↓
# 6. shutdown code runs (close http client)

# Lifecycle = system design theory
# Lifespan = code that executes that theory

# What is lifecycle concept:
# lifecycle starts when Uvicorn(server) starts the app and ends when Uvicorn(server) shuts it down.
# Lifecycle is used to initialize shared resources at startup, allow them to be reused during runtime, and properly clean them up at shutdown.
# **lifespan is a centralized lifecycle manager for application-scoped resources.
# **Lifespan is a mechanism to initialize and manage the lifecycle of shared resources in your application, but it only manages the resources you explicitly define within it. It does not automatically handle all shared resources.
# startup  → create shared resources/ initialize resources
# runtime  → your routes/services use the resources
# shutdown → clean the resources up

# Server starts (uvicorn)
#     ↓
# App startup (lifespan before yield)
#     ↓
# App runs (handles many requests)
#     ↓
# Server stops
#     ↓
# App shutdown (lifespan after yield)
# This defines a controlled application lifecycle manager for FastAPI.

# Why we need lifecycle/lifespan?

# - Single initialization

    # - DB connection pool = DB session created per request but shared engine can be reused (reuse existing idle connections when possible, avoid reconnecting on every request)
        # First request
            # - create connection → DB
        # Next request
            # - reuse pooled connection → no new handshake
        # If pool is full
            # - create new connection → DB

    # - HTTP client
    # - cache (Redis)
    # - ML models

# created once, not per request.

# - Proper cleanup
# Without cleanup:  memory leaks, hanging connections

# - Performance
# Reusing resources:
# connection reuse → faster requests (lower latency)
# less overhead（开销） → better throughput（吞吐量）

# - Consistency
    # All requests share:
        # - same config
        # - same connections
        # - same environment

# Lifecycle ensures resources are initialized once and cleaned up correctly.
# gives you a single structured place to manage shared resources like:
# - HTTP clients (httpx.AsyncClient)
# - database engines / connection pools
# - Redis clients
# - message queue connections
# - model/LLM clients
# - cached config/state
# - background services

@asynccontextmanager # This turns a normal async function into a context manager
                     # Meaning it can define:
                        # - setup (before yield)
                        # - teardown (after yield)
                     # enter → do startup → yield → do shut down → exit

async def lifespan(app: FastAPI): # Defines a function that FastAPI will call to manage app lifecycle
                                  # app: FastAPI is passed by FastAPI internally
                                  # This parameter(app: FastAPI) represents the running application instance
    # Startup Section
    app.state.http_client = httpx.AsyncClient( # This stores an HTTP client instance inside the FastAPI application state.
                                     # httpx.AsyncClient（）单单是这个语法本身就已经是昂贵资源，并包含了（connection pool，tcp connection之类）。Bracket里的不一定需要是昂贵资源，这个语法也可以单独写
                                     # 'app.state' = 'engine + pool' stored here. A shared storage container attached to the FastAPI app instance. "global memory for this app instance for runtime use"
                                     # 'app.state.http_client' = "Attach this HTTP client to the application so all routes can reuse it"
                                     # 'httpx.AsyncClient' is an asynchronous HTTP client used to send outbound（出站) HTTP requests from your backend to external services (e.g., the GitHub API).
                                     # 'httpx' is the bridge from your backend to external systems
                                     # Used for:
                                        # - Calling external APIs (GitHub API)
                                        # - connection reuse (important for performance)
                                     # Why use it here:
                                        # - runs once when app starts
                                        # - avoids creating a new client per request
                                        # - you need it because your application depends on external data (like GitHub)
                                        # - send asynchronous HTTP requests from your backend to external APIs

        base_url="https://api.github.com", # This sets a default root URL.
                                           # 所有request默认都是发送到：https://api.github.com
                                           # instead of: await client.get("https://api.github.com/user")
                                           # you can do: await client.get("/user")

        timeout=10.0, # if GitHub API does not respond within 10 seconds → abort request
    )

    yield  # yield separates startup and shutdown phases. It pauses execution after initialization, lets FastAPI run the application normally,
           # and only resumes when the server is shutting down — not after individual requests finish.
           # app runs here = This is the boundary between startup and shutdown, without yield the app will not properly start serving requests.
           # Everything before = startup
           # Everything after = shutdown
           # During yield:
                # FastAPI is running normally (handling requests)

    # Shutdown Section
    await app.state.http_client.aclose()
    # Properly closes the HTTP client
    # Releases:
         # - open TCP connections
         # - sockets
         # - connection pool
    # Prevents resource leaks

app = FastAPI(lifespan=lifespan)
# - Creates the FastAPI application
# - Registers your lifespan handler
# Now FastAPI knows:
# startup → run code before yield
# shutdown → run code after yield

app.include_router(analysis.router, prefix="/github", tags=["GitHub"])
app.include_router(github.router, prefix="/github", tags=["GitHub"])
# Registers the router from endpoints.py into the main app. Takes all routes inside github.router
# 'github.router' is an APIRouter instance defined in your route file (endpoints.py).
# 'prefix="/github"' = Adds a URL prefix to all routes inside that router. Every endpoint path will have the word 'github' prepended. *Users still need to enter the "/github" parameter themselves
# @router.get("/me") becomes '/github/me'
# It allows you to:
# - group endpoints logically (/github, /users, /ai)
# - avoid collisions (/me could exist in multiple modules)
# - version APIs later (/v1/github/me)

# include_router is a method defined inside the FastAPI class. *Can't change its name*
# include_router is the mechanism that makes your route modules “live” inside your FastAPI app. It registers a group of routes
# Routes(Endpoints) defined in other files are not automatically part of your FastAPI app, so you must register them with the app instance (where app = FastAPI() lives).
# because routes(@router.get("/me")) are defined on an APIRouter, they must be registered to the FastAPI app instance using include_router
# Without it:
# - routes are defined
# - but not usable (404)

# tags=["GitHub"]
# Is metadata for API documentation, not routing logic.
# FastAPI uses this to group endpoints in the Swagger UI (/docs).
# tags=["GitHub"] is used to group your endpoints under “GitHub” in the API docs (/docs). Like a label for the endpoints, the endpoints are under that specific label
# It has no effect on how your API works.

# In the auto-generated Swagger UI docs
# All routes under that router appear under a "GitHub" section:
# GitHub
#   ├── GET /github/me
#   ├── GET /github/users/{username}/repos
