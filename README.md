# AWS MCP Server

MCP tools for Amazon S3, PostgreSQL, and Amazon RDS.

## Setup

Use Python 3.10 or newer. From the repository root, create and activate a virtual environment, then install the project:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Set the values in `.env` for your environment. Configure AWS credentials through the standard AWS credential chain or `AWS_PROFILE`; do not store AWS access keys in `.env`. Writes are disabled unless `ALLOW_WRITES=true`. Use least-privilege AWS and database identities.

For development tools, install the optional dependencies with `pip install -e ".[dev]"`.

## Run

Start the stdio server with `aws-mcp-server` or `python -m aws_mcp_server`.

For streamable HTTP, set `MCP_TRANSPORT=http`. The default bind address is `127.0.0.1`. HTTP authentication is not configured, so do not expose the server on a network interface without an authenticated boundary.

## Project Layout

```text
src/aws_mcp_server/
	services/       S3, RDS, PostgreSQL, and shared service code
	app.py          FastMCP composition and tool registration
	config.py       Validated environment settings
	server.py       CLI entry point
tests/            Automated tests
```

`.env` is local and Git-ignored; `.env.example` is the shareable configuration template. Runtime dependencies are declared in `pyproject.toml`.