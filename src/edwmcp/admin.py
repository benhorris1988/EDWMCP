"""Admin REST API for the EDW + badminton MCP server.

Drives the Flutter Web config app under ../admin_ui. Reads & writes the YAML
skill config and the .env settings file, tests live DB connections, and lists
the MCP tool catalogue that would be registered for the current config.

Auth: a single bearer token sourced from EDWMCP_ADMIN_TOKEN. Set
EDWMCP_ADMIN_INSECURE=1 to skip auth for local development on loopback.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import set_key
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from . import __version__
from .config import Settings, SkillsConfig, load_skills_config
from .server import build_server


_REDACTED = "***"


def _redact_url(url: str | None) -> str | None:
    if not url:
        return url
    try:
        u = make_url(url)
        if u.password:
            u = u.set(password=_REDACTED)
        return str(u)
    except Exception:
        return url


def _is_redacted(url: str | None) -> bool:
    return bool(url) and _REDACTED in (url or "")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    demo: bool
    transport: str
    config_path: str
    badminton_configured: bool
    edw_configured: bool


class SettingsView(BaseModel):
    transport: str
    http_host: str
    http_port: int
    config: str
    edw_url: str | None
    badminton_url: str | None
    query_max_rows: int
    query_timeout_seconds: int
    demo: bool


class SettingsUpdate(BaseModel):
    edw_url: str | None = None
    badminton_url: str | None = None
    query_max_rows: int | None = None
    query_timeout_seconds: int | None = None
    transport: str | None = None
    http_host: str | None = None
    http_port: int | None = None


class ConnectionTestRequest(BaseModel):
    url: str
    timeout_seconds: int = 5


class ConnectionTestResponse(BaseModel):
    ok: bool
    dialect: str | None = None
    server_version: str | None = None
    error: str | None = None


class ToolInfo(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]


def _ensure_writable_config_path(settings: Settings) -> Path:
    p = Path(settings.config).resolve()
    if p.name == "config.example.yaml":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Refusing to overwrite config.example.yaml (it's the template). "
                "Copy it to config.yaml, point EDWMCP_CONFIG at the copy, then retry."
            ),
        )
    return p


def _env_file_path() -> Path:
    return (Path.cwd() / ".env").resolve()


def _build_auth_dep(settings: Settings):
    expected = settings.admin_token

    async def _auth(authorization: str | None = Header(default=None)) -> None:
        if settings.admin_insecure:
            return
        if not expected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin API has no token configured (set EDWMCP_ADMIN_TOKEN).",
            )
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
        provided = authorization.split(" ", 1)[1].strip()
        if not secrets.compare_digest(provided, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    return _auth


def create_admin_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    app = FastAPI(
        title="edwmcp admin API",
        version=__version__,
        description="Configuration plane for the EDW + badminton MCP server.",
    )

    origins = [o.strip() for o in settings.admin_cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    auth = Depends(_build_auth_dep(settings))

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        s = Settings()
        return HealthResponse(
            version=__version__,
            demo=s.demo,
            transport=s.transport,
            config_path=str(Path(s.config).resolve()),
            badminton_configured=bool(s.badminton_url) or s.demo,
            edw_configured=bool(s.edw_url) or s.demo,
        )

    @app.get("/api/settings", response_model=SettingsView, dependencies=[auth])
    def get_settings() -> SettingsView:
        s = Settings()
        return SettingsView(
            transport=s.transport,
            http_host=s.http_host,
            http_port=s.http_port,
            config=s.config,
            edw_url=_redact_url(s.edw_url),
            badminton_url=_redact_url(s.badminton_url),
            query_max_rows=s.query_max_rows,
            query_timeout_seconds=s.query_timeout_seconds,
            demo=s.demo,
        )

    @app.put("/api/settings", response_model=SettingsView, dependencies=[auth])
    def put_settings(update: SettingsUpdate) -> SettingsView:
        env_path = _env_file_path()
        env_path.touch(exist_ok=True)

        kv: dict[str, str] = {}
        if update.edw_url is not None and not _is_redacted(update.edw_url):
            kv["EDWMCP_EDW_URL"] = update.edw_url
        if update.badminton_url is not None and not _is_redacted(update.badminton_url):
            kv["EDWMCP_BADMINTON_URL"] = update.badminton_url
        if update.query_max_rows is not None:
            kv["EDWMCP_QUERY_MAX_ROWS"] = str(update.query_max_rows)
        if update.query_timeout_seconds is not None:
            kv["EDWMCP_QUERY_TIMEOUT_SECONDS"] = str(update.query_timeout_seconds)
        if update.transport is not None:
            kv["EDWMCP_TRANSPORT"] = update.transport
        if update.http_host is not None:
            kv["EDWMCP_HTTP_HOST"] = update.http_host
        if update.http_port is not None:
            kv["EDWMCP_HTTP_PORT"] = str(update.http_port)

        for k, v in kv.items():
            set_key(str(env_path), k, v, quote_mode="never")

        return get_settings()

    @app.get("/api/skills", response_model=SkillsConfig, dependencies=[auth])
    def get_skills() -> SkillsConfig:
        return load_skills_config(Settings().config)

    @app.put("/api/skills", response_model=SkillsConfig, dependencies=[auth])
    def put_skills(skills: SkillsConfig) -> SkillsConfig:
        s = Settings()
        path = _ensure_writable_config_path(s)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(
                skills.model_dump(by_alias=True),
                fh,
                sort_keys=False,
                default_flow_style=False,
            )
        return load_skills_config(s.config)

    @app.post("/api/connections/test", response_model=ConnectionTestResponse, dependencies=[auth])
    def test_connection(req: ConnectionTestRequest) -> ConnectionTestResponse:
        if _is_redacted(req.url):
            return ConnectionTestResponse(
                ok=False,
                error="URL is redacted (***). Re-enter the full connection string with password.",
            )
        try:
            engine = create_engine(req.url, pool_pre_ping=True)
            try:
                with engine.connect() as conn:
                    version_row = conn.execute(text("SELECT 1")).scalar()
                    if version_row != 1:
                        return ConnectionTestResponse(ok=False, error="SELECT 1 did not return 1.")
                    server_version = None
                    try:
                        server_version = str(conn.exec_driver_sql("SELECT @@VERSION").scalar())
                    except Exception:
                        try:
                            server_version = str(conn.exec_driver_sql("SELECT version()").scalar())
                        except Exception:
                            pass
                return ConnectionTestResponse(
                    ok=True,
                    dialect=engine.dialect.name,
                    server_version=server_version,
                )
            finally:
                engine.dispose()
        except Exception as e:
            return ConnectionTestResponse(ok=False, error=f"{type(e).__name__}: {e}")

    @app.get("/api/tools", response_model=list[ToolInfo], dependencies=[auth])
    def list_tools() -> list[ToolInfo]:
        mcp, engines = build_server(Settings())
        try:
            tools = []
            manager = mcp._tool_manager  # type: ignore[attr-defined]
            for name, tool in manager._tools.items():  # type: ignore[attr-defined]
                ann = getattr(tool, "annotations", None)
                if ann is None:
                    ann_dict: dict[str, Any] = {}
                elif hasattr(ann, "model_dump"):
                    ann_dict = ann.model_dump(exclude_none=True)
                elif isinstance(ann, dict):
                    ann_dict = ann
                else:
                    ann_dict = dict(ann)
                tools.append(
                    ToolInfo(
                        name=name,
                        description=(tool.description or "").strip(),
                        input_schema=getattr(tool, "parameters", {}) or {},
                        annotations=ann_dict,
                    )
                )
            return tools
        finally:
            for eng in {engines.edw, engines.badminton}:
                if eng is not None:
                    eng.dispose()

    return app


def run() -> None:
    import uvicorn

    settings = Settings()
    if not settings.admin_token and not settings.admin_insecure:
        raise SystemExit(
            "Refusing to start admin API without auth. "
            "Set EDWMCP_ADMIN_TOKEN, or EDWMCP_ADMIN_INSECURE=1 for loopback dev only."
        )

    uvicorn.run(
        "edwmcp.admin:create_admin_app",
        factory=True,
        host=settings.admin_host,
        port=settings.admin_port,
        log_level="info",
    )
