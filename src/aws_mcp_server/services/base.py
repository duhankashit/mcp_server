"""Shared service plumbing for AWS and PostgreSQL operations."""

import asyncio
from typing import Any, Callable

import boto3
import psycopg2
from botocore.exceptions import BotoCoreError, ClientError
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..config import Settings


class BaseService:
    """Common settings, AWS session, write guard, and blocking I/O offloading."""

    def __init__(self, settings: Settings, session: boto3.Session) -> None:
        self.settings = settings
        self.session = session

    def _require_writes(self, action: str) -> None:
        if not self.settings.allow_writes:
            raise ToolError(
                f"'{action}' is disabled. Set ALLOW_WRITES=true to enable "
                "state-changing operations."
            )

    @staticmethod
    async def _run(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run blocking SDK/database work in a thread and normalize known errors."""
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except ToolError:
            raise
        except ClientError as exc:
            error = exc.response.get("Error", {})
            raise ToolError(
                f"AWS error {error.get('Code')}: {error.get('Message')}"
            ) from exc
        except BotoCoreError as exc:
            raise ToolError(f"AWS client error: {exc}") from exc
        except psycopg2.Error as exc:
            raise ToolError(f"PostgreSQL error: {str(exc).strip()}") from exc

    def register(self, mcp: FastMCP) -> None:
        raise NotImplementedError