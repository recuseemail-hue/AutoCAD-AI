import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_VERSION = "0.4.0"
SUPPORTED_SCHEMA_VERSIONS = ("0.1", "0.2", "0.3", "0.4")


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number.") from error

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


@dataclass(frozen=True)
class Settings:
    plugin_url: str
    plugin_health_timeout_seconds: float
    plugin_command_timeout_seconds: float
    bridge_url: str
    bridge_timeout_seconds: float
    log_path: Path
    log_level: str
    log_max_bytes: int
    log_backup_count: int


def load_settings() -> Settings:
    log_path = Path(
        os.getenv(
            "AUTOCAD_AI_LOG_PATH",
            str(PROJECT_ROOT / "backend" / "output" / "autocad-ai.jsonl"),
        )
    ).expanduser()

    return Settings(
        plugin_url=os.getenv(
            "AUTOCAD_AI_PLUGIN_URL",
            "http://localhost:8765",
        ).rstrip("/"),
        plugin_health_timeout_seconds=_positive_float(
            "AUTOCAD_AI_PLUGIN_HEALTH_TIMEOUT_SECONDS",
            2.0,
        ),
        plugin_command_timeout_seconds=_positive_float(
            "AUTOCAD_AI_PLUGIN_COMMAND_TIMEOUT_SECONDS",
            35.0,
        ),
        bridge_url=os.getenv(
            "AUTOCAD_AI_BRIDGE_URL",
            "http://127.0.0.1:8000",
        ).rstrip("/"),
        bridge_timeout_seconds=_positive_float(
            "AUTOCAD_AI_BRIDGE_TIMEOUT_SECONDS",
            40.0,
        ),
        log_path=log_path,
        log_level=os.getenv("AUTOCAD_AI_LOG_LEVEL", "INFO").upper(),
        log_max_bytes=_positive_int(
            "AUTOCAD_AI_LOG_MAX_BYTES",
            5 * 1024 * 1024,
        ),
        log_backup_count=_positive_int(
            "AUTOCAD_AI_LOG_BACKUP_COUNT",
            3,
        ),
    )


settings = load_settings()
