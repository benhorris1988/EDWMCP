"""SQLite-backed demo schema used when EDWMCP_DEMO=1.

Seeds a badminton club state plus a small `sales` warehouse-style table so the
generic EDW skill has something to introspect. Mirrors the default table and
column names from config.example.yaml so the badminton skill works unchanged.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Engine, create_engine, text


DDL = """
CREATE TABLE Players (
    PlayerId      INTEGER PRIMARY KEY,
    Name          TEXT NOT NULL,
    SkillRating   INTEGER,
    IsActive      INTEGER NOT NULL DEFAULT 1,
    JoinedAt      TEXT NOT NULL
);

CREATE TABLE Courts (
    CourtId       INTEGER PRIMARY KEY,
    Name          TEXT NOT NULL,
    IsAvailable   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE Games (
    GameId        INTEGER PRIMARY KEY AUTOINCREMENT,
    CourtId       INTEGER NOT NULL REFERENCES Courts(CourtId),
    StartedAt     TEXT NOT NULL,
    EndedAt       TEXT,
    Status        TEXT NOT NULL,
    WinningTeam   INTEGER
);

CREATE TABLE GamePlayers (
    GameId        INTEGER NOT NULL REFERENCES Games(GameId),
    PlayerId      INTEGER NOT NULL REFERENCES Players(PlayerId),
    Team          INTEGER NOT NULL,
    PRIMARY KEY (GameId, PlayerId)
);

CREATE TABLE PlayerQueue (
    PlayerId      INTEGER PRIMARY KEY REFERENCES Players(PlayerId),
    JoinedAt      TEXT NOT NULL
);

CREATE TABLE sales_fact (
    sale_id       INTEGER PRIMARY KEY,
    sale_date     TEXT NOT NULL,
    region        TEXT NOT NULL,
    product       TEXT NOT NULL,
    units         INTEGER NOT NULL,
    revenue       REAL NOT NULL
);
"""


def _seed(engine: Engine) -> None:
    now = datetime.utcnow().replace(microsecond=0)

    def iso(dt: datetime) -> str:
        return dt.isoformat(sep=" ")

    players = [
        (1, "Alice",    1700, 1, iso(now - timedelta(days=400))),
        (2, "Bob",      1500, 1, iso(now - timedelta(days=300))),
        (3, "Charlie",  1650, 1, iso(now - timedelta(days=250))),
        (4, "Diana",    1550, 1, iso(now - timedelta(days=200))),
        (5, "Ethan",    1400, 1, iso(now - timedelta(days=150))),
        (6, "Fiona",    1750, 1, iso(now - timedelta(days=120))),
        (7, "George",   1450, 1, iso(now - timedelta(days=90))),
        (8, "Hannah",   1600, 1, iso(now - timedelta(days=60))),
        (9, "Ian",      1350, 0, iso(now - timedelta(days=30))),
    ]
    courts = [
        (1, "Court 1", 1),
        (2, "Court 2", 1),
        (3, "Court 3", 0),
    ]
    queue = [
        (2, iso(now - timedelta(minutes=18))),
        (5, iso(now - timedelta(minutes=15))),
        (7, iso(now - timedelta(minutes=12))),
        (4, iso(now - timedelta(minutes=9))),
        (8, iso(now - timedelta(minutes=6))),
        (3, iso(now - timedelta(minutes=3))),
    ]
    sales = [
        (i + 1,
         iso(now - timedelta(days=i)),
         ["EMEA", "AMER", "APAC"][i % 3],
         ["Racket", "Shuttles", "Grip", "Shoes"][i % 4],
         10 + i,
         round(99.5 + i * 3.25, 2))
        for i in range(40)
    ]

    with engine.begin() as conn:
        conn.executescript(DDL) if hasattr(conn, "executescript") else None
        for stmt in DDL.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))

        conn.execute(
            text(
                "INSERT INTO Players (PlayerId, Name, SkillRating, IsActive, JoinedAt) "
                "VALUES (:id, :name, :skill, :active, :joined)"
            ),
            [{"id": p[0], "name": p[1], "skill": p[2], "active": p[3], "joined": p[4]} for p in players],
        )
        conn.execute(
            text("INSERT INTO Courts (CourtId, Name, IsAvailable) VALUES (:id, :name, :av)"),
            [{"id": c[0], "name": c[1], "av": c[2]} for c in courts],
        )
        conn.execute(
            text("INSERT INTO PlayerQueue (PlayerId, JoinedAt) VALUES (:pid, :ja)"),
            [{"pid": q[0], "ja": q[1]} for q in queue],
        )
        conn.execute(
            text(
                "INSERT INTO sales_fact (sale_id, sale_date, region, product, units, revenue) "
                "VALUES (:id, :d, :r, :p, :u, :rev)"
            ),
            [{"id": s[0], "d": s[1], "r": s[2], "p": s[3], "u": s[4], "rev": s[5]} for s in sales],
        )


def build_demo_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:", future=True)
    _seed(engine)
    return engine
