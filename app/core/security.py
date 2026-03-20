"""Seguridad: validación HMAC de Meta y encriptación Fernet."""

import hashlib
import hmac

from cryptography.fernet import Fernet

from app.core.config import settings

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
