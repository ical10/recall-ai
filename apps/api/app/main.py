from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import router as api_router
from app.core.config import get_settings
from app.core.db import engine

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
SPA_DIST = BASE_DIR.parent / "web" / "dist"
STATIC_CACHE_MAX_AGE = 300


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="RecallAI", lifespan=lifespan)
    settings = get_settings()
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key.get_secret_value(),
        session_cookie="recallai_session",
        max_age=60 * 60 * 4,
        same_site="lax",
        https_only=settings.session_https_only,
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.middleware("http")
    async def add_static_cache_headers(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/static/") and response.status_code == 200:
            response.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
        return response

    @app.exception_handler(401)
    async def unauthenticated_handler(request: Request, _exc: Exception) -> Response:
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        return RedirectResponse(url="/login", status_code=302)

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(api_router)

    if SPA_DIST.exists():
        app.mount("/assets", StaticFiles(directory=str(SPA_DIST / "assets")), name="spa_assets")

        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str) -> FileResponse:
            path = request.url.path
            if any(path.startswith(p) for p in ("/api", "/auth", "/static", "/healthz")):
                from fastapi import HTTPException

                raise HTTPException(status_code=404)
            index = SPA_DIST / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return FileResponse(str(index), status_code=404)

    return app


app = create_app()
