from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.auditor.config import Settings

SessionFactory = sessionmaker[Session]


def build_session_factory(settings: Settings) -> tuple[Engine, SessionFactory]:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
    )
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
