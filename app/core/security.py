"""Seguridad: HMAC, Fernet, bcrypt y JWT."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.ENCRYPTION_KEY:
            raise ValueError(
                "ENCRYPTION_KEY no está configurada en las variables de entorno"
            )
        _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet


def validate_meta_signature(payload: bytes, header: str, app_secret: str) -> bool:
    """Valida la firma HMAC SHA-256 del webhook de Meta.

    Args:
        payload: Body crudo del request (bytes).
        header: Valor del header X-Hub-Signature-256 (e.g. "sha256=abc123...").
        app_secret: App Secret de Meta para este tenant.

    Returns:
        True si la firma es válida.
    """
    expected = hmac.new(
        app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    received = header.replace("sha256=", "")
    return hmac.compare_digest(expected, received)


def encrypt(value: str) -> str:
    """Encripta un valor con Fernet. Devuelve el texto cifrado como string."""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Desencripta un valor cifrado con Fernet. Devuelve el texto plano."""
    return _get_fernet().decrypt(value.encode()).decode()


# --- Bcrypt ---


def hash_password(password: str) -> str:
    """Genera hash bcrypt de una contraseña."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Compara contraseña en texto plano con hash bcrypt."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


# --- JWT ---


def create_access_token(data: dict, expires_minutes: int = 480) -> str:
    """Genera JWT firmado con HS256. Expira en 8h por defecto."""
    if not settings.SECRET_KEY:
        raise ValueError(
            "SECRET_KEY no está configurada en las variables de entorno"
        )
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodifica y valida JWT. Lanza JWTError si inválido o expirado."""
    if not settings.SECRET_KEY:
        raise ValueError(
            "SECRET_KEY no está configurada en las variables de entorno"
        )
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
