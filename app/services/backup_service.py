"""Backup completo de tenants + admin_users a JSON plano. Rotación automática."""

import json
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import structlog

logger = structlog.get_logger()

BACKUP_DIR = Path(__file__).resolve().parents[2] / "backups"

TENANT_FIELDS = [
    "id",
    "slug",
    "nombre_negocio",
    "email_notificaciones",
    "whatsapp_phone_number_id",
    "whatsapp_token",
    "whatsapp_verify_token",
    "meta_app_secret",
    "google_calendar_id",
    "google_access_token",
    "google_refresh_token",
    "google_token_expiry",
    "bot_activo",
    "activo",
    "rate_limit_per_minute",
    "max_citas_activas",
    "created_at",
    "updated_at",
]
ADMIN_FIELDS = [
    "id",
    "tenant_id",
    "username",
    "password_hash",
    "role",
    "email",
    "created_at",
]
# Campos que se guardan encriptados en BD y se desencriptan en el backup
ENCRYPTED_FIELDS = {
    "whatsapp_token",
    "meta_app_secret",
    "google_access_token",
    "google_refresh_token",
}


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]


def _safe_decrypt(value: str | None, fernet) -> str | None:
    """Desencripta un valor Fernet; si falla (ya en plano), devuelve tal cual."""
    if value is None:
        return None
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return value


def _serialize(row: dict) -> dict:
    """Convierte tipos de asyncpg (datetime, UUID…) a str JSON-serializable."""
    result: dict = {}
    for k, v in row.items():
        if v is None:
            result[k] = None
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = str(v)
    return result


async def run_full_backup(keep_last: int = 7, backup_dir: Path | None = None) -> Path:
    """Exporta todos los tenants + admin_users a JSON plano. Rotación automática.

    Returns:
        Path del archivo de backup creado.
    """
    from app.core.config import settings
    from cryptography.fernet import Fernet

    out_dir = backup_dir or BACKUP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    conn = await asyncpg.connect(_dsn(settings.DATABASE_URL))

    try:
        tenant_rows = await conn.fetch(
            f"SELECT {', '.join(TENANT_FIELDS)} FROM tenants ORDER BY created_at"
        )
        admin_rows = await conn.fetch(
            f"SELECT {', '.join(ADMIN_FIELDS)} FROM admin_users ORDER BY created_at"
        )
    finally:
        await conn.close()

    tenants = []
    for row in tenant_rows:
        data = _serialize(dict(row))
        for field in ENCRYPTED_FIELDS:
            if data.get(field):
                data[field] = _safe_decrypt(data[field], fernet)
        tenants.append(data)

    admins = [_serialize(dict(row)) for row in admin_rows]

    payload = {
        "version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "env": {
            "ENCRYPTION_KEY": settings.ENCRYPTION_KEY,
            "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
            "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
            "META_APP_SECRET": settings.META_APP_SECRET,
        },
        "tenants": tenants,
        "admin_users": admins,
    }

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    out_file = out_dir / f"backup_full_{ts}.json"
    out_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Rotación: eliminar backups más antiguos conservando los últimos `keep_last`
    existing = sorted(out_dir.glob("backup_full_*.json"))
    for old in existing[:-keep_last]:
        old.unlink(missing_ok=True)

    logger.info(
        "backup_created",
        path=str(out_file),
        tenants=len(tenants),
        admins=len(admins),
    )
    return out_file


async def restore_full_backup(backup_file: Path) -> dict:
    """Restaura tenants + admin_users desde backup JSON (v2) o .enc (v1 retrocompat).

    Args:
        backup_file: Ruta al archivo .json (v2) o .enc (v1).

    Returns:
        Resumen {"restored_tenants": int, "restored_admins": int}.
    """
    from app.core.config import settings
    from cryptography.fernet import Fernet

    fernet = Fernet(settings.ENCRYPTION_KEY.encode())

    if backup_file.suffix == ".enc":
        # Retrocompatibilidad v1: archivo cifrado con Fernet, un solo tenant
        raw = json.loads(fernet.decrypt(backup_file.read_bytes()))
        payload = {"version": 1, "tenants": [raw], "admin_users": []}
    else:
        payload = json.loads(backup_file.read_text(encoding="utf-8"))

    conn = await asyncpg.connect(_dsn(settings.DATABASE_URL))
    restored_tenants = 0
    restored_admins = 0

    try:
        for t in payload.get("tenants", []):
            # Re-encriptar tokens con la ENCRYPTION_KEY actual antes de insertar
            for field in ENCRYPTED_FIELDS:
                if t.get(field):
                    t[field] = fernet.encrypt(t[field].encode()).decode()

            await conn.execute(
                """
                INSERT INTO tenants (
                    id, slug, nombre_negocio, email_notificaciones,
                    whatsapp_phone_number_id, whatsapp_token, whatsapp_verify_token,
                    meta_app_secret, google_calendar_id, google_access_token,
                    google_refresh_token, google_token_expiry,
                    bot_activo, activo, rate_limit_per_minute, max_citas_activas
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                ON CONFLICT (slug) DO UPDATE SET
                    nombre_negocio          = EXCLUDED.nombre_negocio,
                    email_notificaciones    = EXCLUDED.email_notificaciones,
                    whatsapp_phone_number_id= EXCLUDED.whatsapp_phone_number_id,
                    whatsapp_token          = EXCLUDED.whatsapp_token,
                    whatsapp_verify_token   = EXCLUDED.whatsapp_verify_token,
                    meta_app_secret         = EXCLUDED.meta_app_secret,
                    google_calendar_id      = EXCLUDED.google_calendar_id,
                    google_access_token     = EXCLUDED.google_access_token,
                    google_refresh_token    = EXCLUDED.google_refresh_token,
                    google_token_expiry     = EXCLUDED.google_token_expiry,
                    bot_activo              = EXCLUDED.bot_activo,
                    activo                  = EXCLUDED.activo,
                    rate_limit_per_minute   = EXCLUDED.rate_limit_per_minute,
                    max_citas_activas       = EXCLUDED.max_citas_activas
                """,
                t.get("id"),
                t.get("slug"),
                t.get("nombre_negocio"),
                t.get("email_notificaciones"),
                t.get("whatsapp_phone_number_id"),
                t.get("whatsapp_token"),
                t.get("whatsapp_verify_token"),
                t.get("meta_app_secret"),
                t.get("google_calendar_id"),
                t.get("google_access_token"),
                t.get("google_refresh_token"),
                t.get("google_token_expiry"),
                bool(t.get("bot_activo", True)),
                bool(t.get("activo", True)),
                int(t.get("rate_limit_per_minute", 10)),
                int(t.get("max_citas_activas", 5)),
            )
            restored_tenants += 1

        for u in payload.get("admin_users", []):
            await conn.execute(
                """
                INSERT INTO admin_users (id, tenant_id, username, password_hash, role, email)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (username) DO UPDATE SET
                    tenant_id     = EXCLUDED.tenant_id,
                    password_hash = EXCLUDED.password_hash,
                    role          = EXCLUDED.role,
                    email         = EXCLUDED.email
                """,
                u.get("id"),
                u.get("tenant_id"),
                u.get("username"),
                u.get("password_hash"),
                u.get("role"),
                u.get("email"),
            )
            restored_admins += 1

    finally:
        await conn.close()

    summary = {"restored_tenants": restored_tenants, "restored_admins": restored_admins}
    logger.info("backup_restored", **summary)
    return summary
