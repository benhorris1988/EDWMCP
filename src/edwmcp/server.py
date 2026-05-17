from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from .config import Settings, load_skills_config
from .db import Engines, build_engines
from .skills import badminton as badminton_skill
from .skills import edw as edw_skill

logger = logging.getLogger("edwmcp")


def build_server(settings: Settings | None = None) -> tuple[FastMCP, Engines]:
    settings = settings or Settings()
    skills = load_skills_config(settings.config)

    if settings.demo and skills.badminton.schema_ == "dbo":
        # SQLite has no schemas; the demo engine seeds tables in the default namespace.
        skills.badminton.schema_ = None

    engines = build_engines(settings)
    mcp = FastMCP(
        "edwmcp",
        instructions=(
            "MCP server for an on-prem Enterprise Data Warehouse and a MS SQL Server "
            "badminton database. Use the `edw_*` tools to explore arbitrary warehouse "
            "tables and run safe SELECTs. Use the `badminton_*` tools to read the "
            "club's players/queue/games and (after the user confirms) start or end games."
        ),
    )

    edw_skill.register(mcp, engines.edw, skills.edw, settings)
    badminton_skill.register(mcp, engines.badminton, skills.badminton)

    return mcp, engines
