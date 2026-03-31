"""ConnectionManager para WebSockets del chat admin (handoff)."""

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """Gestiona conexiones WebSocket por tenant_id."""

    def __init__(self) -> None:
        # {tenant_id_str: [WebSocket, ...]}
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, tenant_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(tenant_id, []).append(websocket)
        logger.info("ws_connected", tenant_id=tenant_id, total=len(self._connections[tenant_id]))

    def disconnect(self, tenant_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(tenant_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(tenant_id, None)
        logger.info("ws_disconnected", tenant_id=tenant_id)

    async def send_to_connection(self, websocket: WebSocket, data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            logger.warning("ws_send_failed")

    async def broadcast_to_tenant(self, tenant_id: str, data: dict) -> None:
        """Envia mensaje a todas las conexiones activas de un tenant."""
        conns = self._connections.get(tenant_id, [])
        dead = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tenant_id, ws)

    def has_connections(self, tenant_id: str) -> bool:
        return bool(self._connections.get(tenant_id))


# Singleton global
manager = ConnectionManager()
