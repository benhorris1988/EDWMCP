# edwmcp

An MCP server that sits over an on-prem **Enterprise Data Warehouse** and a Microsoft SQL Server **Badminton** database, and surfaces them to local LLMs (e.g. the models in the [Kinetica](https://github.com/benhorris1988/Kinetica) project) as callable tools.

The server is written in Python (the MCP SDK lands here first and the SQLAlchemy ecosystem covers more on-prem databases than Dart's). It exposes two skills:

- **`edw`** — generic warehouse introspection: list schemas, list tables, describe a table, sample rows, and run a guarded SELECT. Works against anything SQLAlchemy can talk to (SQL Server, Postgres, Teradata, Oracle, Snowflake, …).
- **`badminton`** — opinionated, schema-aware tools over the badminton DB: list players / courts / active games, view the queue, suggest the next group of players, and (after the user confirms) start / end a game.

## How the chatbot flow lines up

```
            ┌────────────────────────┐
            │  Badminton Flutter app │  ← chatbot UI lives here eventually
            └──────────┬─────────────┘
                       │  user prompt
                       ▼
            ┌────────────────────────┐
            │  Kinetica LLM (on-prem)│  ← decides which tool to call
            └──────────┬─────────────┘
                       │  MCP tool call
                       ▼
            ┌────────────────────────┐
            │       edwmcp           │  ← this repo
            └──┬─────────────────┬───┘
               │                 │
               ▼                 ▼
       MS SQL: Badminton   On-prem EDW
```

For your worked example — _"who should the next players be?"_ → _"should I start that game?"_ → _"start it"_:

1. The LLM calls `badminton_suggest_next_players`. The server reads the queue, applies the rotation rules, and returns four players plus a recommended team split with a rationale.
2. The LLM relays that to the user and asks for confirmation.
3. On "yes", the LLM calls `badminton_start_game` with the player IDs. The server creates the `Games` row, the `GamePlayers` rows, removes those players from the queue and marks the court unavailable — all in a single transaction.

`badminton_start_game` and `badminton_end_game` are flagged with MCP's `readOnlyHint: false` annotation, so a well-behaved client will surface a confirmation prompt automatically before invoking them.

## Install

```bash
git clone https://github.com/benhorris1988/edwmcp
cd edwmcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,mssql]"   # add postgres / teradata / oracle / snowflake as needed
```

The `mssql` extra pulls in `pyodbc`. You'll also need the Microsoft ODBC Driver 18 installed on the host running the MCP server.

## Try it without a real DB

```bash
EDWMCP_DEMO=1 edwmcp --transport stdio
```

This seeds an in-memory SQLite database with a small badminton club state (9 players, 3 courts, 6 in queue) and a `sales_fact` table for the EDW skill. Every tool is callable end-to-end against the seed data.

```bash
pytest      # runs unit tests + smoke tests against the demo DB
```

## Configure against the real databases

1. Copy `.env.example` to `.env` and fill in:
   - `EDWMCP_BADMINTON_URL` — SQLAlchemy URL for the SQL Server holding the Badminton schema
   - `EDWMCP_EDW_URL` — SQLAlchemy URL for the on-prem warehouse
2. Copy `config.example.yaml` and edit the `badminton.tables` / `badminton.columns` mapping to match the table and column names actually used by the [Badminton app](https://github.com/benhorris1988/Badminton). The default mapping assumes `dbo.Players`, `dbo.Courts`, `dbo.Games`, `dbo.GamePlayers`, `dbo.PlayerQueue` — adjust freely; the SQL is composed from this mapping at startup and identifier names are validated to a strict charset.
3. Optionally set `badminton.rotation.strategy` to `queue_order` (longest-waiting first, no skill weighting) or `balanced_skill` (longest-waiting first, then team split chosen to minimise the skill-rating gap).

## Run it

**stdio** (Claude Desktop, most local MCP clients, subprocess style):

```bash
edwmcp --transport stdio
```

See `examples/claude_desktop_config.json` for a ready-to-paste client entry.

**HTTP** (Kinetica / any LLM host on a different box):

```bash
edwmcp --transport streamable-http --host 0.0.0.0 --port 8765
```

`examples/kinetica_tool_proxy.py` shows how to consume the HTTP transport from a Python LLM loop that doesn't yet speak MCP natively.

## Tools

### `edw` skill

| Tool | Description |
| --- | --- |
| `edw_list_schemas` | Schemas visible to the connection user, intersected with `allowed_schemas`. |
| `edw_list_tables(schema?)` | Tables and views in the warehouse. |
| `edw_describe_table(name, schema?)` | Columns, PK, FKs. |
| `edw_sample_rows(name, schema?, limit=10)` | A few rows, capped at `max_rows`. |
| `edw_run_query(sql, params?)` | Run a single `SELECT` / `WITH … SELECT`. Rejects any mutating keyword and any multi-statement query. Results truncated to `max_rows`; bind parameters fully supported. |

### `badminton` skill

| Tool | Description | Mutating? |
| --- | --- | --- |
| `badminton_list_players(active_only=True)` | All players. | No |
| `badminton_list_courts(available_only=False)` | Courts and availability. | No |
| `badminton_list_active_games()` | In-progress games with rosters. | No |
| `badminton_get_queue()` | Players currently waiting, longest-waiting first. | No |
| `badminton_get_player_stats(player_id)` | Total games, wins, last game time. | No |
| `badminton_suggest_next_players(court_id?, count?)` | Returns chosen players, team split, court, rationale. | No |
| `badminton_start_game(player_ids, court_id?, team_assignments?)` | Creates a game, clears those players from the queue, marks the court unavailable — atomically. | **Yes** |
| `badminton_end_game(game_id, winning_team?, requeue_players=True)` | Finishes the game, frees the court, re-queues players. | **Yes** |

## Safety notes

- `edw_run_query` parses every statement with `sqlparse` and rejects anything that isn't a single `SELECT` / `WITH … SELECT`. Forbidden keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, `MERGE`, `EXEC`, `GRANT`, …) abort the query whether they appear at the top level or nested.
- All EDW results are capped at `max_rows` (set both server-wide via `EDWMCP_QUERY_MAX_ROWS` and per-skill via `edw.max_rows`); the response carries `truncated=true` when more rows existed.
- All identifiers from `config.yaml` are validated against `^[A-Za-z_][A-Za-z0-9_]*$` at startup, so a typo in the mapping can never become an injection vector.
- All user-supplied values in the badminton skill (player IDs, court IDs, timestamps) are passed as bind parameters, not concatenated into SQL.
- Connect with a read-only DB user on the EDW side and a least-privilege user on the badminton side (SELECT, INSERT into `Games`/`GamePlayers`, DELETE from `PlayerQueue`, UPDATE on the columns the skill actually writes to).

## Admin UI (Flutter Web)

A separate Flutter Web app under `admin_ui/` drives a small REST configuration plane on the server (`edwmcp --admin`). Use it to:

- View server health and the registered MCP tool catalogue.
- Edit the Badminton & EDW SQLAlchemy URLs, with live "test connection" buttons.
- Edit the badminton schema mapping (table & column names) and the rotation rules without touching YAML.
- Enable/disable the EDW skill and restrict it to specific schemas.

Start the API:

```bash
EDWMCP_ADMIN_TOKEN=$(openssl rand -hex 16) edwmcp --admin
```

Run the UI:

```bash
cd admin_ui && flutter pub get && flutter run -d chrome
```

The admin API listens on `127.0.0.1:8766` by default, requires a bearer token (set `EDWMCP_ADMIN_INSECURE=1` to skip auth for loopback dev), and is fully separate from the MCP transport so the Badminton-app chatbot integration is unaffected.

## Project layout

```
src/edwmcp/
  __main__.py        # CLI entry, transport selection, --admin flag
  server.py          # FastMCP factory, wires up skills
  config.py          # Settings (env) + skills config (YAML)
  db.py              # SQLAlchemy engines, catalog helpers, query exec
  safety.py          # SELECT-only guard for the EDW skill
  admin.py           # FastAPI admin REST API (drives admin_ui)
  demo_data.py       # SQLite seed for EDWMCP_DEMO=1
  skills/
    edw.py
    badminton.py
admin_ui/            # Flutter Web configuration UI
tests/
examples/
  claude_desktop_config.json
  kinetica_tool_proxy.py
```
