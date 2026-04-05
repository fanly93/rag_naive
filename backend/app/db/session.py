from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

engine = create_engine(
    settings.mysql_sqlalchemy_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def init_mysql() -> None:
    # Import models before create_all so SQLAlchemy metadata is complete.
    from app import models  # noqa: F401

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.create_all(bind=engine)
