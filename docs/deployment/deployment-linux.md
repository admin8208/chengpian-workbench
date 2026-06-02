# Linux Deployment Guide

## Target

Deploy `成片工作台` on a single Hong Kong Linux server with:

- built frontend assets
- FastAPI API service
- Huey worker service
- PostgreSQL business database
- Redis task queue
- local `data/` directory
- nginx reverse proxy

Recommended OS:

- Ubuntu 22.04 or 24.04

Recommended machine size:

- minimum: 2 CPU / 4 GB RAM / 50 GB disk
- better: 4 CPU / 8 GB RAM / 100 GB disk

## Suggested Layout

```text
/opt/chengpian-workbench/
  apps/
    api/
    web/
  data/
  scripts/
  deploy/
```

## System Packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg nginx curl postgresql postgresql-contrib redis-server
```

Install Node.js 20 if missing.

Example:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## Backend Setup

```bash
cd /opt/chengpian-workbench/apps/api
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install piper-tts==1.4.2 g2pw sentence-stream unicode-rbnf transformers huggingface-hub tokenizers safetensors regex
```

The extra Python packages above enable newer Chinese offline voices such as
`zh_CN-chaowen-medium` and `zh_CN-xiao_ya-medium`.

## PostgreSQL Setup

Create a dedicated database and user before starting the API or worker.

Example:

```bash
sudo -u postgres psql
CREATE USER chengpian WITH PASSWORD 'change-this-password';
CREATE DATABASE chengpian OWNER chengpian;
GRANT ALL PRIVILEGES ON DATABASE chengpian TO chengpian;
\q
```

## Frontend Build

```bash
cd /opt/chengpian-workbench/apps/web
npm install
npm run build
```

## Environment Variables

Recommended production environment:

```bash
export CHENGPIAN_API_HOST=127.0.0.1
export CHENGPIAN_API_PORT=8010
export CHENGPIAN_RELOAD=0
export CHENGPIAN_EXPOSE_DOCS=0
export CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
export CHENGPIAN_REDIS_URL=redis://127.0.0.1:6379/0
export CHENGPIAN_DATA_DIR=/opt/chengpian-workbench/data
export CHENGPIAN_WEB_DIST_DIR=/opt/chengpian-workbench/apps/web/dist
```

Important:

- `CHENGPIAN_DATABASE_URL` is mandatory
- `CHENGPIAN_REDIS_URL` should point to the shared Redis queue
- the current backend only accepts PostgreSQL connection strings
- `data/` stores assets, exports, and local caches; it is no longer used as the business database or queue backend

Optional proxy variable for online TTS:

```bash
export CHENGPIAN_TTS_PROXY=http://127.0.0.1:7890
```

LLM, image generation, media search, and other backend HTTP requests do not inherit this TTS proxy by default.

## Manual Start

Important:

- 生产环境不要在 `root` shell 里手工启动 API / Worker
- 请优先使用 `systemd`，它会以 `chengpian` 用户运行服务
- 如果必须手工启动，也应先切换到 `chengpian` 用户再执行

API:

```bash
cd /opt/chengpian-workbench
./scripts/prod/linux/start_api.sh
```

Worker:

```bash
cd /opt/chengpian-workbench
./scripts/prod/linux/start_worker.sh
```

Health check:

```bash
curl http://127.0.0.1:8010/api/health
```

If you manually started services as `root` before, fix ownership first:

```bash
sudo chown -R chengpian:chengpian /opt/chengpian-workbench/data
```

## systemd

Copy these files into `/etc/systemd/system/`:

- `deploy/systemd/chengpian-api.service`
- `deploy/systemd/chengpian-worker.service`

The service templates load a shared environment file from:

- `/opt/chengpian-workbench/deploy/systemd/chengpian.env`

You can create it from the example file in the repository:

```bash
cp /opt/chengpian-workbench/deploy/systemd/chengpian.env.example /opt/chengpian-workbench/deploy/systemd/chengpian.env
chmod 600 /opt/chengpian-workbench/deploy/systemd/chengpian.env
```

Then edit `CHENGPIAN_DATABASE_URL` and `CHENGPIAN_REDIS_URL` inside that file.

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable chengpian-api
sudo systemctl enable chengpian-worker
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl start chengpian-api
sudo systemctl start chengpian-worker
```

Check status:

```bash
sudo systemctl status chengpian-api
sudo systemctl status chengpian-worker
```

Logs:

```bash
journalctl -u chengpian-api -f
journalctl -u chengpian-worker -f
```

## nginx

Use `deploy/nginx/chengpian.conf` as the site config.

Typical steps:

```bash
sudo cp deploy/nginx/chengpian.conf /etc/nginx/sites-available/chengpian.conf
sudo ln -sf /etc/nginx/sites-available/chengpian.conf /etc/nginx/sites-enabled/chengpian.conf
sudo nginx -t
sudo systemctl reload nginx
```

## Validation Checklist

- `apps/web/dist/index.html` exists
- API responds on `127.0.0.1:8010`
- worker process is alive
- `/api/health` returns ok JSON
- frontend opens through nginx
- create project works
- render job can be consumed by worker
- online TTS can be rechecked on the server itself if needed

## Notes

- Current production shape already uses PostgreSQL as the business database.
- Single-machine deployment is still valid because media files and exports remain on local `data/`.
- If task concurrency and operators increase later, prioritize PostgreSQL backup/observability, worker concurrency tuning, and shared storage strategy before further service splitting.
