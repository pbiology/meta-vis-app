# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import setup_logging

# Configure logging before any router imports so all modules inherit the handlers.
setup_logging(settings.log_level)

from app.database import connect_db, close_db  # noqa: E402
from app.middleware import RequestLoggingMiddleware  # noqa: E402
from app.routers import (  # noqa: E402
    auth,
    ingest,
    cases,
    samples,
    subjects,
    users,
    metaval,
    alerts,
    taxa,
    ntc,
    config,
    health,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="meta-vis-app",
    version="0.1.0",
    lifespan=lifespan,
)

# Parse CORS origins from comma-separated config string
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(RequestLoggingMiddleware)

# API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(samples.router, prefix="/api/v1")
app.include_router(subjects.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(metaval.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(taxa.router, prefix="/api/v1")
app.include_router(ntc.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")

# Health endpoints live at root (not /api/v1) per K8s/Prometheus convention.
app.include_router(health.router)
