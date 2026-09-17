import os

# Point the app at a throwaway SQLite file before any app module is imported.
os.environ["DATABASE_URL"] = "sqlite:////tmp/seatbond_test.db"
os.environ["SEED_ON_EMPTY"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
