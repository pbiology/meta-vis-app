# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import connect_db, close_db
from app.config import settings
from app.routers import auth, ingest, cases, samples, subjects, users, metaval, alerts


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(samples.router, prefix="/api/v1")
app.include_router(subjects.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(metaval.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
