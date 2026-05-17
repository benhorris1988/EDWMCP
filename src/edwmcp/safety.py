"""SQL safety guards for LLM-driven queries against the EDW.

The badminton skill never accepts free-form SQL from the model — it composes
parameterised statements internally. This module is for the generic EDW skill,
which deliberately exposes a `run_query` tool so the LLM can explore data.
"""

from __future__ import annotations

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DML, Keyword

FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
    "ATTACH", "DETACH", "VACUUM", "ANALYZE", "REINDEX",
    "COPY", "BULK", "BACKUP", "RESTORE",
}


class UnsafeQueryError(ValueError):
    pass


def assert_select_only(sql: str) -> None:
    """Raise UnsafeQueryError unless `sql` is a single SELECT (or WITH ... SELECT) statement."""
    if not sql or not sql.strip():
        raise UnsafeQueryError("Empty query.")

    statements: list[Statement] = sqlparse.parse(sql)
    non_empty = [s for s in statements if s.tokens and str(s).strip()]
    if len(non_empty) != 1:
        raise UnsafeQueryError("Only a single statement is allowed per query.")

    stmt = non_empty[0]
    first_token = next(
        (t for t in stmt.flatten() if not t.is_whitespace and t.ttype not in (sqlparse.tokens.Comment,)),
        None,
    )
    if first_token is None:
        raise UnsafeQueryError("No executable tokens found.")

    head = first_token.normalized.upper()
    if head not in {"SELECT", "WITH"}:
        raise UnsafeQueryError(f"Only SELECT/WITH queries are allowed; got '{head}'.")

    for token in stmt.flatten():
        if token.ttype in (DML, Keyword) and token.normalized.upper() in FORBIDDEN_KEYWORDS:
            raise UnsafeQueryError(f"Forbidden keyword in query: {token.normalized}")

    if ";" in sql.strip().rstrip(";"):
        raise UnsafeQueryError("Multiple statements (semicolons) are not allowed.")
