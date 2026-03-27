"""Backup completo de tenants + admin_users a JSON plano.

Uso:
    python backup_tenant.py
"""
import asyncio

from dotenv import load_dotenv

# Cargar .env antes de importar settings
load_dotenv()

from app.services.backup_service import run_full_backup  # noqa: E402


async def main() -> None:
    path = await run_full_backup()
    print(f"Backup guardado: {path}")


if __name__ == "__main__":
    asyncio.run(main())
