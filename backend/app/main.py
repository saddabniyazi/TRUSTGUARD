from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.auth import router as auth_router
from app.api.feedback import router as feedback_router
from app.api.listings import router as listings_router
from app.api.moderation import router as moderation_router
from app.api.reviews import router as reviews_router
from app.api.rules import router as rules_router
from app.api.sellers import router as sellers_router
from app.core.config import settings
from app.core.seed_data import SEED_POLICY_RULES
from app.db.models import PolicyRule
from app.db.session import SessionLocal, init_db


def seed_policy_rules_if_empty() -> None:
    """
    Populates the policy_rules table on first run only — if any rule
    already exists we leave it alone, since an admin may have edited or
    deactivated seed rules and a re-seed shouldn't clobber that.
    """
    db = SessionLocal()
    try:
        if db.query(PolicyRule).first() is not None:
            return
        for rule in SEED_POLICY_RULES:
            db.add(PolicyRule(category=rule["category"], rule_text=rule["rule_text"], version=1, active=True))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_policy_rules_if_empty()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Autonomous multi-agent marketplace moderation copilot.",
    version="0.7.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.frontend_origin.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sellers_router)
app.include_router(listings_router)
app.include_router(reviews_router)
app.include_router(rules_router)
app.include_router(agents_router)
app.include_router(moderation_router)
app.include_router(feedback_router)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "env": settings.env}
