"""FastMCP application composition."""

import boto3
from fastmcp import FastMCP

from .config import Settings
from .services import BaseService, PostgresService, RDSService, S3Service


class AWSMCPServer:
    """Compose AWS services and register their MCP tools."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.session = boto3.Session(
            region_name=self.settings.aws_region,
            profile_name=self.settings.aws_profile,
        )
        self.mcp = FastMCP(
            name="aws-mcp-server",
            instructions=(
                "Tools for AWS S3, PostgreSQL and Amazon RDS. Inspect with the list/"
                "describe tools first. State-changing tools only work when the "
                "server was started with ALLOW_WRITES=true."
            ),
        )
        self.services: list[BaseService] = [
            S3Service(self.settings, self.session),
            PostgresService(self.settings, self.session),
            RDSService(self.settings, self.session),
        ]
        self._register_all()

    def _register_all(self) -> None:
        self.mcp.tool(self.aws_whoami)
        for service in self.services:
            service.register(self.mcp)

    async def aws_whoami(self) -> dict:
        """Show the configured AWS identity, region, and write setting."""
        client = self.session.client("sts")
        identity = await BaseService._run(client.get_caller_identity)
        return {
            "account": identity["Account"],
            "arn": identity["Arn"],
            "region": self.settings.aws_region,
            "writes_enabled": self.settings.allow_writes,
        }

    def run(self) -> None:
        if self.settings.mcp_transport == "stdio":
            self.mcp.run()
            return

        self.mcp.run(
            transport="http",
            host=self.settings.mcp_host,
            port=self.settings.mcp_port,
        )