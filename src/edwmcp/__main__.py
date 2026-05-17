from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import Settings
from .server import build_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edwmcp", description="EDW + Badminton MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        help="Override EDWMCP_TRANSPORT.",
    )
    parser.add_argument("--host", help="Bind host for HTTP transports (default 0.0.0.0).")
    parser.add_argument("--port", type=int, help="Bind port for HTTP transports (default 8765).")
    parser.add_argument("--config", help="Path to skills config YAML.")
    parser.add_argument("--demo", action="store_true", help="Run against a seeded in-memory SQLite DB.")
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Start the admin REST API instead of the MCP server (config plane for the Flutter UI).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.transport:
        os.environ["EDWMCP_TRANSPORT"] = args.transport
    if args.host:
        os.environ["EDWMCP_HTTP_HOST"] = args.host
    if args.port:
        os.environ["EDWMCP_HTTP_PORT"] = str(args.port)
    if args.config:
        os.environ["EDWMCP_CONFIG"] = args.config
    if args.demo:
        os.environ["EDWMCP_DEMO"] = "1"

    settings = Settings()

    if args.admin:
        from .admin import run as run_admin
        run_admin()
        return 0

    mcp, _engines = build_server(settings)

    if settings.transport == "stdio":
        mcp.run()
    else:
        mcp.settings.host = settings.http_host
        mcp.settings.port = settings.http_port
        mcp.run(transport=settings.transport)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
