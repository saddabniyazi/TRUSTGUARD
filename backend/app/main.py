from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.core.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Day-1 scope: just make sure tables exist. Ingestion, agents, and
    # rate limiting get wired in on later days as their routers land.
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Autonomous multi-agent marketplace moderation copilot.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "env": settings.env}
