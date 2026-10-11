"""The migration chain stays linear: one head, one file per number, file name matches revision.

Two files once shared the number 0058; this fails the pull request before that reaches staging."""

import os
import re
from collections import Counter

from alembic.config import Config
from alembic.script import ScriptDirectory

from tests.conftest import API_DIR


def _script() -> ScriptDirectory:
    config = Config(os.path.join(API_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(API_DIR, "migrations"))
    return ScriptDirectory.from_config(config)


def test_there_is_exactly_one_head() -> None:
    assert len(_script().get_heads()) == 1, "two migrations branch from the same parent"


def test_migration_numbers_are_unique_and_match_their_revision() -> None:
    versions = os.path.join(API_DIR, "migrations", "versions")
    files = [f for f in os.listdir(versions) if re.match(r"\d{4}_.*\.py$", f)]
    numbers = Counter(f[:4] for f in files)
    assert [n for n, count in numbers.items() if count > 1] == [], "duplicate migration number"
    for revision in _script().walk_revisions():
        assert os.path.basename(revision.path).startswith(f"{revision.revision}_")
