from __future__ import annotations

import difflib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from play_book_studio.config.settings import load_settings
from play_book_studio.app.connection_store import (
    get_profile as _get_connection_profile,
    get_resource_detail as _get_resource_detail,
)

_ACTION_TYPES = {"scale_deployment", "rollout_restart", "log_bundle"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _document_path(root_dir: Path) -> Path:
    settings = load_settings(root_dir)
    target_dir = settings.artifacts_dir / "ops"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "actions.json"


def _read_document(root_dir: Path) -> dict[str, Any]:
    path = _document_path(root_dir)
    if not path.exists():
        return {
            "version": 1,
            "updated_at": "",
            "requests": [],
            "executions": [],
            "audit": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "version": 1,
            "updated_at": "",
            "requests": [],
            "executions": [],
            "audit": [],
        }
    return {
        "version": 1,
        "updated_at": str(payload.get("updated_at") or ""),
        "requests": [dict(item) for item in payload.get("requests", []) if isinstance(item, dict)],
        "executions": [dict(item) for item in payload.get("executions", []) if isinstance(item, dict)],
        "audit": [dict(item) for item in payload.get("audit", []) if isinstance(item, dict)],
    }


def _write_document(root_dir: Path, payload: dict[str, Any]) -> None:
    _document_path(root_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_audit(document: dict[str, Any], *, event_type: str, actor_id: str, preview: dict[str, Any], request_id: str = "", execution_id: str = "", decision_note: str = "", details: dict[str, Any] | None = None) -> None:
    document["audit"].insert(
        0,
        {
            "event_id": f"audit-{uuid.uuid4().hex}",
            "event_type": event_type,
            "actor_id": actor_id,
            "request_id": request_id,
            "execution_id": execution_id,
            "action_type": str(preview.get("action_type") or ""),
            "namespace": str(preview.get("namespace") or ""),
            "resource_name": str(preview.get("resource_name") or ""),
            "risk_level": str(preview.get("risk_level") or ""),
            "decision_note": decision_note,
            "details": details or {},
            "created_at": _now_iso(),
        },
    )


def _build_unified_diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    before_text = json.dumps(before or {}, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    after_text = json.dumps(after or {}, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    return "\n".join(
        difflib.unified_diff(
            before_text,
            after_text,
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )


def _preview_from_payload(root_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    action_type = str(payload.get("action_type") or "").strip()
    if action_type not in _ACTION_TYPES:
        raise ValueError("action_type must be scale_deployment, rollout_restart, or log_bundle")
    connection_id = str(payload.get("connection_id") or "").strip()
    if not connection_id:
        raise ValueError("connection_id is required")
    profile = _get_connection_profile(root_dir, connection_id)
    if profile is None:
        raise LookupError("Connection profile not found.")
    namespace = str(payload.get("namespace") or "").strip()
    resource_name = str(payload.get("resource_name") or "").strip()
    if not resource_name:
        raise ValueError("resource_name is required")

    replicas = int(payload.get("replicas") or 1)
    break_glass = bool(payload.get("break_glass", False))
    actor_roles = [str(item).strip() for item in payload.get("actor_roles", []) if str(item).strip()]
    allowed = True
    blocked_reasons: list[str] = []
    risk_level = "medium"
    required_approvals = 1
    validation_messages: list[str] = []
    policy_checks: list[str] = ["connection profile present", "action type recognized"]
    diff_unified = ""
    dry_run_status = "ok"
    dry_run_messages: list[str] = []

    if action_type == "scale_deployment":
        risk_level = "high" if replicas >= 5 else "medium"
        required_approvals = 2 if replicas >= 5 else 1
        if replicas < 0:
            allowed = False
            blocked_reasons.append("replicas must be zero or greater")
        detail = _get_resource_detail(root_dir, profile, resource="deployments", namespace=namespace, name=resource_name)
        current_manifest = dict(detail.get("manifest_json") or {})
        current_spec = dict(current_manifest.get("spec") or {})
        current_replicas = int(current_spec.get("replicas") or 0)
        desired_manifest = {
            **current_manifest,
            "spec": {
                **current_spec,
                "replicas": replicas,
            },
        }
        diff_unified = _build_unified_diff(current_manifest, desired_manifest)
        validation_messages.append(f"Current replicas: {current_replicas}")
        validation_messages.append(f"Desired replicas: {replicas}")
        dry_run_messages.append("Deployment exists and a synthetic diff was built from the live manifest.")
    elif action_type == "rollout_restart":
        risk_level = "medium"
        detail = _get_resource_detail(root_dir, profile, resource="deployments", namespace=namespace, name=resource_name)
        current_manifest = dict(detail.get("manifest_json") or {})
        template = dict(((current_manifest.get("spec") or {}).get("template") or {}))
        template_meta = dict(template.get("metadata") or {})
        annotations = dict(template_meta.get("annotations") or {})
        annotations["kubectl.kubernetes.io/restartedAt"] = _now_iso()
        desired_manifest = {
            **current_manifest,
            "spec": {
                **dict(current_manifest.get("spec") or {}),
                "template": {
                    **template,
                    "metadata": {
                        **template_meta,
                        "annotations": annotations,
                    },
                },
            },
        }
        diff_unified = _build_unified_diff(current_manifest, desired_manifest)
        validation_messages.append("Deployment exists and rollout restart would patch pod template annotations.")
        dry_run_messages.append("Synthetic restart diff built from the live deployment manifest.")
    elif action_type == "log_bundle":
        risk_level = "low"
        detail = _get_resource_detail(root_dir, profile, resource="pods", namespace=namespace, name=resource_name)
        current_manifest = dict(detail.get("manifest_json") or {})
        diff_unified = _build_unified_diff(current_manifest, current_manifest)
        validation_messages.append("Pod exists and is readable with the current connection profile.")
        dry_run_messages.append("Read-only log bundle preview validated the target pod.")

    if break_glass:
        required_approvals = max(required_approvals, 2)

    summary = {
        "scale_deployment": f"Scale {resource_name} in {namespace} to {replicas} replicas.",
        "rollout_restart": f"Restart rollout for {resource_name} in {namespace}.",
        "log_bundle": f"Collect a log bundle for {resource_name} in {namespace}.",
    }[action_type]

    return {
        "connection_id": connection_id,
        "action_type": action_type,
        "namespace": namespace,
        "resource_name": resource_name,
        "allowed": allowed,
        "risk_level": risk_level,
        "summary": summary,
        "preview_command": f"{action_type} {resource_name} --namespace {namespace}",
        "break_glass": break_glass,
        "break_glass_reason": str(payload.get("break_glass_reason") or ""),
        "break_glass_ticket": str(payload.get("break_glass_ticket") or ""),
        "required_approvals": required_approvals,
        "approval_strategy": "two_person" if required_approvals > 1 else "single_approver",
        "requester_roles": actor_roles,
        "approver_roles": ["operator", "admin"] if required_approvals > 1 else ["operator"],
        "executor_roles": ["operator", "admin"],
        "approval_rules": [
            "break-glass requests require elevated scrutiny" if break_glass else "standard policy path",
            f"{required_approvals} approval(s) required before execution",
        ],
        "policy_checks": [*policy_checks, "live resource lookup completed"],
        "blocked_reasons": blocked_reasons,
        "validation_messages": [
            "Preview uses live resource reads but does not mutate the cluster.",
            *validation_messages,
        ],
        "diff_unified": diff_unified or f"--- current\n+++ desired\n@@\n-action: idle\n+action: {action_type}\n",
        "dry_run_status": dry_run_status,
        "dry_run_messages": dry_run_messages or ["Synthetic dry-run completed."],
        "next_step": "create_request" if allowed else "adjust_request",
    }


def preview_action(root_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return _preview_from_payload(root_dir, payload)


def create_request(root_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    preview = _preview_from_payload(root_dir, payload)
    actor_id = str(payload.get("actor_id") or "ui-local").strip() or "ui-local"
    timestamp = _now_iso()
    record = {
        "request_id": f"req-{uuid.uuid4().hex}",
        "status": "pending",
        "preview": preview,
        "requested_by": actor_id,
        "requested_roles": preview["requester_roles"],
        "required_approvals": preview["required_approvals"],
        "approval_count": 0,
        "approver_ids": [],
        "approver_role_map": {},
        "reason": str(payload.get("reason") or ""),
        "decision_note": "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    document = _read_document(root_dir)
    document["requests"].insert(0, record)
    document["updated_at"] = timestamp
    _append_audit(document, event_type="request_created", actor_id=actor_id, preview=preview, request_id=record["request_id"], details={"status": "pending"})
    _write_document(root_dir, document)
    return record


def list_requests(root_dir: Path, *, limit: int = 20) -> dict[str, Any]:
    document = _read_document(root_dir)
    return {"items": document["requests"][:limit]}


def _find_request(document: dict[str, Any], request_id: str) -> dict[str, Any]:
    for item in document["requests"]:
        if str(item.get("request_id") or "") == request_id:
            return item
    raise LookupError("Action request not found.")


def approve_request(root_dir: Path, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    actor_id = str(payload.get("actor_id") or "ui-local").strip() or "ui-local"
    actor_roles = [str(item).strip() for item in payload.get("actor_roles", []) if str(item).strip()]
    note = str(payload.get("decision_note") or "").strip()
    document = _read_document(root_dir)
    record = _find_request(document, request_id)
    approver_ids = [str(item) for item in record.get("approver_ids", [])]
    if actor_id not in approver_ids:
        approver_ids.append(actor_id)
    record["approver_ids"] = approver_ids
    approver_role_map = dict(record.get("approver_role_map") or {})
    approver_role_map[actor_id] = actor_roles
    record["approver_role_map"] = approver_role_map
    record["approval_count"] = len(approver_ids)
    record["decision_note"] = note
    record["status"] = "approved" if record["approval_count"] >= int(record.get("required_approvals") or 1) else "pending"
    record["updated_at"] = _now_iso()
    document["updated_at"] = record["updated_at"]
    _append_audit(document, event_type="request_approved", actor_id=actor_id, preview=record["preview"], request_id=request_id, decision_note=note, details={"status": record["status"]})
    _write_document(root_dir, document)
    return record


def reject_request(root_dir: Path, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    actor_id = str(payload.get("actor_id") or "ui-local").strip() or "ui-local"
    note = str(payload.get("decision_note") or "").strip()
    document = _read_document(root_dir)
    record = _find_request(document, request_id)
    record["status"] = "rejected"
    record["decision_note"] = note
    record["updated_at"] = _now_iso()
    document["updated_at"] = record["updated_at"]
    _append_audit(document, event_type="request_rejected", actor_id=actor_id, preview=record["preview"], request_id=request_id, decision_note=note, details={"status": "rejected"})
    _write_document(root_dir, document)
    return record


def execute_request(root_dir: Path, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    actor_id = str(payload.get("actor_id") or "ui-local").strip() or "ui-local"
    actor_roles = [str(item).strip() for item in payload.get("actor_roles", []) if str(item).strip()]
    force = bool(payload.get("force", False))
    document = _read_document(root_dir)
    record = _find_request(document, request_id)
    if str(record.get("status") or "") != "approved" and not force:
        raise ValueError("Request must be approved before execution.")
    timestamp = _now_iso()
    execution = {
        "execution_id": f"exe-{uuid.uuid4().hex}",
        "request_id": request_id,
        "status": "completed",
        "execution_mode": "synthetic",
        "simulated": True,
        "preview": record["preview"],
        "summary": f"Executed synthetic {record['preview']['action_type']} workflow for {record['preview']['resource_name']}.",
        "preflight_checks": [
            "request approved or force enabled",
            "connection profile present",
            "synthetic execution path selected",
        ],
        "output_lines": [
            f"actor={actor_id}",
            f"roles={','.join(actor_roles) if actor_roles else '-'}",
            "Synthetic execution completed without live mutation.",
        ],
        "error": "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    record["status"] = "executed"
    record["updated_at"] = timestamp
    document["executions"].insert(0, execution)
    document["updated_at"] = timestamp
    _append_audit(document, event_type="request_executed", actor_id=actor_id, preview=record["preview"], request_id=request_id, execution_id=execution["execution_id"], details={"status": "completed"})
    _write_document(root_dir, document)
    return execution


def list_executions(root_dir: Path, *, limit: int = 20) -> dict[str, Any]:
    document = _read_document(root_dir)
    return {"items": document["executions"][:limit]}


def list_audit(root_dir: Path, *, limit: int = 20) -> dict[str, Any]:
    document = _read_document(root_dir)
    return {"items": document["audit"][:limit]}


__all__ = [
    "approve_request",
    "create_request",
    "execute_request",
    "list_audit",
    "list_executions",
    "list_requests",
    "preview_action",
    "reject_request",
]
