"""Migrations expand first and contract one release later, so a rollback never breaks the database.

A migration that drops or renames a column or table, or changes a column type, can break the
previous API version still running during a deploy or after a rollback. From 0117 on, such a
migration must say why it is safe with a line `# contract: <reason>` (for example "the column was
unused since 0110"). Earlier migrations are not checked.
Rule: CLAUDE.md, docs/deploy/releases.md."""

import os
import re

from tests.conftest import API_DIR

FIRST_CHECKED = 117
RISKY = re.compile(
    r"drop_column|drop_table|alter_column\([^)]*(new_column_name|type_)|rename_table"
    r"|DROP\s+(COLUMN|TABLE)|RENAME\s+(COLUMN|TO)|ALTER\s+COLUMN\s+\w+\s+(SET\s+DATA\s+)?TYPE",
    re.IGNORECASE | re.DOTALL,
)


def _migrations() -> list[tuple[str, str]]:
    versions = os.path.join(API_DIR, "migrations", "versions")
    found = []
    for name in sorted(os.listdir(versions)):
        match = re.match(r"(\d{4})_.*\.py$", name)
        if match and int(match.group(1)) >= FIRST_CHECKED:
            with open(os.path.join(versions, name), encoding="utf-8") as handle:
                found.append((name, handle.read()))
    return found


def test_destructive_migrations_explain_why_they_are_safe() -> None:
    unexplained = [
        name
        for name, text in _migrations()
        if RISKY.search(text) and not re.search(r"^\s*#\s*contract:\s*\S", text, re.MULTILINE)
    ]
    assert unexplained == [], (
        "These migrations drop, rename or retype something. Expand first, contract one release "
        "later, and add a line '# contract: <why the previous version still works>': "
        f"{unexplained}"
    )


def test_the_check_recognises_risky_statements() -> None:
    for sample in (
        "op.drop_column('t', 'c')",
        "op.execute('ALTER TABLE t DROP COLUMN c')",
        "op.execute('alter table t rename column a to b')",
        "op.execute('ALTER TABLE t ALTER COLUMN a TYPE text')",
        "op.drop_table('t')",
    ):
        assert RISKY.search(sample), sample
    assert not RISKY.search("op.add_column('t', sa.Column('c', sa.Text()))")
