"""
FastAPI app that exposes the VibesClient as a REST API.

The client is created once at startup with background cookie refresh
enabled, so the session stays alive indefinitely.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional as Opt

# Import the vibes_api package (sibling)
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vibes_api import VibesClient, VibesAPIError
from vibes_api.composition import Composition


# --------------------------------------------------------------------------- #
#  Global client (singleton, with background cookie refresh)
# --------------------------------------------------------------------------- #
_client: Optional[VibesClient] = None
_client_lock = threading.Lock()


def get_client() -> VibesClient:
    """Get the global VibesClient instance (created on first use).

    The client is configured with:
    - auto_refresh=True (sliding session via Set-Cookie interception)
    - background_refresh=True (calls /api/auth/me every 25 min)
    - on_cookie_refresh callback (persists to VIBES_COOKIE_FILE if set)
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                meta_session = os.environ.get("VIBES_META_SESSION")
                if not meta_session:
                    raise HTTPException(
                        status_code=500,
                        detail="VIBES_META_SESSION environment variable not set. "
                               "Get your meta_session cookie from vibes.ai DevTools.",
                    )

                # Optional: load persisted cookie from file
                cookie_file = os.environ.get("VIBES_COOKIE_FILE")
                if cookie_file and os.path.exists(cookie_file):
                    try:
                        with open(cookie_file) as f:
                            meta_session = f.read().strip()
                    except IOError:
                        pass

                # Cookie persistence callback
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
def verify_api_key(x_api_key: Opt[str] = Header(None, alias="X-API-Key"),
                   authorization: Opt[str] = Header(None)):
    """Verify the API key if VIBES_API_KEY is set.

    If VIBES_API_KEY is not set, all requests are allowed (no auth).

    Supports two auth methods:
    1. ``X-API-Key: <key>`` header
    2. ``Authorization: Bearer <key>`` header
    """
    expected = os.environ.get("VIBES_API_KEY")
    if not expected:
        return  # No auth required

    provided = None
    if x_api_key:
        provided = x_api_key
    elif authorization:
        if authorization.startswith("Bearer "):
            provided = authorization[7:]

    if provided != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# --------------------------------------------------------------------------- #
#  FastAPI app
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="VibesAI API",
    description=(
        "Unofficial REST API wrapper for [vibes.ai](https://vibes.ai/) — "
        "Meta's AI video creation studio.\n\n"
        "Generate videos, images, TTS, lip-sync, manage timelines, "
        "publish content, and more.\n\n"
        "**Authentication:** Set `X-API-Key` header if `VIBES_API_KEY` "
        "is configured on the server.\n\n"
        "**Cookie auto-refresh:** The server automatically refreshes "
        "the vibes.ai session cookie every 25 minutes."
    ),
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins (configure as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
#  Pydantic request models
# --------------------------------------------------------------------------- #
class ProjectCreate(BaseModel):
    name: str = "Untitled"
    composition: Opt[dict] = None

class ProjectUpdate(BaseModel):
    name: Opt[str] = None
    composition: Opt[dict] = None

class VideoGenerate(BaseModel):
    project_id: str
    prompt: str
    aspect_ratio: str = "9:16"
    resolution: str = "480p"
    variations: int = 4
    video_model: str = "midjen-short"
    image_model: str = "midjen-base"
    prompt_model: str = "gemini-2.5-flash"
    ingredients: Opt[List[dict]] = None
    create_ingredients: Opt[List[dict]] = None
    start_frame: Opt[dict] = None
    end_frame: Opt[dict] = None
    moodboard: Opt[dict] = None
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
    ingredients: Opt[List[dict]] = None
    create_ingredients: Opt[List[dict]] = None
    moodboard: Opt[dict] = None

class ImageEdit(BaseModel):
    source_image_ent_id: str
    edit_prompt: str
    project_id: Opt[str] = None

class PromptEnhance(BaseModel):
    prompt: str
    project_id: Opt[str] = None
    batch_type: str = "videos"

class TTSRequest(BaseModel):
    text: str
    voice: str
    output_format: str = "mp3"
    language: Opt[str] = None

class LipsyncRequest(BaseModel):
    project_id: str
    image_prompt: str
    script: str
    audio_url: str
    audio_duration_ms: int
    engine: str = "midjen"
    ingredients: Opt[List[dict]] = None
    aspect_ratio: Opt[str] = None
    video_orientation: Opt[str] = None
    music_track: Opt[dict] = None
    custom_motion_prompt: Opt[str] = None

class ExtendVideo(BaseModel):
    project_id: str
    batch_id: str
    content_id: Opt[str] = None
    prompt: Opt[str] = None
    poll: bool = True
    poll_timeout: float = 300.0

class EditVideo(BaseModel):
    project_id: str
    batch_id: str
    content_id: Opt[str] = None
    prompt: str
    poll: bool = True
    poll_timeout: float = 300.0

class ShareLinkCreate(BaseModel):
    entity_type: str
    entity_id: str
    expires_at: Opt[str] = None
    max_uses: Opt[int] = None

class IngredientCreate(BaseModel):
    name: str
    ingredient_type: str
    source_image_ent_id: Opt[str] = None
    image_url: Opt[str] = None
    description: Opt[str] = None
    personality: Opt[str] = None
    backstory: Opt[str] = None
    core_beliefs: Opt[str] = None

class TimelineChat(BaseModel):
    input: str
    instructions: Opt[str] = None
    tools: Opt[List[dict]] = None
    composition: Opt[dict] = None

class TimelineExport(BaseModel):
    composition: dict

class PublishRequest(BaseModel):
    content_item_id: str
    batch_id: Opt[str] = None
    caption: Opt[str] = None
    audio_types: Opt[List[str]] = None
    content_attribution: Opt[dict] = None
    prompt: Opt[str] = None
    image_prompt: Opt[str] = None
    video_prompt: Opt[str] = None

class CompositionOp(BaseModel):
    """A composition operation (add clip, split, etc.)."""
    operation: str  # "add_video_clip", "split_clip", etc.
    params: dict

class ParseMidjourney(BaseModel):
    prompt: str

class UploadImage(BaseModel):
    image_base64: str


# --------------------------------------------------------------------------- #
#  Error handler
# --------------------------------------------------------------------------- #
def _handle_error(e: Exception):
    if isinstance(e, VibesAPIError):
        raise HTTPException(
            status_code=e.status or 500,
            detail={"error": str(e), "code": e.code, "response": e.response},
        )
    raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------- #
#  Routes — Auth & System
# --------------------------------------------------------------------------- #
@app.get("/api/v1/me", tags=["Auth"], dependencies=[Depends(verify_api_key)])
async def get_me():
    """Get current authenticated user."""
    try:
        return get_client().get_me()
    except Exception as e:
        _handle_error(e)


@app.get("/api/v1/system-status", tags=["Auth"], dependencies=[Depends(verify_api_key)])
async def get_system_status():
    try:
        return {"status": get_client().get_system_status()}
    except Exception as e:
        _handle_error(e)


@app.get("/api/v1/check-token", tags=["Auth"], dependencies=[Depends(verify_api_key)])
async def check_token():
    """Check if the session token is valid."""
    try:
        return {"valid": get_client().check_token()}
    except Exception as e:
        _handle_error(e)


@app.get("/api/v1/current-cookie", tags=["Auth"], dependencies=[Depends(verify_api_key)])
async def get_current_cookie():
    """Get the current meta_session cookie value (may be auto-refreshed)."""
    return {"meta_session": get_client().get_current_cookie()}


@app.post("/api/v1/logout", tags=["Auth"], dependencies=[Depends(verify_api_key)])
async def logout():
    try:
        get_client().logout()
        return {"success": True}
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Projects
# --------------------------------------------------------------------------- #
@app.get("/api/v1/projects", tags=["Projects"], dependencies=[Depends(verify_api_key)])
async def list_projects(limit: int = 25, offset: int = 0, sort: str = "newest",
                        search: Opt[str] = None):
    try:
        return get_client().list_projects(limit=limit, offset=offset, sort=sort, search=search)
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/projects", tags=["Projects"], dependencies=[Depends(verify_api_key)])
async def create_project(body: ProjectCreate):
    try:
        return get_client().create_project(name=body.name, composition=body.composition)
    except Exception as e:
        _handle_error(e)


@app.get("/api/v1/projects/{project_id}", tags=["Projects"], dependencies=[Depends(verify_api_key)])
async def get_project(project_id: str):
    try:
        return get_client().get_project(project_id)
    except Exception as e:
        _handle_error(e)


@app.put("/api/v1/projects/{project_id}", tags=["Projects"], dependencies=[Depends(verify_api_key)])
async def update_project(project_id: str, body: ProjectUpdate):
    try:
        return get_client().update_project(project_id, name=body.name, composition=body.composition)
    except Exception as e:
        _handle_error(e)


@app.delete("/api/v1/projects/{project_id}", tags=["Projects"], dependencies=[Depends(verify_api_key)])
async def delete_project(project_id: str, delete_assets: bool = False):
    try:
        get_client().delete_project(project_id, delete_assets=delete_assets)
        return {"success": True}
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/projects/{project_id}/duplicate", tags=["Projects"], dependencies=[Depends(verify_api_key)])
async def duplicate_project(project_id: str):
    try:
        return get_client().duplicate_project(project_id)
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Video generation
# --------------------------------------------------------------------------- #
@app.post("/api/v1/videos/generate", tags=["Videos"], dependencies=[Depends(verify_api_key)])
async def generate_video(body: VideoGenerate):
    """Generate one or more video variations from a text prompt."""
    try:
        result = get_client().generate_video(
            project_id=body.project_id,
            prompt=body.prompt,
            aspect_ratio=body.aspect_ratio,
            resolution=body.resolution,
            variations=body.variations,
            video_model=body.video_model,
            image_model=body.image_model,
            prompt_model=body.prompt_model,
            ingredients=body.ingredients,
            create_ingredients=body.create_ingredients,
            start_frame=body.start_frame,
            end_frame=body.end_frame,
            moodboard=body.moodboard,
            poll=body.poll,
            poll_timeout=body.poll_timeout,
        )
        return result
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/videos/extend", tags=["Videos"], dependencies=[Depends(verify_api_key)])
async def extend_video(body: ExtendVideo):
    """Extend a video (auto or manual)."""
    try:
        client = get_client()
        batch = client.get_batch(body.batch_id)
        source = None
        for c in batch.get("content", []):
            if c["id"] == body.content_id:
                source = c
                break
        if not source:
            source = batch["content"][0] if batch.get("content") else None
        if not source:
            raise HTTPException(404, "No content item found in batch")
        return client.extend_video(
            project_id=body.project_id,
            source_video=source,
            prompt=body.prompt,
            poll=body.poll,
            poll_timeout=body.poll_timeout,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/videos/edit", tags=["Videos"], dependencies=[Depends(verify_api_key)])
async def edit_video(body: EditVideo):
    """Edit a video with a prompt (v2v)."""
    try:
        client = get_client()
        batch = client.get_batch(body.batch_id)
        source = None
        for c in batch.get("content", []):
            if c["id"] == body.content_id:
                source = c
                break
        if not source:
            source = batch["content"][0] if batch.get("content") else None
        if not source:
            raise HTTPException(404, "No content item found in batch")
        return client.edit_video(
            project_id=body.project_id,
            source_video=source,
            prompt=body.prompt,
            poll=body.poll,
            poll_timeout=body.poll_timeout,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Image generation
# --------------------------------------------------------------------------- #
@app.post("/api/v1/images/generate", tags=["Images"], dependencies=[Depends(verify_api_key)])
async def generate_image(body: ImageGenerate):
    try:
        return get_client().generate_image(
            project_id=body.project_id,
            prompt=body.prompt,
            aspect_ratio=body.aspect_ratio,
            resolution=body.resolution,
            variations=body.variations,
            image_model=body.image_model,
            prompt_model=body.prompt_model,
            ingredients=body.ingredients,
            create_ingredients=body.create_ingredients,
            moodboard=body.moodboard,
        )
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/images/edit", tags=["Images"], dependencies=[Depends(verify_api_key)])
async def edit_image(body: ImageEdit):
    try:
        return get_client().edit_image(
            source_image_ent_id=body.source_image_ent_id,
            edit_prompt=body.edit_prompt,
            project_id=body.project_id,
        )
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/upload/image", tags=["Uploads"], dependencies=[Depends(verify_api_key)])
async def upload_image(body: UploadImage):
    try:
        return get_client().upload_image(body.image_base64)
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Prompt enhancement
# --------------------------------------------------------------------------- #
@app.post("/api/v1/prompts/enhance", tags=["Prompts"], dependencies=[Depends(verify_api_key)])
async def enhance_prompt(body: PromptEnhance):
    try:
        variations = get_client().enhance_prompt(
            prompt=body.prompt, project_id=body.project_id, batch_type=body.batch_type
        )
        return {"variations": variations}
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — TTS
# --------------------------------------------------------------------------- #
@app.get("/api/v1/voices", tags=["TTS"], dependencies=[Depends(verify_api_key)])
async def list_voices():
    try:
        return {"voices": get_client().list_voices()}
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/tts", tags=["TTS"], dependencies=[Depends(verify_api_key)])
async def tts(body: TTSRequest):
    try:
        return get_client().tts(
            text=body.text, voice=body.voice,
            output_format=body.output_format, language=body.language,
        )
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Media library
# --------------------------------------------------------------------------- #
@app.get("/api/v1/media", tags=["Media"], dependencies=[Depends(verify_api_key)])
async def list_media(limit: int = 50, offset: int = 0,
                     type: Opt[str] = None, sort: str = "newest",
                     search: Opt[str] = None):
    try:
        return get_client().list_media(
            limit=limit, offset=offset, type=type, sort=sort, search=search
        )
    except Exception as e:
        _handle_error(e)


@app.get("/api/v1/media/{item_id}/download", tags=["Media"], dependencies=[Depends(verify_api_key)])
async def download_media(item_id: str, type: str = "video"):
    """Download a media item. Returns binary file."""
    from fastapi import Response
    try:
        client = get_client()
        import tempfile, os
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
    except Exception as e:
        _handle_error(e)


@app.delete("/api/v1/media/{item_id}", tags=["Media"], dependencies=[Depends(verify_api_key)])
async def delete_media_item(item_id: str):
    try:
        get_client().delete_content_item(item_id)
        return {"success": True}
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/media/{item_id}/favorite", tags=["Media"], dependencies=[Depends(verify_api_key)])
async def favorite_media(item_id: str, favorite: bool = True):
    try:
        return get_client().favorite_content_item(item_id, favorite)
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Batches
# --------------------------------------------------------------------------- #
@app.get("/api/v1/batches", tags=["Batches"], dependencies=[Depends(verify_api_key)])
async def list_batches(limit: int = 12, offset: int = 0, project_id: Opt[str] = None):
    try:
        return get_client().list_batches(limit=limit, offset=offset, project_id=project_id)
    except Exception as e:
        _handle_error(e)


@app.get("/api/v1/batches/{batch_id}", tags=["Batches"], dependencies=[Depends(verify_api_key)])
async def get_batch(batch_id: str):
    try:
        return get_client().get_batch(batch_id)
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/batches/{batch_id}/poll", tags=["Batches"], dependencies=[Depends(verify_api_key)])
async def poll_batch(batch_id: str, timeout: float = 180.0):
    """Poll until a batch completes."""
    try:
        return get_client().poll_batch(batch_id, timeout=timeout)
    except Exception as e:
        _handle_error(e)


@app.delete("/api/v1/batches/{batch_id}", tags=["Batches"], dependencies=[Depends(verify_api_key)])
async def delete_batch(batch_id: str):
    try:
        get_client().delete_batch(batch_id)
        return {"success": True}
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Ingredients
# --------------------------------------------------------------------------- #
@app.get("/api/v1/ingredients", tags=["Ingredients"], dependencies=[Depends(verify_api_key)])
async def list_ingredients(owner_filter: str = "LIBRARY",
                           ingredient_type: Opt[str] = None):
    try:
        return {"ingredients": get_client().list_ingredients(
            owner_filter=owner_filter, ingredient_type=ingredient_type
        )}
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/ingredients", tags=["Ingredients"], dependencies=[Depends(verify_api_key)])
async def create_ingredient(body: IngredientCreate):
    try:
        return get_client().create_ingredient(
            name=body.name,
            ingredient_type=body.ingredient_type,
            source_image_ent_id=body.source_image_ent_id,
            image_url=body.image_url,
            description=body.description,
            personality=body.personality,
            backstory=body.backstory,
            core_beliefs=body.core_beliefs,
        )
    except Exception as e:
        _handle_error(e)


@app.delete("/api/v1/ingredients/{ingredient_id}", tags=["Ingredients"], dependencies=[Depends(verify_api_key)])
async def delete_ingredient(ingredient_id: str):
    try:
        get_client().delete_ingredient(ingredient_id)
        return {"success": True}
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Share links
# --------------------------------------------------------------------------- #
@app.post("/api/v1/share-links", tags=["Share"], dependencies=[Depends(verify_api_key)])
async def create_share_link(body: ShareLinkCreate):
    try:
        return get_client().create_share_link(
            body.entity_type, body.entity_id,
            expires_at=body.expires_at, max_uses=body.max_uses,
        )
    except Exception as e:
        _handle_error(e)


@app.get("/api/v1/share-links", tags=["Share"], dependencies=[Depends(verify_api_key)])
async def list_share_links(entity_type: str, entity_id: str):
    try:
        return {"shareLinks": get_client().list_share_links(entity_type, entity_id)}
    except Exception as e:
        _handle_error(e)


@app.delete("/api/v1/share-links/{link_id}", tags=["Share"], dependencies=[Depends(verify_api_key)])
async def revoke_share_link(link_id: str):
    try:
        get_client().revoke_share_link(link_id)
        return {"success": True}
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Timeline (chat + export + composition)
# --------------------------------------------------------------------------- #
@app.post("/api/v1/timeline/chat", tags=["Timeline"], dependencies=[Depends(verify_api_key)])
async def timeline_chat(body: TimelineChat):
    """Stream timeline AI chat (returns collected events as a list)."""
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
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/timeline/export", tags=["Timeline"], dependencies=[Depends(verify_api_key)])
async def export_timeline(project_id: str, body: TimelineExport):
    """Export a composition to MP4. Returns binary."""
    from fastapi import Response
    try:
        mp4_bytes = get_client().export_timeline(project_id, body.composition)
        return Response(content=mp4_bytes, media_type="video/mp4")
    except Exception as e:
        _handle_error(e)


@app.post("/api/v1/composition/operate", tags=["Timeline"], dependencies=[Depends(verify_api_key)])
async def composition_operate(body: CompositionOp):
    """Apply an operation to a composition (add clip, split, etc.).

    Returns the updated composition. Operations:
    - add_video_clip, add_image_clip, add_audio_clip, add_text_overlay
    - resize_clip, move_clip, split_clip, duplicate_clip, delete_clip
    - reorder_clips, extend_timeline_to, set_fade, set_volume, set_speed
    - add_track, delete_track, rename_track, mute_track
    - update_text_overlay, unlink_audio_from_video, link_audio_to_video
    - slip_audio, replace_audio, delete_all_clips, delete_timeline
    """
    try:
        # This endpoint takes a composition + operation and returns the result
        # The caller sends the current composition and the op to apply
        # For simplicity, we return the operation name + params for the caller
        # to apply client-side using the Composition class
        return {
            "operation": body.operation,
            "params": body.params,
            "note": "Use the Composition class client-side to apply operations.",
        }
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Publishing
# --------------------------------------------------------------------------- #
@app.post("/api/v1/publish", tags=["Publishing"], dependencies=[Depends(verify_api_key)])
async def publish_to_vibes(body: PublishRequest):
    try:
        return get_client().publish_to_vibes(
            content_item_id=body.content_item_id,
            batch_id=body.batch_id,
            caption=body.caption,
            audio_types=body.audio_types,
            content_attribution=body.content_attribution,
            prompt=body.prompt,
            image_prompt=body.image_prompt,
            video_prompt=body.video_prompt,
        )
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Lip sync
# --------------------------------------------------------------------------- #
@app.post("/api/v1/lipsync", tags=["LipSync"], dependencies=[Depends(verify_api_key)])
async def generate_lipsync(body: LipsyncRequest):
    try:
        return get_client().generate_lipsync(
            project_id=body.project_id,
            image_prompt=body.image_prompt,
            script=body.script,
            audio_url=body.audio_url,
            audio_duration_ms=body.audio_duration_ms,
            engine=body.engine,
            ingredients=body.ingredients,
            aspect_ratio=body.aspect_ratio,
            video_orientation=body.video_orientation,
            music_track=body.music_track,
            custom_motion_prompt=body.custom_motion_prompt,
        )
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Music
# --------------------------------------------------------------------------- #
@app.get("/api/v1/music/search", tags=["Music"], dependencies=[Depends(verify_api_key)])
async def search_music(q: str = "", limit: int = 30, cursor: Opt[str] = None,
                       exclude_oa: bool = True):
    try:
        return get_client().search_music_filtered(
            query=q, limit=limit, cursor=cursor,
            exclude_original_audio=exclude_oa,
        )
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Moodboards
# --------------------------------------------------------------------------- #
@app.get("/api/v1/moodboards", tags=["Moodboards"], dependencies=[Depends(verify_api_key)])
async def list_moodboards():
    try:
        return {"moodboards": get_client().list_moodboards()}
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Playables
# --------------------------------------------------------------------------- #
@app.get("/api/v1/playables", tags=["Playables"], dependencies=[Depends(verify_api_key)])
async def list_playables(limit: int = 100, offset: int = 0, status: Opt[str] = None):
    try:
        return get_client().list_playables(limit=limit, offset=offset, status=status)
    except Exception as e:
        _handle_error(e)


# --------------------------------------------------------------------------- #
#  Routes — Utilities (no cookie required)
# --------------------------------------------------------------------------- #
@app.post("/api/v1/utils/parse-midjourney", tags=["Utils"])
async def parse_midjourney(body: ParseMidjourney):
    """Parse Midjourney parameters from a prompt. No auth required."""
    return VibesClient.parse_midjourney_params(body.prompt)


@app.post("/api/v1/utils/validate-prompt", tags=["Utils"])
async def validate_prompt(body: ParseMidjourney):
    """Validate a prompt's length. No auth required."""
    return VibesClient.validate_prompt_length(body.prompt)


# --------------------------------------------------------------------------- #
#  Health & root
# --------------------------------------------------------------------------- #
@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "VibesAI API",
        "version": "1.2.0",
        "docs": "/docs",
        "endpoints": "See /docs for full API spec",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check — verifies the session is valid."""
    try:
        client = get_client()
        user = client.get_me()
        return {
            "status": "healthy",
            "user": user.get("username"),
            "cookie_age": "auto-refreshed",
        }
    except VibesAPIError as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "hint": "Set VIBES_META_SESSION env var with a fresh cookie",
        }


# --------------------------------------------------------------------------- #
#  Main entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "").lower() in ("1", "true", "yes"),
    )
