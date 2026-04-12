import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
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


async def _derivation_timeout_loop() -> None:
    """Cada 5 minutos revisa timeouts de conversaciones DERIVADAS en todos los tenants.

    Usa un lock Redis para garantizar que solo un worker lo ejecuta a la vez.
    """
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core.redis import get_redis
    from app.models.tenant import Tenant
    from app.services.derivation_service import check_derivation_timeout

    _LOCK_KEY = "derivation_timeout_loop:lock"
    _LOCK_TTL = 240  # 4 min — menor que el intervalo (5 min) para evitar deadlocks

    log = structlog.get_logger()
    while True:
        await asyncio.sleep(300)
        try:
            redis = await get_redis()
            acquired = await redis.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL)
            if not acquired:
                continue  # Otro worker ya está ejecutando el loop

            async with SessionLocal() as db:
                result = await db.execute(select(Tenant.id))
                tenant_ids = result.scalars().all()
            for tid in tenant_ids:
                async with SessionLocal() as db:
                    await check_derivation_timeout(tid, db)
                    await db.commit()
        except Exception:
            log.error("derivation_timeout_loop_error", exc_info=True)


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
    asyncio.create_task(_derivation_timeout_loop())
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


# 1.4 — Exception handlers: redirige navegadores a landing, JSON para APIs
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/", status_code=302)
    if exc.status_code >= 500:
        structlog.get_logger().error("http_error", path=str(request.url), status=exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    structlog.get_logger().error("unhandled_exception", path=str(request.url), exc_info=exc)
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/", status_code=302)
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
