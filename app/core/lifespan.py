import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
import redis
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from app.config import settings
from app.db.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing application lifespan startup tasks...")
    
    # 1. Verify PostgreSQL connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
    except Exception as e:
        logger.critical(f"Database connection failed: {e}")
        raise RuntimeError(f"Startup failed: Database is unreachable. Details: {e}")

    # 2. Verify Alembic schema migrations are fully up-to-date
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        head_revisions = script.get_heads()
        
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_revision = context.get_current_revision()

        if not current_revision and head_revisions:
            raise RuntimeError("Database is completely unmigrated.")
        if head_revisions and current_revision not in head_revisions:
            raise RuntimeError(
                f"Database revision ({current_revision}) is not at script head ({head_revisions})."
            )
        logger.info(f"Database schema is verified up-to-date (revision: {current_revision}).")
    except Exception as e:
        logger.critical(f"Database schema verification failed: {e}")
        raise RuntimeError(f"Startup failed: Database schema is out of date. Details: {e}")

    # 3. Verify Redis connection (warning level fallback)
    try:
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2.0, socket_timeout=2.0)
        r.ping()
        logger.info("Redis connection verified successfully.")
    except Exception as e:
        logger.warning(
            f"Redis connectivity failed (resilient in-memory fallback will handle rate limits): {e}"
        )

    yield

    # 4. Clean teardown and cleanup on exit
    logger.info("Tearing down application lifespan. Disposing database engine...")
    try:
        engine.dispose()
        logger.info("Database engine pools disposed successfully.")
    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")
    logger.info("Application lifespan shutdown complete.")
