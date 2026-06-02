import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.logging_setup import configure_safe_logging
from app.api.auth_web import auth_guard, router as auth_router
from app.api.asset import router as asset_router
from app.api.channel import router as channel_router
from app.api.feed import router as feed_router
from app.api.image import router as image_router
from app.api.job import router as job_router
from app.api.llm import router as llm_router
from app.api.media import router as media_router
from app.api.project import router as project_router
from app.api.project_ops import router as project_ops_router
from app.api.scene import router as scene_router
from app.api.system import router as system_router
from app.api.tools import router as tools_router
from app.api.tts import router as tts_router
from app.api.cloud import router as cloud_router
from app.application.feed import rebuild_all_projections
from app.db import init_db, session_scope
from app.seed import seed_channel_packs, seed_image_providers, seed_llm_providers
from app.image_service import normalize_image_providers
from app.llm_service import normalize_llm_providers
from app.settings import settings
from app.web_static import SpaStaticFiles, register_static_routes

configure_safe_logging()


def _rebuild_projections_background() -> None:
    threading.Thread(target=rebuild_all_projections, name="feed-projection-rebuild", daemon=True).start()


_expose_docs = os.environ.get("CHENGPIAN_EXPOSE_DOCS", "0").strip().lower() in ("1", "true", "yes")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_channel_packs()
    seed_llm_providers()
    seed_image_providers()
    with session_scope() as session:
        normalize_llm_providers(session)
        normalize_image_providers(session)
    _rebuild_projections_background()
    yield

app = FastAPI(
    title="成片工作台 API",
    version="0.1.0",
    docs_url="/docs" if _expose_docs else None,
    redoc_url="/redoc" if _expose_docs else None,
    openapi_url="/openapi.json" if _expose_docs else None,
    lifespan=lifespan,
)

register_static_routes(app, expose_docs=_expose_docs)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    return await auth_guard(request, call_next)


app.include_router(tts_router)
app.include_router(channel_router)
app.include_router(feed_router)
app.include_router(scene_router)
app.include_router(project_ops_router)
app.include_router(job_router)
app.include_router(project_router)
app.include_router(system_router)
app.include_router(tools_router)
app.include_router(asset_router)
app.include_router(llm_router)
app.include_router(image_router)
app.include_router(media_router)
app.include_router(auth_router)
app.include_router(cloud_router)

def _mount_frontend_dist() -> None:
    dist = settings.web_dist_dir
    try:
        print(f"[web] mount spa: {dist}")
    except Exception:
        pass
    app.mount("/", SpaStaticFiles(directory=str(dist), html=True, check_dir=False), name="web")


_mount_frontend_dist()
