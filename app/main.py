import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent

from app.core.config import settings
from app.core.redis import close_redis
from app.routers.admin import router as admin_router
from app.routers.admin_chat import router as admin_chat_router
from app.routers.admin_features import router as admin_features_router
from app.routers.oauth import router as oauth_router
from app.routers.superadmin import router as superadmin_router
from app.routers.webhook import router as webhook_router


def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )


async def _safe_backup() -> None:
    """Backup fire-and-forget al arrancar. No bloquea el startup."""
    try:
        from app.services.backup_service import run_full_backup

        path = await run_full_backup()
        structlog.get_logger().info("startup_backup_ok", path=str(path))
    except Exception:
        structlog.get_logger().error("startup_backup_failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = structlog.get_logger()
    logger.info("attendoo_started", version="1.3.0")
    asyncio.create_task(_safe_backup())
    yield
    await close_redis()
    logger.info("attendoo_stopped")


app = FastAPI(
    title="Attendoo",
    version="1.3.0",
    lifespan=lifespan,
)


app.include_router(webhook_router)
app.include_router(admin_router)
app.include_router(admin_chat_router)
app.include_router(admin_features_router)
app.include_router(superadmin_router)
app.include_router(oauth_router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/landing", StaticFiles(directory=str(BASE_DIR / "landing")), name="landing")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
