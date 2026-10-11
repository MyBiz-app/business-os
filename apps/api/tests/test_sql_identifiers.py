import pytest

from app.api.common import set_clause


def test_set_clause_builds_bound_assignments():
    assert set_clause({"name": "x"}) == "name = :name, updated_at = now()"


def test_set_clause_casts_columns():
    sql = set_clause({"custom_fields": {}}, casts={"custom_fields": "jsonb"})
    assert sql.startswith("custom_fields = CAST(:custom_fields AS jsonb)")


@pytest.mark.parametrize("bad", ["name; DROP TABLE x", "a = 1, b", "Name", "1a", "a-b"])
def test_set_clause_rejects_unsafe_column_names(bad):
    with pytest.raises(ValueError):
        set_clause({bad: 1})
