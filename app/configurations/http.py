import httpx # you use it to send HTTP requests to other services (like the GitHub API). API-to-API communication
from fastapi import Request

# This file is a dependency access layer for a shared HTTP client.
# - Provide a controlled way for routes/services to access the httpx.AsyncClient stored in app.state.
# - exposes it via dependency injection (get_http_client())

# You need http.py because it acts as a centralized access point for the HTTP client created in your FastAPI lifespan.
# The lifecycle in main.py creates and destroys the client, while http.py provides a clean way for other parts of the system to access it without tight coupling.
# lifespan = owns the resource
# app.state = storage layer(storing the shared http client)
# http.py = exposes the resource(shared HTTP client) to services.
# services = consume the resource via dependency injection

def get_http_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "http_client", None) # When a request comes in, 'request.app' → reference to the FastAPI app instance
    # 'getattr' = retrieves an attribute by name at runtime (dynamic access).
    # getattr(object, "attribute_name", default)
    # attribute exists = returns value
    # attribute missing	= returns default (if provided)
    # missing + no default = raises AttributeError
    if client is None:
        raise RuntimeError("http_client not initialized")

    if not isinstance(client, httpx.AsyncClient): # If client is not an HTTPX async client, stop execution and crash early with a clear error
        raise TypeError("Invalid http_client type")

    return client

# Work flow
# main.py (lifespan)
#     ↓ creates client
# app.state.http_client
#
# request arrives
#     ↓
# FastAPI builds Request
#     ↓
# endpoint calls dependency
#     ↓
# http.py runs get_http_client()
#     ↓
# returns app.state.http_client
#     ↓
# service uses client