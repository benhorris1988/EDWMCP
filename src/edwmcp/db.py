from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import Engine, MetaData, create_engine, inspect, text
from sqlalchemy.engine import Row

from .config import Settings
from .safety import assert_select_only


@dataclass
class Engines:
    edw: Engine | None
    badminton: Engine | None


def build_engines(settings: Settings) -> Engines:
    if settings.demo:
        from .demo_data import build_demo_engine

        shared = build_demo_engine()
        return Engines(edw=shared, badminton=shared)

    edw = create_engine(settings.edw_url, pool_pre_ping=True) if settings.edw_url else None
    badminton = (
        create_engine(settings.badminton_url, pool_pre_ping=True)
        if settings.badminton_url
        else None
    )
    return Engines(edw=edw, badminton=badminton)


def list_schemas(engine: Engine) -> list[str]:
    insp = inspect(engine)
    try:
        return sorted(insp.get_schema_names())
    except NotImplementedError:
        return []


def list_tables(engine: Engine, schema: str | None = None) -> list[dict[str, str]]:
    insp = inspect(engine)
    tables = insp.get_table_names(schema=schema)
    views = insp.get_view_names(schema=schema)
    return (
        [{"schema": schema or "", "name": t, "kind": "table"} for t in tables]
        + [{"schema": schema or "", "name": v, "kind": "view"} for v in views]
    )


def describe_table(engine: Engine, name: str, schema: str | None = None) -> dict[str, Any]:
    insp = inspect(engine)
    cols = insp.get_columns(name, schema=schema)
    pk = insp.get_pk_constraint(name, schema=schema) or {}
    fks = insp.get_foreign_keys(name, schema=schema) or []
    return {
        "schema": schema or "",
        "name": name,
        "columns": [
            {
                "name": c["name"],
                "type": str(c["type"]),
                "nullable": bool(c.get("nullable", True)),
                "default": str(c.get("default")) if c.get("default") is not None else None,
            }
            for c in cols
        ],
        "primary_key": pk.get("constrained_columns", []),
        "foreign_keys": [
            {
                "columns": fk.get("constrained_columns", []),
                "references": {
                    "schema": fk.get("referred_schema") or "",
                    "table": fk.get("referred_table"),
                    "columns": fk.get("referred_columns", []),
                },
            }
            for fk in fks
        ],
    }


def _rows_to_dicts(cols: list[str], rows: Iterable[Row]) -> list[dict[str, Any]]:
    return [{c: _jsonable(r[i]) for i, c in enumerate(cols)} for r in rows]


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def run_select(
    engine: Engine,
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    max_rows: int,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    assert_select_only(sql)
    with engine.connect() as conn:
        if timeout_seconds and engine.dialect.name == "postgresql":
            conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_seconds) * 1000}"))
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        rows: list[Row] = []
        truncated = False
        for r in result:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append(r)
    return {
        "columns": cols,
        "rows": _rows_to_dicts(cols, rows),
        "row_count": len(rows),
        "truncated": truncated,
    }


def run_internal(
    engine: Engine,
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    max_rows: int = 1000,
) -> dict[str, Any]:
    """Execute trusted SELECT composed by a skill (not by the LLM). Skips safety guards."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        rows = result.fetchmany(max_rows)
    return {"columns": cols, "rows": _rows_to_dicts(cols, rows), "row_count": len(rows)}


def execute_internal(engine: Engine, sql: str, params: dict[str, Any] | None = None) -> int:
    """Execute a trusted mutating statement composed by a skill (e.g. start_game)."""
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        return result.rowcount or 0


def reflect_metadata(engine: Engine, schema: str | None = None) -> MetaData:
    md = MetaData(schema=schema)
    md.reflect(bind=engine)
    return md
