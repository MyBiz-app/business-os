"""The second backup (GL15) is defined as code but switched off: these checks keep it safe.

They read the repository's own files only (no network, no database).
"""

import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPTS = ROOT / "scripts" / "backup"
GATE = "vars.OFFSITE_BACKUP_ENABLED == 'true'"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_backup_and_drill_jobs_are_off_until_the_owner_enables_them():
    backup = _workflow("backup-offsite.yml")["jobs"]["backup"]
    drill = _workflow("restore-drill.yml")["jobs"]["drill"]
    remind = _workflow("restore-drill-reminder.yml")["jobs"]["remind"]
    for job in (backup, drill, remind):
        assert job["if"] == GATE


def test_backup_workflow_uses_secrets_never_literals():
    text = (WORKFLOWS / "backup-offsite.yml").read_text(encoding="utf-8")
    assert "secrets.BACKUP_DATABASE_URL" in text
    assert not re.search(r"postgres(ql)?://[^\s$]+:[^\s$@]+@", text)
    # Only the PUBLIC age key is configured; the private key is a drill-only secret.
    assert "BACKUP_AGE_RECIPIENT" in text and "BACKUP_AGE_IDENTITY" not in text


def test_scripts_exist_encrypt_before_writing_and_refuse_a_dirty_target():
    for name in ("backup-db.sh", "copy-files.sh", "restore-drill.sh"):
        path = SCRIPTS / name
        assert path.is_file() and os.access(path, os.X_OK)
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")
    dump = (SCRIPTS / "backup-db.sh").read_text(encoding="utf-8")
    assert re.search(r"pg_dump .*\\\n\s*\| age -r", dump)  # no plain dump on disk
    restore = (SCRIPTS / "restore-drill.sh").read_text(encoding="utf-8")
    assert "is not empty" in restore


def test_runbook_and_checklist_document_the_switch_on_steps():
    runbook = (ROOT / "docs/deploy/restore-runbook.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs/deploy/go-live-checklist.md").read_text(encoding="utf-8")
    assert "OFFSITE_BACKUP_ENABLED" in runbook and "OFFSITE_BACKUP_ENABLED" in checklist
    assert "GL15" in checklist
