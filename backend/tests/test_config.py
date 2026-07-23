from pathlib import Path

import pytest

from backend.src.config import load_settings


def test_plugin_configuration_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "AUTOCAD_AI_PLUGIN_URL",
        "http://localhost:9999/",
    )
    monkeypatch.setenv(
        "AUTOCAD_AI_PLUGIN_HEALTH_TIMEOUT_SECONDS",
        "4.5",
    )
    monkeypatch.setenv(
        "AUTOCAD_AI_PLUGIN_COMMAND_TIMEOUT_SECONDS",
        "55",
    )
    monkeypatch.setenv(
        "AUTOCAD_AI_LOG_PATH",
        str(tmp_path / "commands.jsonl"),
    )

    configured = load_settings()

    assert configured.plugin_url == "http://localhost:9999"
    assert configured.plugin_health_timeout_seconds == 4.5
    assert configured.plugin_command_timeout_seconds == 55.0
    assert configured.log_path == tmp_path / "commands.jsonl"


def test_non_positive_timeout_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AUTOCAD_AI_PLUGIN_COMMAND_TIMEOUT_SECONDS",
        "0",
    )

    with pytest.raises(ValueError, match="greater than zero"):
        load_settings()
