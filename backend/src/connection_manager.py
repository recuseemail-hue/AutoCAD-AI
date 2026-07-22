from fastapi import WebSocket


class AutoCADConnectionManager:
    def __init__(self) -> None:
        self.connection: WebSocket | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connection = websocket

    def disconnect(self, websocket: WebSocket) -> None:
        if self.connection is websocket:
            self.connection = None

    def is_connected(self) -> bool:
        return self.connection is not None

    async def send_command(self, command: dict) -> None:
        if self.connection is None:
            raise RuntimeError("AutoCAD is not connected.")

        await self.connection.send_json(command)


autocad_connection_manager = AutoCADConnectionManager()