"""Restaura tenants + admin_users desde backup JSON (v2) o .enc (v1 retrocompat).

Uso:
    python restore_tenant.py backups/backup_full_ULTIMO.json
    python restore_tenant.py backups/tenant_slug_2026-03-22.enc  # v1 retrocompat
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env antes de importar settings
load_dotenv()

from app.services.backup_service import restore_full_backup  # noqa: E402


async def main(backup_file: Path) -> None:
    summary = await restore_full_backup(backup_file)
    print(
        f"Restaurados: {summary['restored_tenants']} tenant(s), "
        f"{summary['restored_admins']} admin_user(s)"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python restore_tenant.py <archivo.json|.enc>")
        sys.exit(1)
    f = Path(sys.argv[1])
    if not f.exists():
        print(f"Archivo no encontrado: {f}")
        sys.exit(1)
    asyncio.run(main(f))
