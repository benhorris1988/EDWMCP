"""End-to-end smoke tests against the seeded SQLite demo DB."""

from __future__ import annotations

from edwmcp.config import Settings
from edwmcp.server import build_server


def _settings() -> Settings:
    return Settings(
        demo=True,
        config="./config.example.yaml",
        transport="stdio",
    )


def _call(mcp, name, **kwargs):
    """FastMCP stores tools on its internal manager; call them directly for tests."""
    tool = mcp._tool_manager.get_tool(name)  # type: ignore[attr-defined]
    return tool.fn(**kwargs)


def test_list_players():
    mcp, _ = build_server(_settings())
    players = _call(mcp, "badminton_list_players", active_only=True)
    assert len(players) == 8
    assert {p["name"] for p in players} >= {"Alice", "Bob", "Charlie"}


def test_get_queue_orders_by_join_time():
    mcp, _ = build_server(_settings())
    queue = _call(mcp, "badminton_get_queue")
    assert [r["name"] for r in queue][:3] == ["Bob", "Ethan", "George"]


def test_suggest_next_players_returns_four_with_balanced_teams():
    mcp, _ = build_server(_settings())
    out = _call(mcp, "badminton_suggest_next_players")
    assert out["ok"] is True
    assert len(out["players"]) == 4
    assert sorted(out["teams"].keys()) == [1, 2]
    assert len(out["teams"][1]) == 2 and len(out["teams"][2]) == 2


def test_start_and_end_game_round_trip():
    mcp, engines = build_server(_settings())
    suggestion = _call(mcp, "badminton_suggest_next_players")
    pids = [int(p["player_id"]) for p in suggestion["players"]]

    started = _call(mcp, "badminton_start_game", player_ids=pids)
    assert started["ok"] is True
    game_id = started["game_id"]

    active = _call(mcp, "badminton_list_active_games")
    assert any(int(g["id"]) == game_id for g in active)

    queue_after = _call(mcp, "badminton_get_queue")
    assert not (set(pids) & {int(r["player_id"]) for r in queue_after})

    ended = _call(mcp, "badminton_end_game", game_id=game_id, winning_team=1)
    assert ended["ok"] is True

    active_after = _call(mcp, "badminton_list_active_games")
    assert not any(int(g["id"]) == game_id for g in active_after)


def test_edw_list_tables_and_safe_query():
    mcp, _ = build_server(_settings())
    tables = _call(mcp, "edw_list_tables")
    names = {t["name"] for t in tables}
    assert "sales_fact" in names

    res = _call(
        mcp,
        "edw_run_query",
        sql="SELECT region, SUM(revenue) AS rev FROM sales_fact GROUP BY region ORDER BY rev DESC",
    )
    assert res["row_count"] == 3
    assert {row["region"] for row in res["rows"]} == {"EMEA", "AMER", "APAC"}


def test_edw_run_query_blocks_mutation():
    mcp, _ = build_server(_settings())
    res = _call(mcp, "edw_run_query", sql="DELETE FROM sales_fact")
    assert "error" in res
