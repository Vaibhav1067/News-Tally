"""FastAPI application factory.

Run locally (from the repo root):
    uvicorn app.main:app --app-dir backend --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.middleware import BodySizeLimitMiddleware, RateLimitMiddleware, RequestLogMiddleware
from app.api.routes import router
from app.models import FactCheck
from app.services import ml_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("httpx", "huggingface_hub", "sentence_transformers", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("news_tally")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        if db.query(FactCheck).count() == 0:
            from app.services.seed import seed_factchecks
            from app.services.source_service import seed_sources

            n = seed_factchecks(db)
            seed_sources(db)
            log.info("Empty database: seeded %d fact-checks", n)
    ml_registry.get_registry()  # load models at startup, not on the first request
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name,
        version="0.1.0",
        description="Misinformation intelligence API for Indian fact-checks. "
                    "Surfaces published fact-checks and model signals; does not determine truth.",
        lifespan=lifespan,
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": errors})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": s.app_name, "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
