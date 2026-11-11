"""PostgreSQL tools for self-hosted databases and RDS/Aurora PostgreSQL."""

import psycopg2
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from psycopg2.extras import RealDictCursor

from ..utils import jsonable
from .base import BaseService


class PostgresService(BaseService):
    def register(self, mcp: FastMCP) -> None:
        for function in (
            self.pg_list_schemas,
            self.pg_list_tables,
            self.pg_describe_table,
            self.pg_query,
            self.pg_execute,
        ):
            mcp.tool(function)

    def _password(self) -> str | None:
        settings = self.settings
        if settings.pg_use_iam_auth:
            return self.session.client("rds").generate_db_auth_token(
                DBHostname=settings.pg_host,
                Port=settings.pg_port,
                DBUsername=settings.pg_user,
                Region=settings.aws_region,
            )
        return settings.pg_password

    def _connect(self) -> psycopg2.extensions.connection:
        settings = self.settings
        return psycopg2.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            dbname=settings.pg_database,
            user=settings.pg_user,
            password=self._password(),
            sslmode=settings.pg_sslmode,
            connect_timeout=10,
            application_name="aws-mcp-server",
            options=f"-c statement_timeout={settings.pg_statement_timeout_ms}",
        )

    def _fetch(
        self,
        sql: str,
        params: tuple | None = None,
        max_rows: int | None = None,
    ) -> dict:
        """Run SQL in a read-only transaction and return a bounded result set."""
        row_limit = max_rows or self.settings.pg_max_rows
        connection = self._connect()
        try:
            connection.set_session(readonly=True, autocommit=False)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                if cursor.description is None:
                    return {
                        "columns": [],
                        "rows": [],
                        "row_count": 0,
                        "truncated": False,
                    }
                rows = cursor.fetchmany(row_limit + 1)
                truncated = len(rows) > row_limit
                rows = rows[:row_limit]
                return jsonable(
                    {
                        "columns": [column.name for column in cursor.description],
                        "rows": [dict(row) for row in rows],
                        "row_count": len(rows),
                        "truncated": truncated,
                    }
                )
        finally:
            connection.rollback()
            connection.close()

    async def pg_list_schemas(self) -> list[str]:
        """List user schemas in the connected PostgreSQL database."""
        result = await self._run(
            self._fetch,
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog','information_schema') "
            "AND schema_name NOT LIKE 'pg_toast%%' ORDER BY schema_name",
        )
        return [row["schema_name"] for row in result["rows"]]

    async def pg_list_tables(self, schema: str = "public") -> list[dict]:
        """List tables and views in a schema with approximate row counts."""
        result = await self._run(
            self._fetch,
            "SELECT t.table_name, t.table_type, c.reltuples::bigint AS approx_rows "
            "FROM information_schema.tables t "
            "LEFT JOIN pg_class c ON c.relname = t.table_name "
            "AND c.relnamespace = (SELECT oid FROM pg_namespace "
            "WHERE nspname = t.table_schema) "
            "WHERE t.table_schema = %s ORDER BY t.table_name",
            (schema,),
        )
        return result["rows"]

    async def pg_describe_table(self, table: str, schema: str = "public") -> dict:
        """Describe a table's columns, primary key, and indexes."""
        columns = await self._run(
            self._fetch,
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table),
        )
        if not columns["rows"]:
            raise ToolError(f"Table {schema}.{table} not found.")

        primary_key = await self._run(
            self._fetch,
            "SELECT kcu.column_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "ON tc.constraint_name = kcu.constraint_name "
            "AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = 'PRIMARY KEY' "
            "AND tc.table_schema = %s AND tc.table_name = %s "
            "ORDER BY kcu.ordinal_position",
            (schema, table),
        )
        indexes = await self._run(
            self._fetch,
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = %s AND tablename = %s",
            (schema, table),
        )
        return {
            "schema": schema,
            "table": table,
            "columns": columns["rows"],
            "primary_key": [row["column_name"] for row in primary_key["rows"]],
            "indexes": indexes["rows"],
        }

    async def pg_query(self, sql: str, max_rows: int = 100) -> dict:
        """Run SQL in a read-only transaction and limit returned rows."""
        row_limit = max(1, min(max_rows, self.settings.pg_max_rows))
        return await self._run(self._fetch, sql, None, row_limit)

    async def pg_execute(self, sql: str) -> dict:
        """Run a write statement. Requires ALLOW_WRITES=true."""
        self._require_writes("pg_execute")

        def execute() -> dict:
            connection = self._connect()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    affected_rows = cursor.rowcount
                connection.commit()
                return {"status": "committed", "rows_affected": affected_rows}
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        return await self._run(execute)