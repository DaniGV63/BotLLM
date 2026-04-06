import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent

from app.core.config import settings
from app.core.redis import close_redis
from app.routers.admin import router as admin_router
from app.routers.admin_calendar import router as admin_calendar_router
from app.routers.admin_chat import router as admin_chat_router
from app.routers.admin_classes import router as admin_classes_router
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
    # 1.5 — Validación de arranque
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY no está configurada. Revisar .env")
    if not settings.ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY no está configurada. Revisar .env")
    logger.info("atendoo_started", version="1.7.0")
    asyncio.create_task(_safe_backup())
    yield
    await close_redis()
    logger.info("atendoo_stopped")


app = FastAPI(
    title="Atendoo",
    version="1.7.0",
    lifespan=lifespan,
)

# 1.3 — CORS
_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# 1.4 — Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    structlog.get_logger().error("unhandled_exception", path=str(request.url), exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


app.include_router(webhook_router)
app.include_router(admin_router)
app.include_router(admin_calendar_router)
app.include_router(admin_chat_router)
app.include_router(admin_classes_router)
app.include_router(admin_features_router)
app.include_router(superadmin_router)
app.include_router(oauth_router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/landing", StaticFiles(directory=str(BASE_DIR / "landing")), name="landing")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# 1.11 — robots.txt
@app.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    content = (BASE_DIR / "static" / "robots.txt").read_text(encoding="utf-8")
    return PlainTextResponse(content)
