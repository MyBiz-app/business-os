"""Executing pending actions after the user confirms them.

Confirmation sends the pending action's id (never "yes" to the model). The server checks it is
still pending, unexpired, unchanged (payload hash), requested by this user, and that the user
still holds the permission; then it executes exactly once and writes the audit log."""

import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text

from app.ai import scheduled
from app.ai.tools import TOOLS, payload_hash
from app.api import time_billing
from app.api.bookings import cancel_booking, lock_session, place_booking
from app.api.deps import TenantContext, has_module
from app.messaging.notifications import notify_booking
from app.social import studio

# What each action changed, for the audit log: the entity type and its id in the result.
ENTITY = {
    "book_client": ("booking", lambda result: result["booking_id"]),
    "cancel_booking": ("booking", lambda result: result["booking_id"]),
    "log_time": ("time_entry", lambda result: result["time_entry_id"]),
    "bill_month": ("quote", lambda result: result["bills"][0]),
    "publish_post": ("social_draft", lambda result: result["draft_id"]),
    "schedule_task": ("ai_task", lambda result: result["task_id"]),
    "cancel_scheduled_task": ("ai_task", lambda result: result["task_id"]),
}


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _execute(
    tenant: TenantContext, user_id: UUID, agent_key: str, tool_name: str, payload: dict[str, Any]
) -> dict[str, Any]:
    db = tenant.session
    if tool_name == "schedule_task":
        try:
            scheduled.check_limit(db, [k for k in scheduled.MAX_ACTIVE if has_module(db, k)])
            task_id = scheduled.create_task(db, tenant.tenant_id, user_id, agent_key, payload)
        except scheduled.ScheduleError as error:
            raise _conflict(str(error)) from error
        return {"task_id": str(task_id)}
    if tool_name == "cancel_scheduled_task":
        task_id = UUID(payload["task_id"])
        changed = db.execute(
            text("""
                UPDATE app.ai_scheduled_tasks
                SET status = 'done', status_reason = 'cancelled', next_run_at = NULL,
                    updated_at = now()
                WHERE id = :id AND created_by = :user AND status IN ('active', 'paused')
            """),
            {"id": task_id, "user": user_id},
        ).rowcount
        if not changed:
            raise _conflict("already_cancelled")
        return {"task_id": str(task_id)}
    if tool_name == "book_client":
        booking_id = place_booking(
            db,
            tenant.tenant_id,
            UUID(payload["session_id"]),
            UUID(payload["client_id"]),
            requires_plan=False,
            dependent_id=UUID(payload["dependent_id"]) if payload.get("dependent_id") else None,
        )
        notify_booking(db, booking_id, "booked_by_studio")
        booking_status = db.execute(
            text("SELECT status FROM app.bookings WHERE id = :id"), {"id": booking_id}
        ).scalar_one()
        return {"booking_id": str(booking_id), "status": booking_status}
    if tool_name == "cancel_booking":
        booking_id = UUID(payload["booking_id"])
        row = db.execute(
            text("SELECT session_id, status FROM app.bookings WHERE id = :id"), {"id": booking_id}
        ).first()
        if row is None or row.status == "cancelled":
            raise _conflict("already_cancelled")
        lock_session(db, row.session_id)
        cancel_booking(db, booking_id, row.session_id)
        notify_booking(db, booking_id, "booking_cancelled_by_studio")
        return {"booking_id": str(booking_id), "status": "cancelled"}
    if tool_name == "log_time":
        entry = time_billing.log_time(time_billing.TimeEntryCreate(**payload), tenant)
        return {"time_entry_id": str(entry.id)}
    if tool_name == "bill_month":
        # Re-validated now: a client billed since the card was made is skipped.
        result = time_billing.billing_run(time_billing.BillingRun(**payload), tenant)
        if not result.bills:
            raise _conflict("nothing_to_bill")
        return {"bills": [str(bill.id) for bill in result.bills], "skipped": len(result.skipped)}
    if tool_name == "publish_post":
        account_id = UUID(payload["account_id"])
        # Re-validated now: the account must still be in view of the person who confirms.
        if all(a["id"] != account_id for a in studio.visible_accounts(db, tenant.branches)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
        return studio.publish_draft(db, account_id, UUID(payload["draft_id"]))
    raise _conflict("unknown_action")


def decide(tenant: TenantContext, user_id: UUID, action_id: UUID, confirm: bool) -> None:
    db = tenant.session
    action = (
        db.execute(
            text("""
                SELECT id, requested_by, agent_key, tool_name, payload, payload_hash, preview,
                       status, expires_at < now() AS expired
                FROM app.pending_actions WHERE id = :id FOR UPDATE
            """),
            {"id": action_id},
        )
        .mappings()
        .first()
    )
    if action is None or action["requested_by"] != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    if action["status"] != "pending":
        raise _conflict("already_decided")

    def finish(new_status: str, result: dict[str, Any] | None = None) -> None:
        db.execute(
            text("""
                UPDATE app.pending_actions
                SET status = :status, decided_by = :user_id, decided_at = now(), result = :result
                WHERE id = :id
            """),
            {
                "status": new_status,
                "user_id": user_id,
                "result": json.dumps(result) if result is not None else None,
                "id": action_id,
            },
        )

    if action["expired"]:
        finish("expired")
        raise _conflict("expired")
    if not confirm:
        finish("rejected")
        return

    tool = TOOLS[action["tool_name"]]
    if tool.module and not has_module(db, tool.module):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
    if tool.permission not in tenant.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if payload_hash(action["tool_name"], action["payload"]) != action["payload_hash"]:
        finish("failed", {"error": "payload_changed"})
        raise _conflict("payload_changed")

    try:
        with db.begin_nested():
            result = _execute(
                tenant, user_id, action["agent_key"], action["tool_name"], action["payload"]
            )
    except HTTPException as error:
        finish("failed", {"error": str(error.detail)})
        db.commit()  # keep the failed state; the caller's transaction ends with the error
        raise
    finish("executed", result)
    _audit(
        tenant,
        user_id,
        f"assistant.{action['tool_name']}",
        action["tool_name"],
        result,
        {
            "pending_action_id": str(action_id),
            "payload": action["payload"],
            # An outside AI app asked for it (an MCP connector): the log says which.
            **({"source": action["preview"]["source"]} if "source" in action["preview"] else {}),
            **result,
        },
    )


def _audit(
    tenant: TenantContext,
    user_id: UUID,
    action: str,
    tool_name: str,
    result: dict[str, Any],
    details: dict[str, Any],
) -> None:
    entity_type, entity_id = ENTITY[tool_name][0], ENTITY[tool_name][1](result)
    tenant.session.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, on_behalf_of, action, entity_type, entity_id,
                 details)
            VALUES (:tenant_id, 'ai', NULL, :user_id, :action, :entity_type, :entity_id,
                    :details)
        """),
        {
            "tenant_id": tenant.tenant_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": json.dumps(details),
        },
    )


def run_approved(
    tenant: TenantContext,
    user_id: UUID,
    tool_name: str,
    payload: dict[str, Any],
    expected_hash: str,
    task_id: UUID,
) -> dict[str, Any]:
    """Runs an action the user approved earlier, as a scheduled task. Everything is checked again
    now, exactly like a confirmation: the module, the user's permission today, and that the
    approved payload is unchanged. A booking that became full or a client billed since simply
    fails with the tool's own error."""
    tool = TOOLS.get(tool_name)
    if tool is None or tool_name not in scheduled.SCHEDULABLE_TOOLS:
        raise _conflict("unknown_action")
    if tool.module and not has_module(tenant.session, tool.module):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
    if tool.permission not in tenant.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if payload_hash(tool_name, payload) != expected_hash:
        raise _conflict("payload_changed")
    with tenant.session.begin_nested():
        result = _execute(tenant, user_id, "scheduled", tool_name, payload)
    _audit(
        tenant,
        user_id,
        f"assistant.scheduled.{tool_name}",
        tool_name,
        result,
        {"scheduled_task_id": str(task_id), "payload": payload, **result},
    )
    return result
