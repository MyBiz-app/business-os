import pytest

from app.api.common import check_columns, set_clause

ALLOWED = {"name", "custom_fields"}


def test_set_clause_builds_bound_assignments():
    assert set_clause({"name": "x"}, ALLOWED) == "name = :name, updated_at = now()"


def test_set_clause_without_updated_at():
    assert set_clause({"name": "x"}, ALLOWED, touch=False) == "name = :name"


def test_set_clause_casts_columns():
    sql = set_clause({"custom_fields": {}}, ALLOWED, casts={"custom_fields": "jsonb"})
    assert sql.startswith("custom_fields = CAST(:custom_fields AS jsonb)")


@pytest.mark.parametrize("bad", ["name; DROP TABLE x", "a = 1, b", "Name", "1a", "a-b"])
def test_set_clause_rejects_unsafe_column_names(bad):
    with pytest.raises(ValueError):
        set_clause({bad: 1}, {bad})


def test_set_clause_rejects_columns_outside_the_allow_list():
    with pytest.raises(ValueError):
        set_clause({"tenant_id": 1}, ALLOWED)


def test_check_columns_accepts_model_fields():
    from pydantic import BaseModel

    class Form(BaseModel):
        name: str

    check_columns({"name": "x"}, Form.model_fields)
    with pytest.raises(ValueError):
        check_columns({"role": "owner"}, Form.model_fields)
