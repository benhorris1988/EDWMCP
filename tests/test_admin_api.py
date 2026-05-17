"""Tests for the admin REST API used by the Flutter config app."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edwmcp.admin import create_admin_app
from edwmcp.config import Settings


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    shutil.copy("config.example.yaml", cfg)
    env = tmp_path / ".env"
    env.write_text("EDWMCP_DEMO=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EDWMCP_CONFIG", str(cfg))
    monkeypatch.setenv("EDWMCP_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("EDWMCP_ADMIN_INSECURE", "0")
    monkeypatch.setenv("EDWMCP_DEMO", "1")
    monkeypatch.delenv("EDWMCP_BADMINTON_URL", raising=False)
    monkeypatch.delenv("EDWMCP_EDW_URL", raising=False)
    return tmp_path


@pytest.fixture
def client(workspace):
    app = create_admin_app(Settings())
    return TestClient(app)


def _auth(token: str = "test-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_unauthenticated(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["demo"] is True


def test_settings_requires_auth(client):
    assert client.get("/api/settings").status_code == 401


def test_settings_rejects_bad_token(client):
    r = client.get("/api/settings", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_get_skills_returns_default_mapping(client):
    r = client.get("/api/skills", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["badminton"]["tables"]["players"] == "Players"
    assert body["edw"]["max_rows"] == 500


def test_put_skills_persists_and_round_trips(client, workspace):
    r = client.get("/api/skills", headers=_auth())
    skills = r.json()
    skills["badminton"]["rotation"]["rest_minutes"] = 5
    skills["badminton"]["tables"]["players"] = "Members"

    r = client.put("/api/skills", json=skills, headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json()["badminton"]["rotation"]["rest_minutes"] == 5
    assert r.json()["badminton"]["tables"]["players"] == "Members"

    # Re-read from disk via a fresh GET
    r = client.get("/api/skills", headers=_auth())
    assert r.json()["badminton"]["tables"]["players"] == "Members"


def test_put_skills_refuses_to_overwrite_example(client, workspace, monkeypatch):
    monkeypatch.setenv("EDWMCP_CONFIG", "config.example.yaml")
    Path("config.example.yaml").write_text("badminton: {}\nedw: {}\n")
    r = client.get("/api/skills", headers=_auth())
    assert r.status_code == 200
    r = client.put("/api/skills", json=r.json(), headers=_auth())
    assert r.status_code == 400
    assert "config.example.yaml" in r.json()["detail"]


def test_put_settings_writes_env_file(client, workspace):
    r = client.put(
        "/api/settings",
        json={"query_max_rows": 999, "badminton_url": "sqlite:///badminton.db"},
        headers=_auth(),
    )
    assert r.status_code == 200, r.text
    contents = (workspace / ".env").read_text()
    assert "EDWMCP_QUERY_MAX_ROWS=999" in contents
    assert "EDWMCP_BADMINTON_URL=sqlite:///badminton.db" in contents


def test_put_settings_ignores_redacted_url(client, workspace):
    (workspace / ".env").write_text(
        "EDWMCP_DEMO=1\nEDWMCP_BADMINTON_URL=sqlite:///pre-existing.db\n",
        encoding="utf-8",
    )
    r = client.put(
        "/api/settings",
        json={"badminton_url": "sqlite://user:***@host/db"},
        headers=_auth(),
    )
    assert r.status_code == 200
    contents = (workspace / ".env").read_text()
    assert "sqlite:///pre-existing.db" in contents
    assert "***" not in contents


def test_get_settings_redacts_passwords(client, workspace, monkeypatch):
    monkeypatch.setenv("EDWMCP_BADMINTON_URL", "postgresql+psycopg://user:secret@host/db")
    r = client.get("/api/settings", headers=_auth())
    body = r.json()
    assert "secret" not in (body["badminton_url"] or "")
    assert "***" in body["badminton_url"]


def test_connection_test_against_sqlite(client):
    r = client.post(
        "/api/connections/test",
        json={"url": "sqlite:///:memory:"},
        headers=_auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["dialect"] == "sqlite"


def test_connection_test_rejects_redacted(client):
    r = client.post(
        "/api/connections/test",
        json={"url": "postgresql://user:***@host/db"},
        headers=_auth(),
    )
    assert r.json() == {"ok": False, "dialect": None, "server_version": None,
                        "error": "URL is redacted (***). Re-enter the full connection string with password."}


def test_connection_test_reports_failure_cleanly(client):
    r = client.post(
        "/api/connections/test",
        json={"url": "postgresql+psycopg://user:pw@127.0.0.1:1/nope"},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error"]


def test_list_tools_returns_registered_catalogue(client):
    r = client.get("/api/tools", headers=_auth())
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert {"badminton_suggest_next_players", "badminton_start_game", "edw_run_query"} <= names


def test_insecure_mode_skips_auth(workspace, monkeypatch):
    monkeypatch.setenv("EDWMCP_ADMIN_INSECURE", "1")
    monkeypatch.delenv("EDWMCP_ADMIN_TOKEN", raising=False)
    app = create_admin_app(Settings())
    c = TestClient(app)
    assert c.get("/api/settings").status_code == 200


def test_run_refuses_without_token(workspace, monkeypatch):
    monkeypatch.delenv("EDWMCP_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("EDWMCP_ADMIN_INSECURE", "0")
    from edwmcp import admin as admin_mod
    with pytest.raises(SystemExit):
        admin_mod.run()
