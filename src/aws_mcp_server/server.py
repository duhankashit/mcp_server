"""CLI entry point for the AWS MCP server."""

import logging

from .app import AWSMCPServer
from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    AWSMCPServer(settings).run()


if __name__ == "__main__":
    main()