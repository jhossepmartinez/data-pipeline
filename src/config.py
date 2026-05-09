import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://pipeline_user:pipeline_pass@localhost:5433/pipeline_db",
    )
    SOURCE_DB_PATH: str = os.getenv("SOURCE_DB_PATH", "data/raw/northwind.db")
    API_KEY: str = os.getenv("API_KEY", "dev-key")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    @classmethod
    def source_db_url(cls) -> str:
        path = Path(cls.SOURCE_DB_PATH).resolve()
        return f"sqlite:///{path}"


config = Config()
