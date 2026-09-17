from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _migrate() -> None:
    """Idempotent column adds for pre-existing dev databases (create_all only
    creates missing tables, it never alters). Postgres-only syntax."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE seat_holds ADD COLUMN IF NOT EXISTS couple_cols VARCHAR(80) DEFAULT ''")
        )
        conn.execute(
            text("ALTER TABLE conflict_logs ADD COLUMN IF NOT EXISTS kind VARCHAR(20) DEFAULT ''")
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="SeatBond", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
