# Deployment Guide

## Overview

Current product name: `成片工作台`

Current production shape is still a single-machine deployment with four runtime parts:

- Built frontend (`apps/web/dist`)
- API service (`apps/api/run_api.py`)
- Worker service (`apps/api/run_worker.py`)
- PostgreSQL business database
- Redis task queue

The API serves the built frontend in one-port mode.

## Supported Deployment Modes

### 1. Local Development

Use when developing frontend/backend features locally.

- Frontend: Vite dev server
- API: FastAPI with reload
- Worker: Huey worker (dev)
- Database: PostgreSQL
- Queue: Redis
- Runtime files: local `data/`

Typical command:

- `npm run dev` for frontend

### 2. Single-Machine Production

Use for one operator machine or a small internal deployment.

- Frontend: prebuilt static assets in `apps/web/dist`
- API: serves `/api`, `/assets`, `/exports`, and the frontend app
- Worker: separate long-running process
- Database: PostgreSQL
- Queue: Redis
- Runtime files: local `data/` directory shared by API and worker for assets/exports only

Typical runtime:

- nginx serves port `80`
- API runs via `chengpian-api.service`
- worker runs via `chengpian-worker.service`

### 3. Future Split Production

Target shape for later evolution:

- Static frontend hosting
- API service
- Worker service
- Shared data mount
- PostgreSQL kept as the business database
- Stronger database backup / connection pool / observability setup

This shape is **not** the current runtime default.

## Directory Expectations

## Data Boundaries

Current runtime data is split into two layers:

- PostgreSQL stores structured business data such as projects, scenes, jobs, app config, accounts, and provider metadata
- Redis stores Huey task queue data
- local `data/` stores generated media, exports, caches, and other machine-local artifacts

### Required database configuration

- `CHENGPIAN_DATABASE_URL` is required
- `CHENGPIAN_REDIS_URL` is required for the task queue
- only PostgreSQL connection strings are supported by the current backend

Example:

```bash
export CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
export CHENGPIAN_REDIS_URL=redis://127.0.0.1:6379/0
```

### Required runtime directories

- `data/`
- `data/assets/`
- `data/exports/`

### Important generated content

- library assets: `data/assets/library/`
- subtitles: `data/assets/subtitles/`
- audio: `data/assets/audio/`
- final videos: `data/exports/project_<id>/final.mp4`

## Production Start Sequence

1. Build frontend if `apps/web/dist/index.html` is missing
2. Start API
3. Start worker
4. Open browser through nginx on port `80`

## Ports

### Development

- Frontend dev: `5173`
- API dev: `8010`

### Production fallback logic

- prefer `8010`

## Network Notes

### Online capabilities run from the backend machine

The following features depend on the network of the machine that runs API/worker, not the browser:

- online TTS
- LLM providers
- image providers
- Pexels / Pixabay search
- Douyin parsing

If the browser can access the internet but the Python processes cannot, online features may still fail.

## Operational Commands

### Start development

```bash
npm run dev
```

### Start production

```bash
sudo systemctl restart chengpian-api chengpian-worker
sudo systemctl reload nginx
```

### systemd environment file

The systemd service templates support a shared environment file at:

- `/opt/chengpian-workbench/deploy/systemd/chengpian.env`

You can create it from the example file:

```bash
cp /opt/chengpian-workbench/deploy/systemd/chengpian.env.example /opt/chengpian-workbench/deploy/systemd/chengpian.env
chmod 600 /opt/chengpian-workbench/deploy/systemd/chengpian.env
```

At minimum, set:

```bash
CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
CHENGPIAN_REDIS_URL=redis://127.0.0.1:6379/0
```

### Check production ports and processes

```bash
ss -ltnp
systemctl status chengpian-api --no-pager
systemctl status chengpian-worker --no-pager
```

## Refactor Note

The repository has completed the first major in-place refactor:

- frontend views reorganized by domain
- frontend components reorganized by domain
- backend `tts / media / remix` moved into module domains
- route extraction from `main.py` has started

Future deployment docs should be updated after the remaining `project / asset / system` route migration is fully complete.
