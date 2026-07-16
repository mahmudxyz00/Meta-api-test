# Deployment Guide

This guide covers deploying the vibes-api server to various platforms.
The server is a FastAPI app that exposes all 127+ VibesClient methods
as REST endpoints, with **automatic cookie refresh** built in.

---

## 📋 Table of Contents

1. [Quick start (local)](#quick-start-local)
2. [Docker](#docker)
3. [Render](#render)
4. [Railway](#railway)
5. [Fly.io](#flyio)
6. [Heroku](#heroku)
7. [VPS / Vercel](#vps)
8. [Cookie auto-refresh](#cookie-auto-refresh)
9. [API authentication](#api-authentication)
10. [Using the deployed API](#using-the-deployed-api)

---

## Quick start (local)

```bash
# 1) Install dependencies
cd /home/z/my-project/download/vibes-api
pip install -e .
pip install -r requirements-server.txt

# 2) Set your cookie (from vibes.ai DevTools)
export VIBES_META_SESSION="e60e910a-...-K54E"

# 3) Set an API key (optional but recommended)
export VIBES_API_KEY="my-secret-key"

# 4) Start the server
python -m server

# 5) Open the interactive docs
#    http://localhost:8000/docs
```

---

## Docker

The easiest deployment method — works anywhere Docker runs.

### Option A: docker compose (recommended)

```bash
# 1) Set your cookie
export VIBES_META_SESSION="e60e910a-...-K54E"

# 2) Set an API key (optional)
export VIBES_API_KEY="my-secret-key"

# 3) Start
docker compose up -d

# 4) Check health
curl http://localhost:8000/health

# 5) View logs
docker compose logs -f

# 6) Stop
docker compose down
```

The cookie is persisted to a Docker volume (`vibes-data`), so it
survives container restarts and auto-refreshes in the background.

### Option B: docker build + run

```bash
# Build
docker build -t vibes-api .

# Run
docker run -d \
  -p 8000:8000 \
  -e VIBES_META_SESSION="your-cookie" \
  -e VIBES_API_KEY="your-api-key" \
  -v vibes-data:/data \
  --name vibes-api \
  vibes-api

# Check
curl http://localhost:8000/health
```

---

## Render

[Render](https://render.com) is a free-tier-friendly PaaS.

### Steps

1. Push your code to GitHub (already done at `mir-ashiq/VibesAI-api`)

2. Go to [render.com → New → Web Service](https://dashboard.render.com/select-repo)

3. Connect your GitHub repo `mir-ashiq/VibesAI-api`

4. Configure:
   - **Name:** `vibes-api`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -e . && pip install -r requirements-server.txt`
   - **Start Command:** `python -m server`
   - **Instance Type:** Free (or Starter for always-on)

5. Add Environment Variables:
   - `VIBES_META_SESSION` = your cookie value
   - `VIBES_API_KEY` = your secret API key
   - `VIBES_COOKIE_FILE` = `/tmp/.vibes_cookie`

6. Click **Create Web Service**

7. Your API will be live at `https://vibes-api.onrender.com`

### render.yaml (alternative)

Create a `render.yaml` in your repo:

```yaml
services:
  - type: web
    name: vibes-api
    env: python
    buildCommand: pip install -e . && pip install -r requirements-server.txt
    startCommand: python -m server
    envVars:
      - key: VIBES_META_SESSION
        sync: false  # set manually in dashboard
      - key: VIBES_API_KEY
        sync: false
      - key: VIBES_COOKIE_FILE
        value: /tmp/.vibes_cookie
    plan: free
```

Then: `render deploy`

---

## Railway

[Railway](https://railway.app) has a simple UX and good free tier.

### Steps

1. Go to [railway.app → New Project → Deploy from GitHub repo](https://railway.app/new)

2. Select `mir-ashiq/VibesAI-api`

3. Railway auto-detects the Dockerfile — no config needed

4. Add Variables:
   - `VIBES_META_SESSION` = your cookie
   - `VIBES_API_KEY` = your API key

5. Click **Deploy**

6. Your API will be live at `https://vibes-api-production.up.railway.app`

7. Add a custom domain in Settings → Networking

---

## Fly.io

[Fly.io](https://fly.io) is great for global edge deployment.

### Steps

```bash
# 1) Install flyctl
curl -L https://fly.io/install.sh | sh

# 2) Login
fly auth login

# 3) Launch (creates fly.toml automatically)
cd /home/z/my-project/download/vibes-api
fly launch --no-deploy

# 4) Set secrets
fly secrets set VIBES_META_SESSION="your-cookie"
fly secrets set VIBES_API_KEY="your-api-key"

# 5) Deploy
fly deploy

# 6) Open
fly open
```

### fly.toml (auto-generated, tweak as needed)

```toml
app = "vibes-api"
primary_region = "iad"

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0  # set to 1 for always-on

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256
```

For persistent cookie storage, add a volume:

```bash
fly volumes create vibes_data --size 1
fly secrets set VIBES_COOKIE_FILE=/data/.vibes_cookie
```

Add to `fly.toml`:
```toml
[mounts]
  source = "vibes_data"
  destination = "/data"
```

---

## Heroku

[Heroku](https://heroku.com) — classic PaaS.

### Steps

```bash
# 1) Install Heroku CLI, then:
heroku login

# 2) Create app
cd /home/z/my-project/download/vibes-api
heroku create vibes-api-yourname

# 3) Set buildpack
heroku buildpacks:set heroku/python

# 4) Set config vars
heroku config:set VIBES_META_SESSION="your-cookie"
heroku config:set VIBES_API_KEY="your-api-key"
heroku config:set VIBES_COOKIE_FILE="/tmp/.vibes_cookie"

# 5) Deploy
git push heroku main

# 6) Open
heroku open
```

Note: Heroku's free tier has an ephemeral filesystem — the cookie
file will be lost on restart. The background refresh thread will
re-establish the session from the initial `VIBES_META_SESSION` value.
For persistent storage, use Heroku Postgres or Redis.

---

## VPS

For a VPS (DigitalOcean, Linode, Hetzner, etc.):

### Steps

```bash
# 1) SSH into your server
ssh root@your-server

# 2) Install Docker
curl -fsSL https://get.docker.com | sh

# 3) Clone the repo
git clone https://github.com/mir-ashiq/VibesAI-api.git
cd VibesAI-api

# 4) Set env vars
export VIBES_META_SESSION="your-cookie"
export VIBES_API_KEY="your-api-key"

# 5) Start with docker compose
docker compose up -d

# 6) Set up a reverse proxy (nginx + certbot for HTTPS)
apt install nginx certbot python3-certbot-nginx -y

# Create /etc/nginx/sites-available/vibes-api
cat > /etc/nginx/sites-available/vibes-api << 'EOF'
server {
    server_name api.yourdomain.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/vibes-api /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d api.yourdomain.com
```

Your API is now live at `https://api.yourdomain.com`

---

## Cookie auto-refresh

The server implements **automatic cookie refresh** — you never need
to manually update the cookie (as long as the server stays running).

### How it works

Vibes.ai uses a **sliding session**: every API response includes a
`Set-Cookie: meta_session=...` header with a fresh token that extends
the session for ~30 minutes. The server intercepts this header on
every API call and updates its cookie automatically.

Additionally, a **background daemon thread** calls `/api/auth/me`
every 25 minutes to keep the session alive during idle periods
(matching the vibes.ai web app's behavior).

### Configuration

| Env var | Default | Description |
|---|---|---|
| `VIBES_COOKIE_FILE` | (none) | File path to persist the auto-refreshed cookie. Allows session to survive server restarts. |
| `VIBES_REFRESH_INTERVAL` | `1500` (25 min) | Background refresh interval in seconds. |

### Persistence

If `VIBES_COOKIE_FILE` is set (e.g., `/data/.vibes_cookie`), the
server writes the latest cookie to that file every time it's refreshed.
On server restart, it reads the cookie from the file instead of using
the initial `VIBES_META_SESSION` value.

This means:
- **Without persistence**: The server uses the initial cookie. If the
  server restarts after the cookie has expired (>30 min of no activity),
  you'd need to update `VIBES_META_SESSION`.
- **With persistence**: The server reads the latest refreshed cookie
  from disk on restart. As long as the server was running within the
  last 30 minutes before restart, the session continues seamlessly.

### What happens when the cookie expires?

If the cookie expires (e.g., server was down for >30 min), all API
calls will return `401 Session validation failed`. To recover:

1. Get a fresh cookie from vibes.ai (DevTools → Application → Cookies)
2. Update the env var: `VIBES_META_SESSION=new-value`
3. Restart the server

Or, if using `VIBES_COOKIE_FILE`, just write the new cookie to the
file and restart — no env var change needed.

---

## API authentication

The server supports optional API key authentication to protect your
deployed API from unauthorized use.

### Enable auth

Set the `VIBES_API_KEY` environment variable:

```bash
export VIBES_API_KEY="my-secret-api-key-12345"
```

### Use the API

Clients must send the API key in one of two ways:

```bash
# Option 1: X-API-Key header
curl -H "X-API-Key: my-secret-api-key-12345" \
     https://your-api.onrender.com/api/v1/me

# Option 2: Authorization: Bearer header
curl -H "Authorization: Bearer my-secret-api-key-12345" \
     https://your-api.onrender.com/api/v1/me
```

### Disable auth

If `VIBES_API_KEY` is not set (empty), all requests are allowed
without authentication. **Only do this for local development.**

### Utility endpoints (no auth)

The following endpoints don't require auth (they're offline utilities):

- `POST /api/v1/utils/parse-midjourney` — parse Midjourney params
- `POST /api/v1/utils/validate-prompt` — validate prompt length
- `GET /` — server info
- `GET /health` — health check
- `GET /docs` — Swagger UI

---

## Using the deployed API

Once deployed, your API is a full vibes.ai wrapper. Here are common
usage patterns:

### Generate a video

```bash
# Create a project
PROJECT=$(curl -s -X POST https://your-api.onrender.com/api/v1/projects \
  -H "X-API-Key: $VIBES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Video"}')
PROJECT_ID=$(echo $PROJECT | jq -r .id)

# Generate a video (waits for completion)
curl -s -X POST https://your-api.onrender.com/api/v1/videos/generate \
  -H "X-API-Key: $VIBES_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"prompt\": \"a sunset over the ocean, drone shot\",
    \"aspect_ratio\": \"16:9\",
    \"resolution\": \"720p\",
    \"variations\": 4
  }" | jq .
```

### Generate an image

```bash
curl -s -X POST https://your-api.onrender.com/api/v1/images/generate \
  -H "X-API-Key: $VIBES_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"prompt\": \"cyberpunk city at night\",
    \"aspect_ratio\": \"1:1\"
  }" | jq .
```

### Text-to-speech

```bash
curl -s -X POST https://your-api.onrender.com/api/v1/tts \
  -H "X-API-Key: $VIBES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "voice": "play_ai_Marisol"
  }' | jq .
```

### List your media

```bash
curl -s https://your-api.onrender.com/api/v1/media \
  -H "X-API-Key: $VIBES_API_KEY" | jq .
```

### Download a video

```bash
curl -o video.mp4 \
  https://your-api.onrender.com/api/v1/media/CONTENT_ID/download \
  -H "X-API-Key: $VIBES_API_KEY"
```

### Python client (using requests)

```python
import requests

API_URL = "https://your-api.onrender.com"
API_KEY = "your-api-key"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Create project
r = requests.post(f"{API_URL}/api/v1/projects", headers=HEADERS,
                  json={"name": "My Video"})
project_id = r.json()["id"]

# Generate video
r = requests.post(f"{API_URL}/api/v1/videos/generate", headers=HEADERS, json={
    "project_id": project_id,
    "prompt": "a sunset over the ocean",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "variations": 4,
})
batch = r.json()
print(f"Generated {len(batch['content'])} videos")

# Download the first one
video_id = batch["content"][0]["id"]
r = requests.get(f"{API_URL}/api/v1/media/{video_id}/download",
                 headers={"X-API-Key": API_KEY})
with open("video.mp4", "wb") as f:
    f.write(r.content)
```

### JavaScript / fetch

```javascript
const API_URL = "https://your-api.onrender.com";
const API_KEY = "your-api-key";

// Generate a video
const response = await fetch(`${API_URL}/api/v1/videos/generate`, {
  method: "POST",
  headers: {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    project_id: "your-project-id",
    prompt: "a sunset over the ocean",
    aspect_ratio: "16:9",
    resolution: "720p",
    variations: 4,
  }),
});
const batch = await response.json();
console.log(`Generated ${batch.content.length} videos`);
```

### Swagger UI

The best way to explore the API is the interactive docs at:
```
https://your-api.onrender.com/docs
```

You can try every endpoint directly from the browser.

---

## Cost comparison

| Platform | Free tier | Always-on | Notes |
|---|---|---|---|
| Render | Yes (sleeps after 15 min idle) | $7/mo (Starter) | Easiest setup |
| Railway | $5 trial credit | ~$5/mo (usage-based) | Best UX |
| Fly.io | 3 shared VMs (256MB) | ~$2-5/mo | Global edge |
| Heroku | No (ended Nov 2022) | $7/mo (Eco) | Classic choice |
| VPS | No | $4-10/mo | Most control |

**Recommendation:** Use **Render free tier** for testing, then upgrade
to **Railway** or **Fly.io** for production (always-on, persistent
storage, better performance).
