"""
FastAPI app exposing the VibesClient as a REST API.

The client is created once at startup with background cookie refresh
enabled, so the session stays alive indefinitely.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure the vibes_api package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vibes_api import VibesClient, VibesAPIError

# --------------------------------------------------------------------------- #
#  Global client (singleton, with background cookie refresh)
# --------------------------------------------------------------------------- #
_client: Optional[VibesClient] = None
_client_lock = threading.Lock()


def get_client() -> VibesClient:
    """Get the global VibesClient instance (created on first use)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                meta_session = os.environ.get("VIBES_META_SESSION")
                if not meta_session:
                    raise HTTPException(
                        status_code=500,
                        detail="VIBES_META_SESSION environment variable not set.",
                    )
                # Optional: load persisted cookie from file
                cookie_file = os.environ.get("VIBES_COOKIE_FILE")
                if cookie_file and os.path.exists(cookie_file):
                    try:
                        with open(cookie_file) as f:
                            meta_session = f.read().strip()
                    except IOError:
                        pass

                def _save_cookie(new_cookie: str):
                    if cookie_file:
                        try:
                            with open(cookie_file, "w") as f:
                                f.write(new_cookie)
                        except IOError:
                            pass

                _client = VibesClient(
                    meta_session=meta_session,
                    auto_refresh=True,
                    background_refresh=True,
                    refresh_interval=float(os.environ.get("VIBES_REFRESH_INTERVAL", "1500")),
                    on_cookie_refresh=_save_cookie,
                )
    return _client


# --------------------------------------------------------------------------- #
#  API key authentication
# --------------------------------------------------------------------------- #
def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
                   authorization: Optional[str] = Header(None)):
    """Verify the API key if VIBES_API_KEY is set."""
    expected = os.environ.get("VIBES_API_KEY")
    if not expected:
        return  # No auth required
    provided = None
    if x_api_key:
        provided = x_api_key
    elif authorization and authorization.startswith("Bearer "):
        provided = authorization[7:]
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# --------------------------------------------------------------------------- #
#  Pydantic models
# --------------------------------------------------------------------------- #
class ProjectCreate(BaseModel):
    name: str = "Untitled"
    composition: Optional[dict] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    composition: Optional[dict] = None

class VideoGenerate(BaseModel):
    project_id: str
    prompt: str
    aspect_ratio: str = "9:16"
    resolution: str = "480p"
    variations: int = 4
    video_model: str = "midjen-short"
    image_model: str = "midjen-base"
    prompt_model: str = "gemini-2.5-flash"
    ingredients: Optional[List[dict]] = None
    create_ingredients: Optional[List[dict]] = None
    start_frame: Optional[dict] = None
    end_frame: Optional[dict] = None
    moodboard: Optional[dict] = None
    poll: bool = True
    poll_timeout: float = 300.0

class ImageGenerate(BaseModel):
    project_id: str
    prompt: str
    aspect_ratio: str = "1:1"
    resolution: str = "480p"
    variations: int = 1
    image_model: str = "midjen-base"
    prompt_model: str = "gemini-2.5-flash"
    ingredients: Optional[List[dict]] = None
    create_ingredients: Optional[List[dict]] = None
    moodboard: Optional[dict] = None

class ImageEdit(BaseModel):
    source_image_ent_id: str
    edit_prompt: str
    project_id: Optional[str] = None

class PromptEnhance(BaseModel):
    prompt: str
    project_id: Optional[str] = None
    batch_type: str = "videos"

class TTSRequest(BaseModel):
    text: str
    voice: str
    output_format: str = "mp3"
    language: Optional[str] = None

class LipsyncRequest(BaseModel):
    project_id: str
    image_prompt: str
    script: str
    audio_url: str
    audio_duration_ms: int
    engine: str = "midjen"
    ingredients: Optional[List[dict]] = None
    aspect_ratio: Optional[str] = None
    music_track: Optional[dict] = None
    custom_motion_prompt: Optional[str] = None

class ExtendVideo(BaseModel):
    project_id: str
    batch_id: str
    content_id: Optional[str] = None
    prompt: Optional[str] = None
    poll: bool = True
    poll_timeout: float = 300.0

class EditVideo(BaseModel):
    project_id: str
    batch_id: str
    content_id: Optional[str] = None
    prompt: str
    poll: bool = True
    poll_timeout: float = 300.0

class ShareLinkCreate(BaseModel):
    entity_type: str
    entity_id: str
    expires_at: Optional[str] = None
    max_uses: Optional[int] = None

class IngredientCreate(BaseModel):
    name: str
    ingredient_type: str
    source_image_ent_id: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None

class TimelineChat(BaseModel):
    input: str
    instructions: Optional[str] = None
    tools: Optional[List[dict]] = None
    composition: Optional[dict] = None

class TimelineExport(BaseModel):
    composition: dict

class PublishRequest(BaseModel):
    content_item_id: str
    batch_id: Optional[str] = None
    caption: Optional[str] = None
    audio_types: Optional[List[str]] = None
    prompt: Optional[str] = None
    image_prompt: Optional[str] = None
    video_prompt: Optional[str] = None

class ParseMidjourney(BaseModel):
    prompt: str

class UploadImage(BaseModel):
    image_base64: str


def _handle_error(e: Exception):
    if isinstance(e, VibesAPIError):
        raise HTTPException(
            status_code=e.status or 500,
            detail={
                "error": str(e),
                "code": e.code,
                "response": e.response,
            },
        )
    raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------- #
#  FastAPI app
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="VibesAI API",
    description=(
        "Unofficial REST API wrapper for vibes.ai. Generate videos, images, "
        "TTS, lip-sync, manage timelines, publish content, and more."
    ),
    version="1.2.1",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH = [Depends(verify_api_key)]

# --------------------------------------------------------------------------- #
#  Health & root
# --------------------------------------------------------------------------- #
@app.get("/", tags=["Health"])
async def root():
    return {"name": "VibesAI API", "version": "1.2.1", "docs": "/docs"}

@app.get("/health", tags=["Health"])
async def health():
    try:
        user = get_client().get_me()
        return {"status": "healthy", "user": user.get("username")}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# --------------------------------------------------------------------------- #
#  Auth
# --------------------------------------------------------------------------- #
@app.get("/api/v1/me", tags=["Auth"], dependencies=AUTH)
async def get_me():
    try: return get_client().get_me()
    except Exception as e: _handle_error(e)

@app.get("/api/v1/check-token", tags=["Auth"], dependencies=AUTH)
async def check_token():
    try: return {"valid": get_client().check_token()}
    except Exception as e: _handle_error(e)

@app.get("/api/v1/current-cookie", tags=["Auth"], dependencies=AUTH)
async def get_current_cookie():
    return {"meta_session": get_client().get_current_cookie()}

@app.post("/api/v1/logout", tags=["Auth"], dependencies=AUTH)
async def logout():
    try:
        get_client().logout()
        return {"success": True}
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Projects
# --------------------------------------------------------------------------- #
@app.get("/api/v1/projects", tags=["Projects"], dependencies=AUTH)
async def list_projects(limit: int = 25, offset: int = 0, sort: str = "newest", search: Optional[str] = None):
    try: return get_client().list_projects(limit=limit, offset=offset, sort=sort, search=search)
    except Exception as e: _handle_error(e)

@app.post("/api/v1/projects", tags=["Projects"], dependencies=AUTH)
async def create_project(body: ProjectCreate):
    try: return get_client().create_project(name=body.name, composition=body.composition)
    except Exception as e: _handle_error(e)

@app.get("/api/v1/projects/{project_id}", tags=["Projects"], dependencies=AUTH)
async def get_project(project_id: str):
    try: return get_client().get_project(project_id)
    except Exception as e: _handle_error(e)

@app.put("/api/v1/projects/{project_id}", tags=["Projects"], dependencies=AUTH)
async def update_project(project_id: str, body: ProjectUpdate):
    try: return get_client().update_project(project_id, name=body.name, composition=body.composition)
    except Exception as e: _handle_error(e)

@app.delete("/api/v1/projects/{project_id}", tags=["Projects"], dependencies=AUTH)
async def delete_project(project_id: str, delete_assets: bool = False):
    try:
        get_client().delete_project(project_id, delete_assets=delete_assets)
        return {"success": True}
    except Exception as e: _handle_error(e)

@app.post("/api/v1/projects/{project_id}/duplicate", tags=["Projects"], dependencies=AUTH)
async def duplicate_project(project_id: str):
    try: return get_client().duplicate_project(project_id)
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Videos
# --------------------------------------------------------------------------- #
@app.post("/api/v1/videos/generate", tags=["Videos"], dependencies=AUTH)
async def generate_video(body: VideoGenerate):
    try:
        return get_client().generate_video(
            project_id=body.project_id, prompt=body.prompt,
            aspect_ratio=body.aspect_ratio, resolution=body.resolution,
            variations=body.variations, video_model=body.video_model,
            image_model=body.image_model, prompt_model=body.prompt_model,
            ingredients=body.ingredients, create_ingredients=body.create_ingredients,
            start_frame=body.start_frame, end_frame=body.end_frame,
            moodboard=body.moodboard, poll=body.poll, poll_timeout=body.poll_timeout,
        )
    except Exception as e: _handle_error(e)

@app.post("/api/v1/videos/extend", tags=["Videos"], dependencies=AUTH)
async def extend_video(body: ExtendVideo):
    try:
        client = get_client()
        batch = client.get_batch(body.batch_id)
        source = next((c for c in batch.get("content", []) if c["id"] == body.content_id), None)
        if not source:
            source = batch["content"][0] if batch.get("content") else None
        if not source:
            raise HTTPException(404, "No content item found in batch")
        return client.extend_video(
            project_id=body.project_id, source_video=source,
            prompt=body.prompt, poll=body.poll, poll_timeout=body.poll_timeout,
        )
    except HTTPException: raise
    except Exception as e: _handle_error(e)

@app.post("/api/v1/videos/edit", tags=["Videos"], dependencies=AUTH)
async def edit_video(body: EditVideo):
    try:
        client = get_client()
        batch = client.get_batch(body.batch_id)
        source = next((c for c in batch.get("content", []) if c["id"] == body.content_id), None)
        if not source:
            source = batch["content"][0] if batch.get("content") else None
        if not source:
            raise HTTPException(404, "No content item found in batch")
        return client.edit_video(
            project_id=body.project_id, source_video=source,
            prompt=body.prompt, poll=body.poll, poll_timeout=body.poll_timeout,
        )
    except HTTPException: raise
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Images
# --------------------------------------------------------------------------- #
@app.post("/api/v1/images/generate", tags=["Images"], dependencies=AUTH)
async def generate_image(body: ImageGenerate):
    try:
        return get_client().generate_image(
            project_id=body.project_id, prompt=body.prompt,
            aspect_ratio=body.aspect_ratio, resolution=body.resolution,
            variations=body.variations, image_model=body.image_model,
            prompt_model=body.prompt_model, ingredients=body.ingredients,
            create_ingredients=body.create_ingredients, moodboard=body.moodboard,
        )
    except Exception as e: _handle_error(e)

@app.post("/api/v1/images/edit", tags=["Images"], dependencies=AUTH)
async def edit_image(body: ImageEdit):
    try:
        return get_client().edit_image(
            source_image_ent_id=body.source_image_ent_id,
            edit_prompt=body.edit_prompt, project_id=body.project_id,
        )
    except Exception as e: _handle_error(e)

@app.post("/api/v1/upload/image", tags=["Uploads"], dependencies=AUTH)
async def upload_image(body: UploadImage):
    try: return get_client().upload_image(body.image_base64)
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Prompts
# --------------------------------------------------------------------------- #
@app.post("/api/v1/prompts/enhance", tags=["Prompts"], dependencies=AUTH)
async def enhance_prompt(body: PromptEnhance):
    try:
        return {"variations": get_client().enhance_prompt(
            prompt=body.prompt, project_id=body.project_id, batch_type=body.batch_type
        )}
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  TTS
# --------------------------------------------------------------------------- #
@app.get("/api/v1/voices", tags=["TTS"], dependencies=AUTH)
async def list_voices():
    try: return {"voices": get_client().list_voices()}
    except Exception as e: _handle_error(e)

@app.post("/api/v1/tts", tags=["TTS"], dependencies=AUTH)
async def tts(body: TTSRequest):
    try:
        return get_client().tts(
            text=body.text, voice=body.voice,
            output_format=body.output_format, language=body.language,
        )
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Media
# --------------------------------------------------------------------------- #
@app.get("/api/v1/media", tags=["Media"], dependencies=AUTH)
async def list_media(limit: int = 50, offset: int = 0, type: Optional[str] = None, search: Optional[str] = None):
    try: return get_client().list_media(limit=limit, offset=offset, type=type, search=search)
    except Exception as e: _handle_error(e)

@app.get("/api/v1/media/{item_id}/download", tags=["Media"], dependencies=AUTH)
async def download_media(item_id: str, type: str = "video"):
    from fastapi import Response
    import tempfile
    try:
        client = get_client()
        suffix = ".mp4" if type == "video" else ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            path = f.name
        if type == "video":
            client.download_video(item_id, path)
        else:
            client.download_image(item_id, path)
        with open(path, "rb") as f:
            content = f.read()
        os.unlink(path)
        media_type = "video/mp4" if type == "video" else "image/png"
        return Response(content=content, media_type=media_type)
    except Exception as e: _handle_error(e)

@app.delete("/api/v1/media/{item_id}", tags=["Media"], dependencies=AUTH)
async def delete_media_item(item_id: str):
    try:
        get_client().delete_content_item(item_id)
        return {"success": True}
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Batches
# --------------------------------------------------------------------------- #
@app.get("/api/v1/batches", tags=["Batches"], dependencies=AUTH)
async def list_batches(limit: int = 12, offset: int = 0, project_id: Optional[str] = None):
    try: return get_client().list_batches(limit=limit, offset=offset, project_id=project_id)
    except Exception as e: _handle_error(e)

@app.get("/api/v1/batches/{batch_id}", tags=["Batches"], dependencies=AUTH)
async def get_batch(batch_id: str):
    try: return get_client().get_batch(batch_id)
    except Exception as e: _handle_error(e)

@app.post("/api/v1/batches/{batch_id}/poll", tags=["Batches"], dependencies=AUTH)
async def poll_batch(batch_id: str, timeout: float = 180.0):
    try: return get_client().poll_batch(batch_id, timeout=timeout)
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Ingredients
# --------------------------------------------------------------------------- #
@app.get("/api/v1/ingredients", tags=["Ingredients"], dependencies=AUTH)
async def list_ingredients(owner_filter: str = "LIBRARY", ingredient_type: Optional[str] = None):
    try: return {"ingredients": get_client().list_ingredients(owner_filter=owner_filter, ingredient_type=ingredient_type)}
    except Exception as e: _handle_error(e)

@app.post("/api/v1/ingredients", tags=["Ingredients"], dependencies=AUTH)
async def create_ingredient(body: IngredientCreate):
    try: return get_client().create_ingredient(
        name=body.name, ingredient_type=body.ingredient_type,
        source_image_ent_id=body.source_image_ent_id, image_url=body.image_url,
        description=body.description,
    )
    except Exception as e: _handle_error(e)

@app.delete("/api/v1/ingredients/{ingredient_id}", tags=["Ingredients"], dependencies=AUTH)
async def delete_ingredient(ingredient_id: str):
    try:
        get_client().delete_ingredient(ingredient_id)
        return {"success": True}
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Share links
# --------------------------------------------------------------------------- #
@app.post("/api/v1/share-links", tags=["Share"], dependencies=AUTH)
async def create_share_link(body: ShareLinkCreate):
    try: return get_client().create_share_link(
        body.entity_type, body.entity_id, expires_at=body.expires_at, max_uses=body.max_uses
    )
    except Exception as e: _handle_error(e)

@app.get("/api/v1/share-links", tags=["Share"], dependencies=AUTH)
async def list_share_links(entity_type: str, entity_id: str):
    try: return {"shareLinks": get_client().list_share_links(entity_type, entity_id)}
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Timeline
# --------------------------------------------------------------------------- #
@app.post("/api/v1/timeline/chat", tags=["Timeline"], dependencies=AUTH)
async def timeline_chat(body: TimelineChat):
    try:
        events = []
        for event in get_client().timeline_chat(
            body.input, instructions=body.instructions,
            tools=body.tools, composition=body.composition,
        ):
            events.append(event)
            if event.get("type") in ("completed", "error"):
                break
        return {"events": events}
    except Exception as e: _handle_error(e)

@app.post("/api/v1/timeline/export", tags=["Timeline"], dependencies=AUTH)
async def export_timeline(project_id: str, body: TimelineExport):
    from fastapi import Response
    try:
        mp4_bytes = get_client().export_timeline(project_id, body.composition)
        return Response(content=mp4_bytes, media_type="video/mp4")
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Publishing
# --------------------------------------------------------------------------- #
@app.post("/api/v1/publish", tags=["Publishing"], dependencies=AUTH)
async def publish_to_vibes(body: PublishRequest):
    try: return get_client().publish_to_vibes(
        content_item_id=body.content_item_id, batch_id=body.batch_id,
        caption=body.caption, audio_types=body.audio_types,
        prompt=body.prompt, image_prompt=body.image_prompt, video_prompt=body.video_prompt,
    )
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Lip sync
# --------------------------------------------------------------------------- #
@app.post("/api/v1/lipsync", tags=["LipSync"], dependencies=AUTH)
async def generate_lipsync(body: LipsyncRequest):
    try: return get_client().generate_lipsync(
        project_id=body.project_id, image_prompt=body.image_prompt,
        script=body.script, audio_url=body.audio_url,
        audio_duration_ms=body.audio_duration_ms, engine=body.engine,
        ingredients=body.ingredients, aspect_ratio=body.aspect_ratio,
        music_track=body.music_track, custom_motion_prompt=body.custom_motion_prompt,
    )
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Music
# --------------------------------------------------------------------------- #
@app.get("/api/v1/music/search", tags=["Music"], dependencies=AUTH)
async def search_music(q: str = "", limit: int = 30, cursor: Optional[str] = None):
    try: return get_client().search_music_filtered(query=q, limit=limit, cursor=cursor)
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Moodboards
# --------------------------------------------------------------------------- #
@app.get("/api/v1/moodboards", tags=["Moodboards"], dependencies=AUTH)
async def list_moodboards():
    try: return {"moodboards": get_client().list_moodboards()}
    except Exception as e: _handle_error(e)

# --------------------------------------------------------------------------- #
#  Utilities (no auth)
# --------------------------------------------------------------------------- #
@app.post("/api/v1/utils/parse-midjourney", tags=["Utils"])
async def parse_midjourney(body: ParseMidjourney):
    return VibesClient.parse_midjourney_params(body.prompt)

@app.post("/api/v1/utils/validate-prompt", tags=["Utils"])
async def validate_prompt(body: ParseMidjourney):
    return VibesClient.validate_prompt_length(body.prompt)

# --------------------------------------------------------------------------- #
#  Main entry
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
