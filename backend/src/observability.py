import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from backend.src.config import settings


COMMAND_LOGGER_NAME = "autocad_ai.commands"
command_logger = logging.getLogger(COMMAND_LOGGER_NAME)


def configure_command_logging() -> None:
    if command_logger.handlers:
        return

    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    command_logger.addHandler(handler)
    command_logger.setLevel(settings.log_level)
    command_logger.propagate = True


def log_command_event(
    event: str,
    *,
    command: dict[str, Any] | None = None,
    status: str | None = None,
    error_code: str | None = None,
    duration_ms: float | None = None,
) -> None:
    command = command or {}
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "schema_version": command.get("schema_version"),
        "run_id": command.get("run_id"),
        "import_id": command.get("import_id"),
        "command_id": command.get("command_id"),
        "application": command.get("application"),
        "operation": command.get("operation"),
        "status": status,
        "error_code": error_code,
        "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
    }
    command_logger.info(
        json.dumps(
            record,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


configure_command_logging()
