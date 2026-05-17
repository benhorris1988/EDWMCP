"""Adapter that exposes this MCP server as plain Python callables for an
on-prem LLM runtime that does not yet speak MCP directly (e.g. an
Ollama/llama.cpp setup wired up from the Kinetica project).

Run `edwmcp --transport streamable-http` somewhere reachable by the LLM host,
then import `tools()` here and feed the resulting list into your tool-use
loop. Each entry has `.name`, `.description`, `.input_schema`, and `.invoke()`.

This is a thin shim — drop or replace it once the Kinetica side has a real
MCP client.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@dataclass
class ToolHandle:
    name: str
    description: str
    input_schema: dict[str, Any]
    _session: ClientSession

    async def invoke(self, **arguments: Any) -> Any:
        result = await self._session.call_tool(self.name, arguments=arguments)
        return [c.model_dump() for c in result.content]


async def tools(url: str = "http://localhost:8765/mcp") -> list[ToolHandle]:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            return [
                ToolHandle(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema,
                    _session=session,
                )
                for t in listed.tools
            ]


if __name__ == "__main__":
    async def _demo() -> None:
        handles = await tools()
        for t in handles:
            print(f"- {t.name}: {t.description.splitlines()[0] if t.description else ''}")

    asyncio.run(_demo())
