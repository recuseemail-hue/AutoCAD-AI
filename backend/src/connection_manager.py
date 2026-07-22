import asyncio
from typing import Any

from fastapi import WebSocket


class AutoCADConnectionManager:
    def __init__(self) -> None:
        self.connection: WebSocket | None = None
        self.pending_commands: dict[str, asyncio.Future[dict[str, Any]]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connection = websocket

    def disconnect(self, websocket: WebSocket) -> None:
        if self.connection is websocket:
            self.connection = None

            for future in self.pending_commands.values():
                if not future.done():
                    future.set_exception(
                        RuntimeError("AutoCAD disconnected before returning a result.")
                    )

            self.pending_commands.clear()

    def is_connected(self) -> bool:
        return self.connection is not None

    async def send_command(
        self,
        command: dict[str, Any],
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        if self.connection is None:
            raise RuntimeError("AutoCAD is not connected.")

        command_id = command["command_id"]

        if command_id in self.pending_commands:
            raise ValueError(f"Command is already pending: {command_id}")

        future = asyncio.get_running_loop().create_future()
        self.pending_commands[command_id] = future

        try:
            await self.connection.send_json(command)
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        except TimeoutError as error:
            raise TimeoutError(
                f"AutoCAD did not return a result within {timeout_seconds:g} seconds."
            ) from error
        finally:
            self.pending_commands.pop(command_id, None)

    def resolve_command(self, response: dict[str, Any]) -> bool:
        command_id = response.get("command_id")

        if not isinstance(command_id, str):
            return False

        future = self.pending_commands.get(command_id)

        if future is None or future.done():
            return False

        future.set_result(response)
        return True


autocad_connection_manager = AutoCADConnectionManager()
