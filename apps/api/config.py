import os

DEFAULT_DEVELOPMENT_DATABASE_URL = (
    "postgresql+psycopg://compoundos:local-development-only@127.0.0.1:5432/compoundos"
)


def get_database_url() -> str:
    """Return the explicit PostgreSQL connection URL for local development."""
    return os.environ.get("DATABASE_URL", DEFAULT_DEVELOPMENT_DATABASE_URL)
