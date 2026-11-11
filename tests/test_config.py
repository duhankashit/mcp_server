from dataclasses import replace

import pytest

from aws_mcp_server.config import Settings, _env_bool


def test_env_bool_accepts_common_true_and_false_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_FLAG", "yes")
    assert _env_bool("FEATURE_FLAG") is True

    monkeypatch.setenv("FEATURE_FLAG", "off")
    assert _env_bool("FEATURE_FLAG", default=True) is False


def test_env_bool_rejects_unknown_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_FLAG", "sometimes")

    with pytest.raises(ValueError, match="FEATURE_FLAG"):
        _env_bool("FEATURE_FLAG")


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("pg_port", 0, "PG_PORT"),
        ("s3_max_read_bytes", 0, "S3_MAX_READ_BYTES"),
        ("pg_max_rows", 0, "PG_MAX_ROWS"),
        ("pg_statement_timeout_ms", 0, "PG_STATEMENT_TIMEOUT_MS"),
        ("mcp_port", 65536, "MCP_PORT"),
        ("mcp_transport", "tcp", "MCP_TRANSPORT"),
    ],
)
def test_settings_reject_invalid_values(
    setting: str,
    value: object,
    message: str,
) -> None:
    settings = Settings.from_env()

    with pytest.raises(ValueError, match=message):
        replace(settings, **{setting: value})