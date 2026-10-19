"""The security agent's tools (slice C5): a defensive, read-only look at MyBiz's own staging.

The agent reads the structure of the database (tables without row level security, owner-rights
functions with open grants), two-step sign-in coverage, the team's visits inside businesses and
the console audit log, ranks what it finds and saves a report. It never runs a scanner, never
opens a connection to anything and never reads rows of a business. Its tools refuse to run in
production: it works on staging (and on a developer's own machine and tests) only. The server
sorts and counts the findings, so a report's numbers do not depend on the model."""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

# Where the agent may run. Production is never in this list; a test keeps it that way.
ALLOWED_ENVIRONMENTS = ("local", "test", "staging")
SEVERITIES = ("critical", "high", "medium", "low", "info")
STATUSES = ("open", "in_progress", "fixed")
MAX_FINDINGS = 60


def environment() -> str:
    return get_settings().environment


def ensure_allowed() -> None:
    if environment() not in ALLOWED_ENVIRONMENTS:
        raise ValueError(
            "the security agent works on staging only and is switched off in this environment"
        )


def db_checks(db: Session, _args: dict[str, Any]) -> dict[str, Any]:
    ensure_allowed()
    rows = db.execute(text("SELECT * FROM app.platform_security_db_checks()")).mappings()
    findings, checked = [], []
    for r in rows:
        if r["severity"] == "info":
            checked.append(r["detail"])
        else:
            findings.append(
                {
                    "check": r["check_name"],
                    "severity": r["severity"],
                    "subject": r["subject"],
                    "detail": r["detail"],
                }
            )
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["subject"]))
    return {"checked": checked, "findings": findings[:MAX_FINDINGS], "total": len(findings)}


def _finding(raw: dict[str, Any]) -> dict[str, str]:
    severity = str(raw["severity"])
    status = str(raw.get("status") or "open")
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {', '.join(SEVERITIES)}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    title, fix = str(raw["title"]).strip()[:160], str(raw["fix"]).strip()[:600]
    if not title or not fix:
        raise ValueError("every finding needs a title and how to fix it")
    return {
        "severity": severity,
        "status": status,
        "title": title,
        "evidence": str(raw["evidence"]).strip()[:600],
        "fix": fix,
    }


def save_security_report(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    ensure_allowed()
    title = str(args["title"]).strip()[:120]
    summary = str(args["summary"]).strip()[:2000]
    if not title or not summary:
        raise ValueError("a report needs a title and a summary")
    raw = list(args["findings"])
    if len(raw) > MAX_FINDINGS:
        raise ValueError(f"send at most {MAX_FINDINGS} findings")
    findings = sorted(
        (_finding(f) for f in raw), key=lambda f: (SEVERITIES.index(f["severity"]), f["title"])
    )
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    body = {"findings": findings, "counts": counts, "environment": environment()}
    report_id = db.execute(
        text(
            "SELECT app.platform_ai_report_add('security', :title, :summary, CAST(:body AS jsonb))"
        ),
        {"title": title, "summary": summary, "body": json.dumps(body)},
    ).scalar_one()
    return {
        "report_id": str(report_id),
        "counts": counts,
        "note": "Saved. A person decides what to fix; the agent changes nothing.",
    }
