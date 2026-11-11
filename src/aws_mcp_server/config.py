"""Application settings loaded from environment variables and the local .env file."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


@dataclass(frozen=True)
class Settings:
    aws_region: str
    aws_profile: str | None
    s3_default_bucket: str | None
    s3_max_read_bytes: int
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str | None
    pg_sslmode: str
    pg_use_iam_auth: bool
    pg_max_rows: int
    pg_statement_timeout_ms: int
    allow_writes: bool
    mcp_transport: str
    mcp_host: str
    mcp_port: int
    log_level: str

    def __post_init__(self) -> None:
        if not self.aws_region.strip():
            raise ValueError("AWS_REGION must not be empty.")
        if not 1 <= self.pg_port <= 65535:
            raise ValueError("PG_PORT must be between 1 and 65535.")
        if self.s3_max_read_bytes <= 0:
            raise ValueError("S3_MAX_READ_BYTES must be greater than zero.")
        if self.pg_max_rows <= 0:
            raise ValueError("PG_MAX_ROWS must be greater than zero.")
        if self.pg_statement_timeout_ms <= 0:
            raise ValueError("PG_STATEMENT_TIMEOUT_MS must be greater than zero.")
        if self.mcp_transport not in {"stdio", "http", "streamable-http"}:
            raise ValueError("MCP_TRANSPORT must be stdio, http, or streamable-http.")
        if not 1 <= self.mcp_port <= 65535:
            raise ValueError("MCP_PORT must be between 1 and 65535.")
        if self.log_level.upper() not in {
            "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"
        }:
            raise ValueError("LOG_LEVEL must be a standard Python logging level.")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            aws_profile=os.getenv("AWS_PROFILE") or None,
            s3_default_bucket=os.getenv("S3_DEFAULT_BUCKET") or None,
            s3_max_read_bytes=int(os.getenv("S3_MAX_READ_BYTES", "1048576")),
            pg_host=os.getenv("PG_HOST", "localhost"),
            pg_port=int(os.getenv("PG_PORT", "5432")),
            pg_database=os.getenv("PG_DATABASE", "postgres"),
            pg_user=os.getenv("PG_USER", "postgres"),
            pg_password=os.getenv("PG_PASSWORD") or None,
            pg_sslmode=os.getenv("PG_SSLMODE", "require"),
            pg_use_iam_auth=_env_bool("PG_USE_IAM_AUTH"),
            pg_max_rows=int(os.getenv("PG_MAX_ROWS", "500")),
            pg_statement_timeout_ms=int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "15000")),
            allow_writes=_env_bool("ALLOW_WRITES"),
            mcp_transport=os.getenv("MCP_TRANSPORT", "stdio").strip().lower(),
            mcp_host=os.getenv("MCP_HOST", "127.0.0.1"),
            mcp_port=int(os.getenv("MCP_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )