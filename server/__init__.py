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

Endpoints
---------
All 127+ VibesClient methods are exposed as REST endpoints:

    GET    /api/v1/me
    POST   /api/v1/projects
    GET    /api/v1/projects
    POST   /api/v1/videos/generate
    POST   /api/v1/images/generate
    POST   /api/v1/tts
    GET    /api/v1/voices
    GET    /api/v1/media
    POST   /api/v1/batches/{id}/poll
    POST   /api/v1/share-links
    POST   /api/v1/publish
    GET    /api/v1/ingredients
    POST   /api/v1/ingredients
    GET    /api/v1/moodboards
    POST   /api/v1/timeline/chat
    POST   /api/v1/timeline/export
    ...and 100+ more

See /docs (Swagger UI) for the full interactive API spec.
"""

from .app import app, get_client

__all__ = ["app", "get_client"]
