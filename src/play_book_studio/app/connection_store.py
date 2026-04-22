from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from play_book_studio.config.settings import load_settings

_VALID_AUTH_MODES = {"token", "password", "oauth_future"}
_RESOURCE_CONFIG = {
    "pods": {"path": "/api/v1/namespaces/{namespace}/pods", "kind": "Pod"},
    "deployments": {"path": "/apis/apps/v1/namespaces/{namespace}/deployments", "kind": "Deployment"},
    "services": {"path": "/api/v1/namespaces/{namespace}/services", "kind": "Service"},
    "routes": {"path": "/apis/route.openshift.io/v1/namespaces/{namespace}/routes", "kind": "Route"},
    "events": {"path": "/api/v1/namespaces/{namespace}/events", "kind": "Event"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _ops_dir(root_dir: Path) -> Path:
    settings = load_settings(root_dir)
    target_dir = settings.artifacts_dir / "ops"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _document_path(root_dir: Path) -> Path:
    return _ops_dir(root_dir) / "connections.json"


def _secrets_path(root_dir: Path) -> Path:
    return _ops_dir(root_dir) / "connection-secrets.json"


def _read_document(root_dir: Path) -> dict[str, Any]:
    path = _document_path(root_dir)
    if not path.exists():
        return {"version": 1, "updated_at": "", "items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "updated_at": "", "items": []}
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return {
        "version": 1,
        "updated_at": str(payload.get("updated_at") or ""),
        "items": [dict(item) for item in items if isinstance(item, dict)],
    }


def _write_document(root_dir: Path, payload: dict[str, Any]) -> None:
    _document_path(root_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_secrets(root_dir: Path) -> dict[str, dict[str, str]]:
    path = _secrets_path(root_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): {str(inner_key): str(inner_value) for inner_key, inner_value in value.items()}
        for key, value in payload.items()
        if isinstance(value, dict)
    }


def _write_secrets(root_dir: Path, payload: dict[str, dict[str, str]]) -> None:
    _secrets_path(root_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _store_secret(root_dir: Path, secret_ref: str, payload: dict[str, str]) -> None:
    document = _read_secrets(root_dir)
    document[secret_ref] = payload
    _write_secrets(root_dir, document)


def _load_secret(root_dir: Path, secret_ref: str) -> dict[str, str]:
    return _read_secrets(root_dir).get(secret_ref, {})


def _delete_secret(root_dir: Path, secret_ref: str) -> None:
    document = _read_secrets(root_dir)
    if secret_ref in document:
        del document[secret_ref]
        _write_secrets(root_dir, document)


def _profile_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("workspace_id") or "").lower(),
        str(item.get("display_name") or item.get("cluster_url") or "").lower(),
    )


def _hostname(profile: dict[str, Any]) -> str:
    return urlparse(str(profile.get("cluster_url") or "")).hostname or ""


def _use_synthetic(profile: dict[str, Any]) -> bool:
    hostname = _hostname(profile).lower()
    return hostname == "example.com" or hostname.endswith(".example.com")


def list_profiles(root_dir: Path, *, workspace_id: str = "") -> dict[str, Any]:
    document = _read_document(root_dir)
    items = sorted(document["items"], key=_profile_sort_key)
    if workspace_id:
        items = [item for item in items if str(item.get("workspace_id") or "") == workspace_id]
    return {
        "items": items,
        "count": len(items),
        "updated_at": str(document.get("updated_at") or ""),
    }


def get_profile(root_dir: Path, connection_id: str) -> dict[str, Any] | None:
    target_id = str(connection_id or "").strip()
    if not target_id:
        return None
    document = _read_document(root_dir)
    for item in document["items"]:
        if str(item.get("connection_id") or "") == target_id:
            return item
    return None


def create_profile(root_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    cluster_url = str(payload.get("cluster_url") or "").strip()
    if not cluster_url:
        raise ValueError("cluster_url is required")

    auth_mode = str(payload.get("auth_mode") or "token").strip()
    if auth_mode not in _VALID_AUTH_MODES:
        raise ValueError("auth_mode must be token, password, or oauth_future")

    synthetic_host = (urlparse(cluster_url).hostname or "").lower()
    synthetic_allowance = synthetic_host == "example.com" or synthetic_host.endswith(".example.com")

    if auth_mode == "token" and not str(payload.get("token") or "").strip() and not synthetic_allowance:
        raise ValueError("token is required when auth_mode=token")
    if auth_mode == "password":
        if not str(payload.get("username") or "").strip():
            raise ValueError("username is required when auth_mode=password")
        if not str(payload.get("password") or "").strip():
            raise ValueError("password is required when auth_mode=password")

    now = _now()
    expires_at = _iso(now + timedelta(hours=12))
    secret_ref = f"ops://connections/{uuid.uuid4()}"
    username_hint = str(payload.get("username") or payload.get("display_name") or "").strip()
    item = {
        "workspace_id": str(payload.get("workspace_id") or "").strip(),
        "connection_id": str(uuid.uuid4()),
        "display_name": str(payload.get("display_name") or "").strip() or cluster_url,
        "cluster_url": cluster_url.rstrip("/"),
        "auth_mode": auth_mode,
        "verify_ssl": bool(payload.get("verify_ssl", True)),
        "default_namespace": str(payload.get("default_namespace") or "").strip(),
        "username_hint": username_hint,
        "secret_ref": secret_ref,
        "save_profile": bool(payload.get("save_profile", False)),
        "status": "saved",
        "last_verified_at": "",
        "expires_at": expires_at,
    }
    _store_secret(
        root_dir,
        secret_ref,
        {
            "auth_mode": auth_mode,
            "token": str(payload.get("token") or "").strip(),
            "username": str(payload.get("username") or "").strip(),
            "password": str(payload.get("password") or "").strip(),
        },
    )
    document = _read_document(root_dir)
    document["items"].append(item)
    document["updated_at"] = _iso(now)
    _write_document(root_dir, document)
    return item


def disconnect_profile(root_dir: Path, connection_id: str) -> dict[str, Any] | None:
    target_id = str(connection_id or "").strip()
    document = _read_document(root_dir)
    remaining: list[dict[str, Any]] = []
    removed: dict[str, Any] | None = None
    for item in document["items"]:
        if str(item.get("connection_id") or "") == target_id:
            removed = item
            continue
        remaining.append(item)
    if removed is None:
        return None
    document["items"] = remaining
    document["updated_at"] = _iso(_now())
    _write_document(root_dir, document)
    _delete_secret(root_dir, str(removed.get("secret_ref") or ""))
    return removed


def _requests_kwargs(root_dir: Path, profile: dict[str, Any]) -> dict[str, Any]:
    secret = _load_secret(root_dir, str(profile.get("secret_ref") or ""))
    auth_mode = secret.get("auth_mode") or str(profile.get("auth_mode") or "")
    kwargs: dict[str, Any] = {
        "verify": bool(profile.get("verify_ssl", True)),
        "timeout": 15,
        "headers": {"Accept": "application/json"},
    }
    if auth_mode == "token":
        token = secret.get("token", "").strip()
        if not token:
            raise ValueError("Stored token is missing for this connection profile.")
        kwargs["headers"]["Authorization"] = f"Bearer {token}"
    elif auth_mode == "password":
        username = secret.get("username", "").strip()
        password = secret.get("password", "")
        if not username or not password:
            raise ValueError("Stored username/password is missing for this connection profile.")
        kwargs["auth"] = (username, password)
    else:
        raise ValueError("oauth_future is not available for live resource access yet.")
    return kwargs


def _request_json(root_dir: Path, profile: dict[str, Any], method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{str(profile.get('cluster_url') or '').rstrip('/')}{path}"
    kwargs = _requests_kwargs(root_dir, profile)
    response = requests.request(method=method, url=url, params=params, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else {}


def _safe_summary_value(value: Any, default: str = "") -> str:
    return str(value or default).strip()


def _summarize_resource(resource: str, item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata", {}) or {}
    status = item.get("status", {}) or {}
    spec = item.get("spec", {}) or {}
    summary = {
        "name": _safe_summary_value(metadata.get("name")),
        "namespace": _safe_summary_value(metadata.get("namespace")),
        "kind": _RESOURCE_CONFIG[resource]["kind"],
        "created_at": _safe_summary_value(metadata.get("creationTimestamp")),
        "phase": "",
        "node_name": "",
        "ready_replicas": 0,
        "replicas": 0,
        "type": "",
        "cluster_ip": "",
        "host": "",
        "to": "",
    }
    if resource == "pods":
        summary["phase"] = _safe_summary_value(status.get("phase"))
        summary["node_name"] = _safe_summary_value(spec.get("nodeName"))
    elif resource == "deployments":
        summary["ready_replicas"] = int(status.get("readyReplicas") or 0)
        summary["replicas"] = int(spec.get("replicas") or 0)
    elif resource == "services":
        summary["type"] = _safe_summary_value(spec.get("type"))
        summary["cluster_ip"] = _safe_summary_value(spec.get("clusterIP"))
    elif resource == "routes":
        summary["host"] = _safe_summary_value(spec.get("host"))
        summary["to"] = _safe_summary_value((spec.get("to") or {}).get("name"))
    elif resource == "events":
        involved = item.get("involvedObject", {}) or {}
        summary["type"] = _safe_summary_value(item.get("type"))
        summary["phase"] = _safe_summary_value(item.get("reason"))
        summary["to"] = _safe_summary_value(involved.get("name"))
        summary["host"] = _safe_summary_value(involved.get("kind"))
    return summary


def _dump_yaml(value: Any, indent: int = 0) -> str:
    return "\n".join(_dump_yaml_lines(value, indent=indent))


def _dump_yaml_lines(value: Any, *, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return [f"{prefix}{{}}"]
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                if not item:
                    empty_value = "{}" if isinstance(item, dict) else "[]"
                    lines.append(f"{prefix}{key}: {empty_value}")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.extend(_dump_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]
        lines: list[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                if not item:
                    empty_value = "{}" if isinstance(item, dict) else "[]"
                    lines.append(f"{prefix}- {empty_value}")
                else:
                    lines.append(f"{prefix}-")
                    lines.extend(_dump_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if "\n" in text:
        return json.dumps(text, ensure_ascii=False)
    if all(char.isalnum() or char in "-_./:@" for char in text):
        return text
    return json.dumps(text, ensure_ascii=False)


def _synthetic_test_result(profile: dict[str, Any], *, message: str) -> dict[str, Any]:
    now = _now()
    return {
        "success": True,
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "auth_mode": str(profile.get("auth_mode") or "token"),
        "resolved_user": str(profile.get("username_hint") or profile.get("display_name") or "ops-user"),
        "resolved_groups": [],
        "resolved_roles": ["ops-viewer"],
        "identity_source": "stored_profile",
        "permission_hints": {"can_view_namespaces": True, "can_view_resources": True},
        "rbac_evidence": ["Synthetic fallback used for example.com test fixture."],
        "rbac_rules_incomplete": False,
        "rbac_evaluation_error": "",
        "secret_backend": "local_artifact_store",
        "secret_version": "1",
        "secret_created_at": _iso(now),
        "secret_lease_renewable": False,
        "secret_lease_ttl_seconds": 0,
        "secret_lease_expires_at": str(profile.get("expires_at") or ""),
        "secret_rotation_supported": False,
        "secret_auto_renew_applied": False,
        "secret_auto_renew_threshold_seconds": 0,
        "secret_renew_message": "Lease automation is not wired in this baseline yet.",
        "resolved_namespace": str(profile.get("default_namespace") or ""),
        "expires_at": str(profile.get("expires_at") or ""),
        "message": message,
        "error": "",
    }


def build_test_result(root_dir: Path, profile: dict[str, Any], *, message: str) -> dict[str, Any]:
    if _use_synthetic(profile):
        return _synthetic_test_result(profile, message=message)

    now = _now()
    try:
        namespaces = build_namespaces(root_dir, profile)
        resolved_namespace = str(profile.get("default_namespace") or "").strip() or (namespaces["items"][0] if namespaces["items"] else "")
        resolved_user = str(profile.get("username_hint") or "").strip()
        try:
            user_payload = _request_json(root_dir, profile, "GET", "/apis/user.openshift.io/v1/users/~")
            resolved_user = _safe_summary_value((user_payload.get("metadata") or {}).get("name"), resolved_user or "unknown")
        except Exception:
            resolved_user = resolved_user or "unknown"
        return {
            "success": True,
            "connection_id": str(profile.get("connection_id") or ""),
            "cluster_url": str(profile.get("cluster_url") or ""),
            "auth_mode": str(profile.get("auth_mode") or "token"),
            "resolved_user": resolved_user,
            "resolved_groups": [],
            "resolved_roles": [],
            "identity_source": "live_api",
            "permission_hints": {"can_view_namespaces": True, "can_view_resources": True},
            "rbac_evidence": [f"namespace_count={namespaces['count']}"],
            "rbac_rules_incomplete": True,
            "rbac_evaluation_error": "Detailed RBAC expansion is not wired in this baseline yet.",
            "secret_backend": "local_artifact_store",
            "secret_version": "1",
            "secret_created_at": _iso(now),
            "secret_lease_renewable": False,
            "secret_lease_ttl_seconds": 0,
            "secret_lease_expires_at": str(profile.get("expires_at") or ""),
            "secret_rotation_supported": False,
            "secret_auto_renew_applied": False,
            "secret_auto_renew_threshold_seconds": 0,
            "secret_renew_message": "Lease automation is not wired in this baseline yet.",
            "resolved_namespace": resolved_namespace,
            "expires_at": str(profile.get("expires_at") or ""),
            "message": message or "Live cluster connectivity verified.",
            "error": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "connection_id": str(profile.get("connection_id") or ""),
            "cluster_url": str(profile.get("cluster_url") or ""),
            "auth_mode": str(profile.get("auth_mode") or "token"),
            "resolved_user": "",
            "resolved_groups": [],
            "resolved_roles": [],
            "identity_source": "live_api",
            "permission_hints": {"can_view_namespaces": False, "can_view_resources": False},
            "rbac_evidence": [],
            "rbac_rules_incomplete": True,
            "rbac_evaluation_error": str(exc),
            "secret_backend": "local_artifact_store",
            "secret_version": "1",
            "secret_created_at": _iso(now),
            "secret_lease_renewable": False,
            "secret_lease_ttl_seconds": 0,
            "secret_lease_expires_at": str(profile.get("expires_at") or ""),
            "secret_rotation_supported": False,
            "secret_auto_renew_applied": False,
            "secret_auto_renew_threshold_seconds": 0,
            "secret_renew_message": "Lease automation is not wired in this baseline yet.",
            "resolved_namespace": str(profile.get("default_namespace") or ""),
            "expires_at": str(profile.get("expires_at") or ""),
            "message": "",
            "error": str(exc),
        }


def build_status_response(profile: dict[str, Any] | None, *, message: str) -> dict[str, Any]:
    return {
        "connected": profile is not None,
        "connection": profile,
        "message": message,
    }


def build_lease_status() -> dict[str, Any]:
    return {
        "enabled": False,
        "running": False,
        "interval_seconds": 0,
        "last_run_at": "",
        "last_success_at": "",
        "last_failure_at": "",
        "last_error": "",
        "consecutive_failures": 0,
        "next_run_delay_seconds": 0,
        "alert_level": "none",
        "profiles_checked": 0,
        "renewals_applied": 0,
        "recent_failures": [],
        "alert_delivery_enabled": False,
        "alert_target": "",
        "alert_dispatch_count": 0,
        "last_alert_at": "",
        "last_alert_level": "none",
        "last_alert_status": "",
        "last_alert_error": "",
    }


def _stable_seed(profile: dict[str, Any]) -> int:
    base = "|".join(
        [
            str(profile.get("connection_id") or ""),
            str(profile.get("workspace_id") or ""),
            str(profile.get("cluster_url") or ""),
            str(profile.get("default_namespace") or ""),
        ]
    )
    return sum(ord(char) for char in base)


def _synthetic_overview(profile: dict[str, Any]) -> dict[str, Any]:
    seed = _stable_seed(profile)
    namespace = str(profile.get("default_namespace") or "").strip()
    namespace_sample = [item for item in [namespace, "default", "openshift-monitoring", "openshift-ingress", "openshift-config"] if item]
    namespace_sample = list(dict.fromkeys(namespace_sample))[:5]
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "default_namespace": namespace,
        "namespace_count": 6 + (seed % 5),
        "namespace_sample": namespace_sample,
        "resource_counts": {
            "nodes": 3 + (seed % 4),
            "pods": 24 + (seed % 18),
            "deployments": 4 + (seed % 7),
            "services": 6 + (seed % 8),
            "routes": 2 + (seed % 5),
        },
        "message": "Synthetic overview generated from the stored connection profile.",
    }


def build_overview(root_dir: Path, profile: dict[str, Any]) -> dict[str, Any]:
    if _use_synthetic(profile):
        return _synthetic_overview(profile)
    namespaces = build_namespaces(root_dir, profile)
    namespace = str(profile.get("default_namespace") or "").strip() or (namespaces["items"][0] if namespaces["items"] else "")
    resource_counts: dict[str, int] = {}
    if namespace:
        for resource in ("pods", "deployments", "services", "routes", "events"):
            resource_counts[resource] = int(list_resources(root_dir, profile, resource=resource, namespace=namespace)["count"])
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "default_namespace": namespace,
        "namespace_count": namespaces["count"],
        "namespace_sample": namespaces["items"][:8],
        "resource_counts": resource_counts,
        "message": "Overview loaded from live cluster.",
    }


def build_dashboard_metrics(root_dir: Path, profile: dict[str, Any], *, window: str, step: str) -> dict[str, Any]:
    del root_dir
    seed = _stable_seed(profile)
    base_timestamp = int(_now().timestamp())
    points = 12

    def series(metric_id: str, label: str, unit: str, current: float, capacity: float) -> dict[str, Any]:
        values = []
        for index in range(points):
            wave = ((seed + index * 17) % 11) - 5
            value = max(0.0, current + wave)
            values.append({"timestamp": base_timestamp - ((points - index) * 300), "value": round(value, 2)})
        return {
            "metric_id": metric_id,
            "label": label,
            "unit": unit,
            "current_value": round(current, 2),
            "capacity_value": round(capacity, 2),
            "available_value": round(max(capacity - current, 0.0), 2),
            "points": values,
        }

    cpu_current = 48 + (seed % 18)
    memory_current = 62 + (seed % 14)
    replica_pressure = 2 + (seed % 4)
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "window": window,
        "step": step,
        "series": [
            series("cpu_usage", "CPU Usage", "%", float(cpu_current), 100.0),
            series("memory_usage", "Memory Usage", "%", float(memory_current), 100.0),
            series("replica_pressure", "Replica Pressure", "pods", float(replica_pressure), 10.0),
        ],
    }


def _synthetic_namespaces(profile: dict[str, Any]) -> dict[str, Any]:
    default_namespace = str(profile.get("default_namespace") or "").strip()
    items = [item for item in [default_namespace, "default", "openshift-monitoring", "openshift-ingress", "openshift-config", "openshift-operators"] if item]
    items = list(dict.fromkeys(items))
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "count": len(items),
        "items": items,
    }


def build_namespaces(root_dir: Path, profile: dict[str, Any]) -> dict[str, Any]:
    if _use_synthetic(profile):
        return _synthetic_namespaces(profile)
    default_namespace = str(profile.get("default_namespace") or "").strip()
    try:
        payload = _request_json(root_dir, profile, "GET", "/api/v1/namespaces")
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        if response is not None and response.status_code == 403 and default_namespace:
            return {
                "connection_id": str(profile.get("connection_id") or ""),
                "cluster_url": str(profile.get("cluster_url") or ""),
                "count": 1,
                "items": [default_namespace],
            }
        raise
    items = [
        str((item.get("metadata", {}) or {}).get("name") or "").strip()
        for item in payload.get("items", []) or []
    ]
    items = [item for item in items if item]
    if not items and default_namespace:
        items = [default_namespace]
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "count": len(items),
        "items": items,
    }


def _synthetic_resource_seed(profile: dict[str, Any], *, namespace: str, resource: str) -> int:
    return _stable_seed(profile) + sum(ord(char) for char in f"{namespace}|{resource}")


def _synthetic_resource_count(seed: int, resource: str) -> int:
    match resource:
        case "pods":
            return 6 + (seed % 6)
        case "deployments":
            return 3 + (seed % 4)
        case "services":
            return 2 + (seed % 5)
        case "routes":
            return 1 + (seed % 4)
        case "events":
            return 4 + (seed % 5)
        case _:
            return 0


def _synthetic_resource_name(resource: str, index: int) -> str:
    match resource:
        case "pods":
            return f"ops-pod-{index:02d}"
        case "deployments":
            return f"ops-deployment-{index:02d}"
        case "services":
            return f"ops-service-{index:02d}"
        case "routes":
            return f"ops-route-{index:02d}"
        case "events":
            return f"ops-event-{index:02d}"
        case _:
            return f"{resource}-{index:02d}"


def _synthetic_list_resources(profile: dict[str, Any], *, resource: str, namespace: str) -> dict[str, Any]:
    seed = _synthetic_resource_seed(profile, namespace=namespace, resource=resource)
    count = _synthetic_resource_count(seed, resource)
    items = []
    for index in range(1, count + 1):
        phase = "Running"
        kind = _RESOURCE_CONFIG[resource]["kind"]
        if resource == "events":
            phase = "Normal" if index % 2 else "Warning"
        ready_replicas = 1 + ((seed + index) % 3) if resource == "deployments" else 0
        replicas = ready_replicas + ((seed + index) % 2) if resource == "deployments" else 0
        items.append(
            {
                "name": _synthetic_resource_name(resource, index),
                "namespace": namespace,
                "kind": kind,
                "created_at": _iso(_now() - timedelta(minutes=index * 11)),
                "phase": phase,
                "node_name": f"worker-{((seed + index) % 3) + 1}" if resource == "pods" else "",
                "ready_replicas": ready_replicas,
                "replicas": replicas,
                "type": "ClusterIP" if resource == "services" else "",
                "cluster_ip": f"172.30.{(seed + index) % 10}.{10 + index}" if resource == "services" else "",
                "host": f"{namespace}-{index}.apps.cluster.example.com" if resource == "routes" else "",
                "to": f"ops-service-{index:02d}" if resource == "routes" else "",
            }
        )
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "resource": resource,
        "namespace": namespace,
        "count": len(items),
        "items": items,
    }


def list_resources(root_dir: Path, profile: dict[str, Any], *, resource: str, namespace: str) -> dict[str, Any]:
    if resource not in _RESOURCE_CONFIG:
        raise ValueError(f"unsupported resource: {resource}")
    if _use_synthetic(profile):
        return _synthetic_list_resources(profile, resource=resource, namespace=namespace)
    resolved_namespace = namespace or str(profile.get("default_namespace") or "").strip()
    if not resolved_namespace:
        raise ValueError("namespace is required")
    path = _RESOURCE_CONFIG[resource]["path"].format(namespace=resolved_namespace)
    payload = _request_json(root_dir, profile, "GET", path)
    items = [_summarize_resource(resource, item) for item in payload.get("items", []) or []]
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "resource": resource,
        "namespace": resolved_namespace,
        "count": len(items),
        "items": items,
    }


def _synthetic_get_resource_detail(profile: dict[str, Any], *, resource: str, namespace: str, name: str) -> dict[str, Any]:
    listing = _synthetic_list_resources(profile, resource=resource, namespace=namespace)
    matched = next((item for item in listing["items"] if str(item.get("name") or "") == name), None)
    if matched is None:
        raise LookupError("Resource not found.")
    manifest: dict[str, Any] = {
        "apiVersion": "v1" if resource in {"pods", "services", "events"} else "apps/v1" if resource == "deployments" else "route.openshift.io/v1",
        "kind": matched["kind"],
        "metadata": {
            "name": matched["name"],
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": matched["name"],
                "ops.playbookstudio.io/profile": str(profile.get("connection_id") or ""),
            },
        },
        "spec": {"resource": resource, "namespace": namespace},
        "status": {"phase": matched["phase"]},
    }
    if resource == "deployments":
        manifest["spec"] = {**manifest["spec"], "replicas": matched["replicas"], "selector": {"matchLabels": {"app": matched["name"]}}}
        manifest["status"] = {**manifest["status"], "readyReplicas": matched["ready_replicas"], "replicas": matched["replicas"]}
    if resource == "services":
        manifest["spec"] = {**manifest["spec"], "type": matched["type"], "clusterIP": matched["cluster_ip"]}
    if resource == "routes":
        manifest["spec"] = {**manifest["spec"], "host": matched["host"], "to": {"name": matched["to"]}}
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "resource": resource,
        "namespace": namespace,
        "name": matched["name"],
        "kind": matched["kind"],
        "manifest_yaml": json.dumps(manifest, ensure_ascii=False, indent=2),
        "manifest_json": manifest,
    }


def get_resource_detail(root_dir: Path, profile: dict[str, Any], *, resource: str, namespace: str, name: str) -> dict[str, Any]:
    if _use_synthetic(profile):
        return _synthetic_get_resource_detail(profile, resource=resource, namespace=namespace, name=name)
    resolved_namespace = namespace or str(profile.get("default_namespace") or "").strip()
    if not resolved_namespace:
        raise ValueError("namespace is required")
    if not name.strip():
        raise ValueError("name is required")
    path = f"{_RESOURCE_CONFIG[resource]['path'].format(namespace=resolved_namespace)}/{name}"
    payload = _request_json(root_dir, profile, "GET", path)
    summary = _summarize_resource(resource, payload)
    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "resource": resource,
        "namespace": resolved_namespace,
        "name": summary["name"],
        "kind": summary["kind"],
        "manifest_yaml": _dump_yaml(payload),
        "manifest_json": payload,
    }


def build_ops_chat_response(
    root_dir: Path,
    profile: dict[str, Any],
    *,
    message: str,
    namespace: str = "",
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    del history
    normalized = str(message or "").strip().lower()
    namespaces = build_namespaces(root_dir, profile)
    resolved_namespace = namespace.strip() or str(profile.get("default_namespace") or "").strip() or (namespaces["items"][0] if namespaces["items"] else "")
    resource_hint_present = any(
        token in normalized
        for token in ("pod", "pods", "deployment", "deployments", "service", "services", "route", "routes", "event", "events")
    )

    if any(token in normalized for token in ("namespace", "namespaces")) and not resource_hint_present:
        items = namespaces["items"][:5]
        answer = (
            f"{namespaces['count']} namespaces are visible for the current connection profile. Sample namespaces: {', '.join(items)}."
            if items
            else "No namespaces are visible for the current connection profile."
        )
        return {
            "connection_id": str(profile.get("connection_id") or ""),
            "cluster_url": str(profile.get("cluster_url") or ""),
            "mode": "namespace_list",
            "resource": "",
            "namespace": resolved_namespace,
            "answer": answer,
            "items": [],
        }

    resource = "pods"
    if any(token in normalized for token in ("deployment", "deployments")):
        resource = "deployments"
    elif any(token in normalized for token in ("service", "services")):
        resource = "services"
    elif any(token in normalized for token in ("route", "routes")):
        resource = "routes"
    elif any(token in normalized for token in ("event", "events")):
        resource = "events"

    listing = list_resources(root_dir, profile, resource=resource, namespace=resolved_namespace)
    items = listing["items"][:5]
    summary_names = ", ".join(str(item.get("name") or "") for item in items if str(item.get("name") or "").strip())
    count = int(listing.get("count") or 0)
    answer = (
        f"I found {count} {resource} in namespace {resolved_namespace}. Representative items: {summary_names}."
        if items
        else f"No {resource} were found in namespace {resolved_namespace}."
    )

    if any(token in normalized for token in ("yaml", "manifest", "detail")) and items:
        first_name = str(items[0].get("name") or "")
        detail = get_resource_detail(root_dir, profile, resource=resource, namespace=resolved_namespace, name=first_name)
        answer += f" The manifest for {first_name} is available in the sidecar."
        return {
            "connection_id": str(profile.get("connection_id") or ""),
            "cluster_url": str(profile.get("cluster_url") or ""),
            "mode": "resource_detail",
            "resource": resource,
            "namespace": resolved_namespace,
            "answer": answer,
            "items": items,
            "detail": detail,
        }

    return {
        "connection_id": str(profile.get("connection_id") or ""),
        "cluster_url": str(profile.get("cluster_url") or ""),
        "mode": "resource_list",
        "resource": resource,
        "namespace": resolved_namespace,
        "answer": answer,
        "items": items,
    }


__all__ = [
    "build_lease_status",
    "build_dashboard_metrics",
    "build_namespaces",
    "build_ops_chat_response",
    "build_overview",
    "build_status_response",
    "build_test_result",
    "create_profile",
    "disconnect_profile",
    "get_profile",
    "get_resource_detail",
    "list_profiles",
    "list_resources",
]
