from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import connect_db, close_db
from app.routers import ingest, runs, samples


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="meta-vis-app",
    description="Visualisation API for meta-vis",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ingest.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(samples.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}