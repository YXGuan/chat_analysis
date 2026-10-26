"""Loopback API for private history imports and the saved-data frontend."""

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, staticfiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from kura.codex import DEFAULT_ENGINE, DEFAULT_MODEL, codex_binary
from kura.history import MAX_EXPORT_BYTES
from kura.imports import ImportStore

ROOT = Path(__file__).resolve().parents[2]


class LocalImport(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class AnalysisRequest(BaseModel):
    months: int = 3
    name: str = Field(default="My ChatGPT history", max_length=100)


def create_app(
    data_dir: Path | None = None, store: ImportStore | None = None
) -> FastAPI:
    """Create the local API, keeping imported histories outside public assets."""
    app = FastAPI(title="Kura local history")
    app.state.store = store or ImportStore(
        data_dir or Path(os.environ.get("KURA_DATA_DIR", ROOT / ".local/kura"))
    )

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # Cross-origin sites must not start hosted model work or read local paths.
        origin = request.headers.get("origin")
        if request.url.path.startswith("/api/") and origin:
            from urllib.parse import urlparse

            source = urlparse(origin)
            if source.hostname not in ("localhost", "127.0.0.1", "::1"):
                return JSONResponse(
                    {"detail": "Open Kura on localhost to import a history."},
                    status_code=403,
                )
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid_input(_request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.get("/api/status")
    def status():
        return {
            "engine": DEFAULT_ENGINE,
            "model": DEFAULT_MODEL,
            "codex_available": bool(codex_binary()),
        }

    @app.get("/api/datasets")
    def datasets():
        return app.state.store.datasets()

    @app.get("/api/datasets/{key}")
    def dataset(key: str):
        return app.state.store.profile(key)

    @app.post("/api/imports")
    async def upload(files: list[UploadFile] = File(...)):
        values = []
        size = 0
        try:
            for file in files:
                content = await file.read(MAX_EXPORT_BYTES - size + 1)
                size += len(content)
                if size > MAX_EXPORT_BYTES:
                    raise HTTPException(
                        413,
                        "This export exceeds the 256 MB import limit. Choose its conversation JSON files instead.",
                    )
                values.append((file.filename or "export.json", content))
            return await run_in_threadpool(app.state.store.upload, values)
        finally:
            for file in files:
                await file.close()

    @app.post("/api/imports/local")
    async def local_export(body: LocalImport):
        return await run_in_threadpool(app.state.store.local, Path(body.path))

    @app.get("/api/imports/{key}")
    def preview(key: str, months: int = 3):
        return app.state.store.preview(key, months)

    @app.post("/api/imports/{key}/analyze")
    def analyze(key: str, body: AnalysisRequest):
        return app.state.store.start(key, body.months, body.name)

    @app.get("/api/jobs/{key}")
    def job(key: str):
        return app.state.store.job(key)

    web_dir = ROOT / "kura/static/dist"
    if web_dir.exists():
        app.mount("/", staticfiles.StaticFiles(directory=str(web_dir), html=True))
    return app


api = create_app()
