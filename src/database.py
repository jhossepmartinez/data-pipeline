from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import config

# Engine 1: SQLite (Source - Solo lectura)
source_engine = create_engine(
    config.source_db_url(),
    connect_args={"check_same_thread": False},
    echo=False,
)

# Engine 2: PostgreSQL (Target - Lectura/Escritura)
if config.DATABASE_URL.startswith("sqlite"):
    target_engine = create_engine(
        config.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
else:
    target_engine = create_engine(config.DATABASE_URL, echo=False)

# Session makers
SourceSessionLocal = sessionmaker(bind=source_engine)
TargetSessionLocal = sessionmaker(bind=target_engine)


@contextmanager
def get_source_session():
    """Sesion para leer de Northwind SQLite."""
    session = SourceSessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_target_session():
    """Sesion para escribir/leer la base canonica PostgreSQL."""
    session = TargetSessionLocal()
    try:
        yield session
    finally:
        session.close()
