from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_couple_cols() -> None:
    """Backfill seat_holds.couple_cols on databases created before it existed."""
    insp = inspect(engine)
    if "seat_holds" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("seat_holds")}
    if "couple_cols" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE seat_holds ADD COLUMN couple_cols VARCHAR(40) NOT NULL DEFAULT ''")
            )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_couple_cols()
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
