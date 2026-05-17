import pytest

from edwmcp.safety import UnsafeQueryError, assert_select_only


def test_allows_simple_select():
    assert_select_only("SELECT 1")


def test_allows_select_with_cte():
    assert_select_only("WITH x AS (SELECT 1 AS n) SELECT n FROM x")


def test_allows_select_with_joins_and_where():
    assert_select_only(
        "SELECT p.id, g.id FROM players p JOIN games g ON g.player_id = p.id WHERE p.active = 1"
    )


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM players",
        "UPDATE players SET name = 'x'",
        "INSERT INTO players VALUES (1)",
        "DROP TABLE players",
        "ALTER TABLE players ADD COLUMN x INT",
        "TRUNCATE TABLE players",
        "CREATE TABLE x (id INT)",
        "EXEC sp_who",
        "GRANT SELECT ON players TO public",
    ],
)
def test_rejects_mutations(sql):
    with pytest.raises(UnsafeQueryError):
        assert_select_only(sql)


def test_rejects_multiple_statements():
    with pytest.raises(UnsafeQueryError):
        assert_select_only("SELECT 1; SELECT 2")


def test_rejects_select_then_delete():
    with pytest.raises(UnsafeQueryError):
        assert_select_only("SELECT 1; DELETE FROM players")


def test_rejects_empty():
    with pytest.raises(UnsafeQueryError):
        assert_select_only("   ")
