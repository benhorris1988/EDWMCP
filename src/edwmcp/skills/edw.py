"""Generic Enterprise Data Warehouse skill.

Exposes catalog introspection plus a guarded `run_query` so the LLM can explore
data on its own. All mutating operations are out of scope here — destructive
keywords are rejected by `safety.assert_select_only`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine

from .. import db
from ..config import EdwSkill, Settings
from ..safety import UnsafeQueryError


def register(mcp, engine: Engine | None, skill: EdwSkill, settings: Settings) -> None:
    if not skill.enabled:
        return

    def _require_engine() -> Engine:
        if engine is None:
            raise RuntimeError(
                "EDW engine is not configured. Set EDWMCP_EDW_URL or run with EDWMCP_DEMO=1."
            )
        return engine

    def _check_schema(schema: str | None) -> None:
        if schema and skill.allowed_schemas and schema not in skill.allowed_schemas:
            raise PermissionError(
                f"Schema '{schema}' is not in the allow-list: {skill.allowed_schemas}"
            )

    @mcp.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False, "title": "List EDW schemas"},
    )
    def edw_list_schemas() -> list[str]:
        """List schemas visible to the EDW connection user."""
        schemas = db.list_schemas(_require_engine())
        if skill.allowed_schemas:
            return [s for s in schemas if s in skill.allowed_schemas]
        return schemas

    @mcp.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False, "title": "List EDW tables"},
    )
    def edw_list_tables(schema: str | None = None) -> list[dict[str, str]]:
        """List tables and views in the EDW, optionally scoped to a single schema."""
        _check_schema(schema)
        return db.list_tables(_require_engine(), schema=schema)

    @mcp.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False, "title": "Describe EDW table"},
    )
    def edw_describe_table(name: str, schema: str | None = None) -> dict[str, Any]:
        """Return columns, primary key, and foreign keys for a single table or view."""
        _check_schema(schema)
        return db.describe_table(_require_engine(), name=name, schema=schema)

    @mcp.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False, "title": "Sample EDW rows"},
    )
    def edw_sample_rows(name: str, schema: str | None = None, limit: int = 10) -> dict[str, Any]:
        """Return up to `limit` sample rows from a table (capped by server max_rows)."""
        _check_schema(schema)
        eng = _require_engine()
        ref = f"{schema}.{name}" if schema else name
        cap = min(limit, skill.max_rows, settings.query_max_rows)
        return db.run_internal(eng, f"SELECT * FROM {ref}", max_rows=cap)

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": False,
            "destructiveHint": False,
            "title": "Run a SELECT query on the EDW",
        },
    )
    def edw_run_query(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a single SELECT (or WITH ... SELECT) statement.

        Mutating statements (INSERT/UPDATE/DELETE/DDL etc.) are rejected. Results
        are capped at the server `max_rows` setting; `truncated=true` in the
        response indicates more rows existed than were returned.
        """
        eng = _require_engine()
        cap = min(skill.max_rows, settings.query_max_rows)
        try:
            return db.run_select(
                eng,
                sql,
                params=params,
                max_rows=cap,
                timeout_seconds=settings.query_timeout_seconds,
            )
        except UnsafeQueryError as e:
            return {"error": str(e), "columns": [], "rows": [], "row_count": 0, "truncated": False}
