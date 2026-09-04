import uvicorn
from sqlalchemy import create_engine

from app.config import Settings
from app.storage.postgres import (
    PostgresLeadStore,
    PostgresNeighborhoodStore,
    PostgresPropertyLogStore,
)
from app.web import create_app

settings = Settings()

if not settings.database_url:
    raise ValueError(
        "DATABASE_URL is empty: LeadLogStore is retired and Postgres is now "
        "required. Set DATABASE_URL (e.g. postgres://user:pass@host:5432/inmobot)."
    )

_engine = create_engine(settings.database_url)
store = PostgresLeadStore(_engine)
neighborhood_store = PostgresNeighborhoodStore(_engine)
property_log_store = PostgresPropertyLogStore(_engine)
app = create_app(settings, store)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
