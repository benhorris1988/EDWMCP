from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BadmintonTables(BaseModel):
    players: str = "Players"
    courts: str = "Courts"
    games: str = "Games"
    game_players: str = "GamePlayers"
    queue: str = "PlayerQueue"


class BadmintonColumnsPlayers(BaseModel):
    id: str = "PlayerId"
    name: str = "Name"
    skill: str | None = "SkillRating"
    active: str | None = "IsActive"
    joined_at: str | None = "JoinedAt"


class BadmintonColumnsCourts(BaseModel):
    id: str = "CourtId"
    name: str = "Name"
    available: str | None = "IsAvailable"


class BadmintonColumnsGames(BaseModel):
    id: str = "GameId"
    court_id: str = "CourtId"
    started_at: str = "StartedAt"
    ended_at: str | None = "EndedAt"
    status: str = "Status"
    winning_team: str | None = "WinningTeam"


class BadmintonColumnsGamePlayers(BaseModel):
    game_id: str = "GameId"
    player_id: str = "PlayerId"
    team: str = "Team"


class BadmintonColumnsQueue(BaseModel):
    player_id: str = "PlayerId"
    joined_at: str = "JoinedAt"


class BadmintonColumns(BaseModel):
    players: BadmintonColumnsPlayers = Field(default_factory=BadmintonColumnsPlayers)
    courts: BadmintonColumnsCourts = Field(default_factory=BadmintonColumnsCourts)
    games: BadmintonColumnsGames = Field(default_factory=BadmintonColumnsGames)
    game_players: BadmintonColumnsGamePlayers = Field(default_factory=BadmintonColumnsGamePlayers)
    queue: BadmintonColumnsQueue = Field(default_factory=BadmintonColumnsQueue)


class BadmintonRotation(BaseModel):
    players_per_game: int = 4
    strategy: Literal["queue_order", "balanced_skill"] = "balanced_skill"
    rest_minutes: int = 2


class BadmintonSkill(BaseModel):
    enabled: bool = True
    schema_: str | None = Field(default="dbo", alias="schema")
    tables: BadmintonTables = Field(default_factory=BadmintonTables)
    columns: BadmintonColumns = Field(default_factory=BadmintonColumns)
    rotation: BadmintonRotation = Field(default_factory=BadmintonRotation)

    model_config = {"populate_by_name": True}

    def qualified(self, table_key: str) -> str:
        table = getattr(self.tables, table_key)
        return f"{self.schema_}.{table}" if self.schema_ else table


class EdwSkill(BaseModel):
    enabled: bool = True
    allowed_schemas: list[str] = Field(default_factory=list)
    max_rows: int = 500


class SkillsConfig(BaseModel):
    badminton: BadmintonSkill = Field(default_factory=BadmintonSkill)
    edw: EdwSkill = Field(default_factory=EdwSkill)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EDWMCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    transport: Literal["stdio", "streamable-http", "sse"] = "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8765

    config: str = "./config.example.yaml"
    edw_url: str | None = None
    badminton_url: str | None = None

    query_max_rows: int = 500
    query_timeout_seconds: int = 30
    demo: bool = False

    admin_token: str | None = None
    admin_insecure: bool = False
    admin_host: str = "127.0.0.1"
    admin_port: int = 8766
    admin_cors_origins: str = "*"


def load_skills_config(path: str | Path) -> SkillsConfig:
    p = Path(path)
    if not p.exists():
        return SkillsConfig()
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return SkillsConfig.model_validate(raw)
