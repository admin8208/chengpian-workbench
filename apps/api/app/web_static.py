from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from starlette.staticfiles import StaticFiles as StarletteStaticFiles

from app.settings import settings
from app.project_paths import projects_root_dir


class SpaStaticFiles(StarletteStaticFiles):
    async def get_response(self, path: str, scope):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        from starlette.responses import PlainTextResponse

        method = str(scope.get("method") or "").upper()

        def _should_spa_fallback() -> bool:
            if method != "GET":
                return False
            req_path = str(scope.get("path") or "")
            leaf = req_path.rsplit("/", 1)[-1]
            if req_path.startswith("/api") or req_path.startswith("/assets") or req_path.startswith("/exports") or req_path.startswith("/projects"):
                return False
            if req_path.startswith("/docs") or req_path == "/openapi.json" or req_path.startswith("/redoc"):
                return False
            if "." in leaf:
                return False
            try:
                hdrs = dict((k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in (scope.get("headers") or []))
                accept = (hdrs.get("accept") or "").lower()
                if accept and ("text/html" not in accept and "*/*" not in accept):
                    return False
            except Exception:
                pass
            return True

        async def _fallback_index():
            try:
                idx = Path(str(getattr(self, "directory", ""))) / "index.html"
                if not idx.exists():
                    return PlainTextResponse("Web UI not built. Run npm install && npm run build in apps/web and refresh.", status_code=404)
            except Exception:
                pass
            return await StarletteStaticFiles.get_response(self, "index.html", scope)

        try:
            resp = await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if getattr(e, "status_code", None) == 404 and _should_spa_fallback():
                return await _fallback_index()
            raise
        if getattr(resp, "status_code", None) == 404 and _should_spa_fallback():
            return await _fallback_index()
        return resp


def register_static_routes(app: FastAPI, *, expose_docs: bool) -> None:
    if not expose_docs:
        @app.get("/docs", include_in_schema=False)
        def _docs_disabled():
            raise HTTPException(status_code=404, detail="Not Found")

        @app.get("/redoc", include_in_schema=False)
        def _redoc_disabled():
            raise HTTPException(status_code=404, detail="Not Found")

        @app.get("/openapi.json", include_in_schema=False)
        def _openapi_disabled():
            raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/favicon.ico", include_in_schema=False)
    def _favicon_ico() -> Response:
        return Response(status_code=204)

    @app.get("/vite.svg", include_in_schema=False)
    def _vite_svg() -> Response:
        return Response(status_code=204)

    app.mount("/assets", StaticFiles(directory=str(settings.assets_dir), html=False), name="assets")
    app.mount("/exports", StaticFiles(directory=str(settings.exports_dir), html=False), name="exports")
