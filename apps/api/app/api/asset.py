"""Asset router extracted from the main application entrypoint."""

from fastapi import APIRouter

from .file_access import router as file_access_router
from .library_assets import router as library_assets_router
from .library_search import router as library_search_router
from .project_assets import router as project_assets_router

router = APIRouter(tags=["asset"])

router.include_router(project_assets_router)
router.include_router(library_assets_router)
router.include_router(library_search_router)
router.include_router(file_access_router)
