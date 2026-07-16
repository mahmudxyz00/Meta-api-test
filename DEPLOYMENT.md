# Deployment Guide

## Quick start (local)

```bash
pip install -e ".[server]"
export VIBES_META_SESSION="your-cookie"
export VIBES_API_KEY="your-secret"  # optional
python -m server
# Open http://localhost:8000/docs
```

## Docker

```bash
export VIBES_META_SESSION="your-cookie"
export VIBES_API_KEY="your-secret"
docker compose up -d
```

## Render / Railway / Fly.io

1. Push to GitHub
2. Create new web service, connect repo
3. Build: `pip install -e ".[server]"`
4. Start: `python -m server`
5. Add env vars: `VIBES_META_SESSION`, `VIBES_API_KEY`

## Cookie auto-refresh

The server automatically refreshes the vibes.ai session cookie:
- Intercepts `Set-Cookie` headers on every API response (sliding session)
- Background thread calls `/api/auth/me` every 25 minutes
- Optional persistence to `VIBES_COOKIE_FILE` for restart survival

## API authentication

Set `VIBES_API_KEY` env var. Clients send `X-API-Key: <key>` header.
If not set, no auth required.

## Usage

```bash
# Generate a video
curl -X POST https://your-api.com/api/v1/videos/generate \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"project_id":"...","prompt":"sunset over ocean","aspect_ratio":"16:9"}'

# List media
curl -H "X-API-Key: your-key" https://your-api.com/api/v1/media
```
