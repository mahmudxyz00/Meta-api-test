"""
FastAPI server that exposes the vibes_api client as a REST API.

Deploy this anywhere (Render, Railway, Fly.io, Docker, etc.) and you get
a full HTTP API for generating videos, images, TTS, and more.

Quick start
-----------
    pip install -e .[server]
    export VIBES_META_SESSION="your-cookie"
    export VIBES_API_KEY="your-secret-api-key"  # optional auth
    python -m server

    # Then open http://localhost:8000/docs for Swagger UI
"""

from .app import app, get_client

__all__ = ["app", "get_client"]
