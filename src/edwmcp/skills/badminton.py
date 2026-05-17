"""Badminton skill — opinionated tools over the on-prem MS SQL Server DB.

All SQL is composed from the table/column mapping in `BadmintonSkill`. Identifier
names from config are validated to a strict charset so the mapping cannot smuggle
SQL fragments through. User-supplied values are always passed as parameters.
"""

from __future__ import annotations

import itertools
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine

from .. import db
from ..config import BadmintonSkill

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid identifier in config: {name!r}")
    return name


def register(mcp, engine: Engine | None, skill: BadmintonSkill) -> None:
    if not skill.enabled:
        return

    p = skill.columns.players
    c = skill.columns.courts
    g = skill.columns.games
    gp = skill.columns.game_players
    q = skill.columns.queue

    # Validate everything up-front so a misconfigured identifier fails loudly
    # at startup rather than the first time a tool is called.
    for v in [
        skill.tables.players, skill.tables.courts, skill.tables.games,
        skill.tables.game_players, skill.tables.queue,
        p.id, p.name, p.skill or "x", p.active or "x", p.joined_at or "x",
        c.id, c.name, c.available or "x",
        g.id, g.court_id, g.started_at, g.ended_at or "x", g.status, g.winning_team or "x",
        gp.game_id, gp.player_id, gp.team,
        q.player_id, q.joined_at,
    ]:
        _ident(v)

    T_PLAYERS = skill.qualified("players")
    T_COURTS = skill.qualified("courts")
    T_GAMES = skill.qualified("games")
    T_GAME_PLAYERS = skill.qualified("game_players")
    T_QUEUE = skill.qualified("queue")

    def _require_engine() -> Engine:
        if engine is None:
            raise RuntimeError(
                "Badminton engine is not configured. Set EDWMCP_BADMINTON_URL or run with EDWMCP_DEMO=1."
            )
        return engine

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": False,
            "title": "List badminton players",
        },
    )
    def badminton_list_players(active_only: bool = True) -> list[dict[str, Any]]:
        """List players known to the badminton database."""
        where = f"WHERE {p.active} = 1" if active_only and p.active else ""
        sql = f"""
            SELECT {p.id} AS id, {p.name} AS name,
                   {p.skill or 'NULL'} AS skill,
                   {p.active or '1'} AS active
              FROM {T_PLAYERS}
              {where}
             ORDER BY {p.name}
        """
        return db.run_internal(_require_engine(), sql)["rows"]

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": False,
            "title": "List courts",
        },
    )
    def badminton_list_courts(available_only: bool = False) -> list[dict[str, Any]]:
        """List courts and their availability."""
        where = f"WHERE {c.available} = 1" if available_only and c.available else ""
        sql = f"""
            SELECT {c.id} AS id, {c.name} AS name,
                   {c.available or '1'} AS available
              FROM {T_COURTS} {where}
             ORDER BY {c.name}
        """
        return db.run_internal(_require_engine(), sql)["rows"]

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": False,
            "title": "List active games",
        },
    )
    def badminton_list_active_games() -> list[dict[str, Any]]:
        """Return games currently in progress, including the players on each team."""
        eng = _require_engine()
        games_sql = f"""
            SELECT {g.id} AS id, {g.court_id} AS court_id,
                   {g.started_at} AS started_at, {g.status} AS status
              FROM {T_GAMES}
             WHERE {g.status} = :s
             ORDER BY {g.started_at}
        """
        games = db.run_internal(eng, games_sql, {"s": "in_progress"})["rows"]
        if not games:
            return []

        gp_sql = f"""
            SELECT gp.{gp.game_id} AS game_id,
                   gp.{gp.player_id} AS player_id,
                   gp.{gp.team} AS team,
                   pl.{p.name} AS player_name
              FROM {T_GAME_PLAYERS} gp
              JOIN {T_PLAYERS} pl ON pl.{p.id} = gp.{gp.player_id}
             WHERE gp.{gp.game_id} IN ({",".join(str(int(row["id"])) for row in games)})
        """
        rosters = db.run_internal(eng, gp_sql)["rows"]
        by_game: dict[int, dict[int, list[dict[str, Any]]]] = {}
        for r in rosters:
            by_game.setdefault(int(r["game_id"]), {}).setdefault(int(r["team"]), []).append(
                {"player_id": r["player_id"], "name": r["player_name"]}
            )
        for game in games:
            game["teams"] = by_game.get(int(game["id"]), {})
        return games

    @mcp.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False, "title": "Get the player queue"},
    )
    def badminton_get_queue() -> list[dict[str, Any]]:
        """Return players currently waiting for a game, longest-waiting first."""
        sql = f"""
            SELECT pl.{p.id} AS player_id, pl.{p.name} AS name,
                   {('pl.' + p.skill) if p.skill else 'NULL'} AS skill,
                   q.{q.joined_at} AS joined_at
              FROM {T_QUEUE} q
              JOIN {T_PLAYERS} pl ON pl.{p.id} = q.{q.player_id}
             ORDER BY q.{q.joined_at} ASC
        """
        return db.run_internal(_require_engine(), sql)["rows"]

    @mcp.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False, "title": "Get player stats"},
    )
    def badminton_get_player_stats(player_id: int) -> dict[str, Any]:
        """Return total games played, wins, and last game time for a single player."""
        eng = _require_engine()
        base = db.run_internal(
            eng,
            f"SELECT {p.id} AS id, {p.name} AS name FROM {T_PLAYERS} WHERE {p.id} = :pid",
            {"pid": player_id},
        )["rows"]
        if not base:
            return {"error": f"No player with id {player_id}"}

        counts_sql = f"""
            SELECT COUNT(*) AS games_played,
                   SUM(CASE WHEN g.{g.winning_team or g.id} = gp.{gp.team} THEN 1 ELSE 0 END) AS wins,
                   MAX(g.{g.started_at}) AS last_game_at
              FROM {T_GAME_PLAYERS} gp
              JOIN {T_GAMES} g ON g.{g.id} = gp.{gp.game_id}
             WHERE gp.{gp.player_id} = :pid
        """
        counts = db.run_internal(eng, counts_sql, {"pid": player_id})["rows"]
        out = base[0]
        out.update(counts[0] if counts else {})
        return out

    @mcp.tool(
        annotations={
            "readOnlyHint": True,
            "openWorldHint": False,
            "title": "Suggest next players for a game",
        },
    )
    def badminton_suggest_next_players(
        court_id: int | None = None,
        count: int | None = None,
    ) -> dict[str, Any]:
        """Pick the next group of players from the queue and propose a team split.

        Honours the rotation strategy (`queue_order` or `balanced_skill`) and
        `rest_minutes` setting from the skill config. The returned `players`
        and `teams` are suggestions only — call `badminton_start_game` to
        actually start the match after the user confirms.
        """
        eng = _require_engine()
        n = count or skill.rotation.players_per_game

        rest_cutoff_sql = f"""
            SELECT gp.{gp.player_id} AS player_id, MAX(g.{g.started_at}) AS last_game_at
              FROM {T_GAME_PLAYERS} gp
              JOIN {T_GAMES} g ON g.{g.id} = gp.{gp.game_id}
          GROUP BY gp.{gp.player_id}
        """
        last_games = {
            int(r["player_id"]): r["last_game_at"]
            for r in db.run_internal(eng, rest_cutoff_sql)["rows"]
        }

        queue_sql = f"""
            SELECT pl.{p.id} AS player_id, pl.{p.name} AS name,
                   {('pl.' + p.skill) if p.skill else 'NULL'} AS skill,
                   q.{q.joined_at} AS joined_at
              FROM {T_QUEUE} q
              JOIN {T_PLAYERS} pl ON pl.{p.id} = q.{q.player_id}
             WHERE {('pl.' + p.active + ' = 1') if p.active else '1=1'}
             ORDER BY q.{q.joined_at} ASC
        """
        candidates = db.run_internal(eng, queue_sql)["rows"]

        rest = skill.rotation.rest_minutes
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        kept: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for row in candidates:
            last = last_games.get(int(row["player_id"]))
            if last and rest > 0:
                try:
                    last_dt = datetime.fromisoformat(str(last).replace("Z", ""))
                    minutes_since = (now - last_dt).total_seconds() / 60
                    if minutes_since < rest:
                        skipped.append({**row, "reason": f"resting ({minutes_since:.1f} min < {rest})"})
                        continue
                except ValueError:
                    pass
            kept.append(row)

        if len(kept) < n:
            return {
                "ok": False,
                "reason": f"Not enough rested players in the queue (have {len(kept)}, need {n}).",
                "queue_size": len(candidates),
                "skipped_for_rest": skipped,
            }

        chosen = kept[:n]

        if skill.rotation.strategy == "balanced_skill" and n == 4 and all(
            r.get("skill") is not None for r in chosen
        ):
            best_split = None
            best_diff = None
            for combo in itertools.combinations(range(4), 2):
                team1 = [chosen[i] for i in combo]
                team2 = [chosen[i] for i in range(4) if i not in combo]
                diff = abs(sum(r["skill"] for r in team1) - sum(r["skill"] for r in team2))
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_split = (team1, team2)
            teams = {1: best_split[0], 2: best_split[1]}
            rationale = (
                f"Picked the {n} longest-waiting rested players. Teams chosen to balance skill "
                f"(skill-rating difference {best_diff})."
            )
        else:
            teams = {1: chosen[: n // 2], 2: chosen[n // 2 :]}
            rationale = f"Picked the {n} longest-waiting rested players in queue order."

        court = None
        if court_id is not None:
            court_rows = db.run_internal(
                eng,
                f"SELECT {c.id} AS id, {c.name} AS name FROM {T_COURTS} WHERE {c.id} = :cid",
                {"cid": court_id},
            )["rows"]
            court = court_rows[0] if court_rows else None
        else:
            free = db.run_internal(
                eng,
                f"SELECT {c.id} AS id, {c.name} AS name FROM {T_COURTS} "
                f"WHERE {(c.available + ' = 1') if c.available else '1=1'} "
                f"ORDER BY {c.id} LIMIT 1",
            )["rows"] if engine.dialect.name == "sqlite" else db.run_internal(
                eng,
                f"SELECT TOP 1 {c.id} AS id, {c.name} AS name FROM {T_COURTS} "
                f"WHERE {(c.available + ' = 1') if c.available else '1=1'} "
                f"ORDER BY {c.id}",
            )["rows"]
            court = free[0] if free else None

        return {
            "ok": True,
            "players": chosen,
            "teams": teams,
            "court": court,
            "rationale": rationale,
            "skipped_for_rest": skipped,
        }

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
            "title": "Start a badminton game",
        },
    )
    def badminton_start_game(
        player_ids: list[int],
        court_id: int | None = None,
        team_assignments: dict[str, list[int]] | None = None,
    ) -> dict[str, Any]:
        """Create a new in-progress game.

        `team_assignments` maps team number ("1"/"2") to player IDs. If omitted,
        the first half of `player_ids` is team 1 and the rest team 2. Players are
        removed from the queue and the court is marked unavailable as part of
        the same transaction.
        """
        eng = _require_engine()

        if len(player_ids) < 2 or len(player_ids) % 2 != 0:
            return {"ok": False, "error": "player_ids must contain an even number (>=2) of IDs."}
        if len(set(player_ids)) != len(player_ids):
            return {"ok": False, "error": "player_ids contains duplicates."}

        if team_assignments:
            t1 = team_assignments.get("1", [])
            t2 = team_assignments.get("2", [])
            if sorted(t1 + t2) != sorted(player_ids) or len(t1) != len(t2):
                return {"ok": False, "error": "team_assignments must partition player_ids evenly."}
        else:
            half = len(player_ids) // 2
            t1, t2 = player_ids[:half], player_ids[half:]

        if court_id is None:
            free = db.run_internal(
                eng,
                f"SELECT {c.id} AS id FROM {T_COURTS} "
                f"WHERE {(c.available + ' = 1') if c.available else '1=1'} "
                f"ORDER BY {c.id}",
            )["rows"]
            if not free:
                return {"ok": False, "error": "No available courts."}
            court_id = int(free[0]["id"])

        now_iso = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat(sep=" ")

        with eng.begin() as conn:
            from sqlalchemy import text as _text

            result = conn.execute(
                _text(
                    f"INSERT INTO {T_GAMES} ({g.court_id}, {g.started_at}, {g.status}) "
                    f"VALUES (:cid, :ts, :st)"
                ),
                {"cid": court_id, "ts": now_iso, "st": "in_progress"},
            )
            game_id = result.lastrowid
            if game_id is None:
                # MSSQL: lastrowid isn't always populated; fall back to SCOPE_IDENTITY().
                game_id = conn.execute(_text("SELECT SCOPE_IDENTITY()")).scalar()

            conn.execute(
                _text(
                    f"INSERT INTO {T_GAME_PLAYERS} ({gp.game_id}, {gp.player_id}, {gp.team}) "
                    f"VALUES (:gid, :pid, :team)"
                ),
                [{"gid": game_id, "pid": pid, "team": 1} for pid in t1]
                + [{"gid": game_id, "pid": pid, "team": 2} for pid in t2],
            )
            placeholders = ",".join(f":p{i}" for i in range(len(player_ids)))
            conn.execute(
                _text(f"DELETE FROM {T_QUEUE} WHERE {q.player_id} IN ({placeholders})"),
                {f"p{i}": pid for i, pid in enumerate(player_ids)},
            )
            if c.available:
                conn.execute(
                    _text(f"UPDATE {T_COURTS} SET {c.available} = 0 WHERE {c.id} = :cid"),
                    {"cid": court_id},
                )

        return {
            "ok": True,
            "game_id": int(game_id) if game_id is not None else None,
            "court_id": court_id,
            "started_at": now_iso,
            "teams": {"1": t1, "2": t2},
        }

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
            "title": "End a badminton game",
        },
    )
    def badminton_end_game(
        game_id: int,
        winning_team: int | None = None,
        requeue_players: bool = True,
    ) -> dict[str, Any]:
        """Mark a game as finished, free its court, and optionally re-queue its players."""
        eng = _require_engine()
        now_iso = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat(sep=" ")

        from sqlalchemy import text as _text

        with eng.begin() as conn:
            row = conn.execute(
                _text(f"SELECT {g.court_id} AS cid, {g.status} AS st FROM {T_GAMES} WHERE {g.id} = :gid"),
                {"gid": game_id},
            ).first()
            if row is None:
                return {"ok": False, "error": f"No game with id {game_id}"}
            if row.st != "in_progress":
                return {"ok": False, "error": f"Game {game_id} is not in progress (status={row.st})"}

            wt_set = f", {g.winning_team} = :wt" if g.winning_team and winning_team is not None else ""
            params: dict[str, Any] = {"gid": game_id, "ts": now_iso}
            if wt_set:
                params["wt"] = winning_team

            conn.execute(
                _text(
                    f"UPDATE {T_GAMES} SET {g.status} = 'finished'"
                    f"{', ' + g.ended_at + ' = :ts' if g.ended_at else ''}"
                    f"{wt_set} WHERE {g.id} = :gid"
                ),
                params,
            )
            if c.available:
                conn.execute(
                    _text(f"UPDATE {T_COURTS} SET {c.available} = 1 WHERE {c.id} = :cid"),
                    {"cid": int(row.cid)},
                )
            if requeue_players:
                conn.execute(
                    _text(
                        f"INSERT INTO {T_QUEUE} ({q.player_id}, {q.joined_at}) "
                        f"SELECT {gp.player_id}, :ts FROM {T_GAME_PLAYERS} "
                        f"WHERE {gp.game_id} = :gid "
                        f"AND {gp.player_id} NOT IN (SELECT {q.player_id} FROM {T_QUEUE})"
                    ),
                    {"gid": game_id, "ts": now_iso},
                )

        return {"ok": True, "game_id": game_id, "ended_at": now_iso, "winning_team": winning_team}
