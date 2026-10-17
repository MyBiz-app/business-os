"""No new SQL built with f-strings.

`text(f"...")` puts Python values straight into SQL text, so a user value that reaches one is an
SQL injection. The existing ones were audited (October 2026): they interpolate only module
constants (column lists, SELECTs), WHERE fragments the code picks from literals, and column names
checked by `set_clause` / `check_columns` against an allow-list. Values always go in as bound
`:params`.

This test keeps that list from growing: a new f-string (or `.format()` / `%`) inside `text(`
fails CI. Bind values as `:params` instead; if a dynamic identifier is really needed, build it
with `set_clause` / `check_columns` and raise the file's count below in the same pull request,
where review can see it. When a file loses one, lower its count.
"""

import ast
from collections import Counter
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

# Audited f-strings inside text(...), per file under app/.
ALLOWED = {
    "api/billing.py": 3,
    "api/bookings.py": 3,
    "api/checkouts.py": 1,
    "api/client_app.py": 7,
    "api/client_notes.py": 2,
    "api/clients.py": 4,
    "api/common.py": 2,
    "api/dependents.py": 4,
    "api/documents.py": 4,
    "api/files.py": 5,
    "api/health.py": 4,
    "api/leads.py": 4,
    "api/locations.py": 4,
    "api/messaging.py": 2,
    "api/onsite_jobs.py": 6,
    "api/people.py": 1,
    "api/plans.py": 7,
    "api/privacy.py": 1,
    "api/promo_codes.py": 2,
    "api/quotes.py": 4,
    "api/receipts.py": 5,
    "api/resources.py": 1,
    "api/reviews.py": 3,
    "api/routes.py": 1,
    "api/schedule.py": 3,
    "api/services.py": 4,
    "api/settings.py": 1,
    "api/shift_planning.py": 2,
    "api/shift_swaps.py": 2,
    "api/shifts.py": 3,
    "api/staff.py": 8,
    "api/stations.py": 2,
    "api/time_billing.py": 4,
    "api/time_off_requests.py": 2,
    "core/business_export.py": 1,  # table and column names read from the database catalog
    "files/__init__.py": 1,
    "reports/metrics.py": 1,
    "secrets_rotation.py": 2,  # table and column names from the COLUMNS constant
}


def _is_formatted(node: ast.expr) -> bool:
    """An f-string, "...".format(...) or "..." % values."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format"
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)


def _formatted_text_calls() -> Counter[str]:
    found: Counter[str] = Counter()
    for path in APP.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name | ast.Attribute)
                and (getattr(node.func, "id", None) or getattr(node.func, "attr", None)) == "text"
                and node.args
                and _is_formatted(node.args[0])
            ):
                found[path.relative_to(APP).as_posix()] += 1
    return found


def test_no_new_formatted_sql():
    found = _formatted_text_calls()
    grown = {f: n for f, n in found.items() if n > ALLOWED.get(f, 0)}
    assert not grown, (
        f"New f-string SQL inside text(...) in {grown} (allowed: "
        f"{ {f: ALLOWED.get(f, 0) for f in grown} }). Bind values as :params; for a dynamic "
        "column name use set_clause/check_columns and raise the count in this test."
    )


def test_allow_list_is_tight():
    found = _formatted_text_calls()
    shrunk = {f: found.get(f, 0) for f, n in ALLOWED.items() if found.get(f, 0) < n}
    assert not shrunk, f"Fewer f-string SQL calls than allowed; lower the counts to {shrunk}."


def test_detects_formatted_sql():
    for source in ('text(f"x {y}")', 'text("x {}".format(y))', 'text("x %s" % y)'):
        assert _is_formatted(ast.parse(source).body[0].value.args[0])  # type: ignore[attr-defined]
    assert not _is_formatted(ast.parse('text("x" + y)').body[0].value.args[0])  # type: ignore[attr-defined]
