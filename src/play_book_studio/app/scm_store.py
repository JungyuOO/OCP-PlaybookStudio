from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from play_book_studio.config.settings import load_effective_env, load_settings

_PROVIDERS = {"github", "gitlab"}
_DELIVERY_MODES = {"gitops_commit", "cicd_pipeline"}
_MANIFEST_KINDS = {"config_yaml", "helm_values", "kustomize"}
_GITHUB_TOKEN_ENV_KEYS = ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_CLASSIC_TOKEN", "GITHUB_PAT")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _document_path(root_dir: Path) -> Path:
    settings = load_settings(root_dir)
    target_dir = settings.artifacts_dir / "ops"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "scm.json"


def _read_document(root_dir: Path) -> dict[str, Any]:
    path = _document_path(root_dir)
    if not path.exists():
        return {"version": 1, "updated_at": "", "connections": [], "repositories": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "updated_at": "", "connections": [], "repositories": []}
    return {
        "version": 1,
        "updated_at": str(payload.get("updated_at") or ""),
        "connections": [dict(item) for item in payload.get("connections", []) if isinstance(item, dict)],
        "repositories": [dict(item) for item in payload.get("repositories", []) if isinstance(item, dict)],
    }


def _write_document(root_dir: Path, payload: dict[str, Any]) -> None:
    _document_path(root_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _github_token(root_dir: Path) -> str:
    effective_env = load_effective_env(root_dir)
    for key in _GITHUB_TOKEN_ENV_KEYS:
        token = str(effective_env.get(key) or "").strip()
        if token:
            return token
    return ""


def _github_headers(root_dir: Path) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OCP-PlaybookStudio/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _github_token(root_dir)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_github_repo(root_dir: Path, repo_full_name: str) -> dict[str, Any]:
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}",
        headers=_github_headers(root_dir),
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _github_content_exists(root_dir: Path, repo_full_name: str, ref: str, path: str) -> bool:
    target_path = str(path or "").strip().strip("/")
    if not target_path:
        return False
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/contents/{target_path}",
        headers=_github_headers(root_dir),
        params={"ref": ref},
        timeout=15,
    )
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def list_connections(root_dir: Path, workspace_id: str) -> dict[str, Any]:
    document = _read_document(root_dir)
    items = [item for item in document["connections"] if str(item.get("workspace_id") or "") == workspace_id]
    return {"items": items}


def create_connection(root_dir: Path, workspace_id: str, payload: dict[str, Any], *, auth_type_override: str | None = None) -> dict[str, Any]:
    provider = str(payload.get("provider") or "").strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError("provider must be github or gitlab")
    host_url = str(payload.get("host_url") or "").strip() or ("https://gitlab.com" if provider == "gitlab" else "https://github.com")
    auth_type = str(auth_type_override or payload.get("auth_type") or "token").strip() or "token"
    account_label = str(payload.get("account_label") or "").strip() or f"{provider}-account"
    timestamp = _now_iso()
    item = {
        "scm_connection_id": f"scm-{uuid.uuid4().hex}",
        "workspace_id": workspace_id,
        "provider": provider,
        "host_url": host_url,
        "auth_type": auth_type,
        "account_label": account_label,
        "login_name": account_label.replace(" ", "-").lower(),
        "scopes": ["repo", "read:org"] if provider == "github" else ["api", "read_repository"],
        "secret_ref": f"ops://scm/{provider}/{uuid.uuid4().hex}",
        "status": "connected",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    document = _read_document(root_dir)
    document["connections"].insert(0, item)
    document["updated_at"] = timestamp
    _write_document(root_dir, document)
    return item


def get_connection(root_dir: Path, connection_id: str) -> dict[str, Any] | None:
    document = _read_document(root_dir)
    for item in document["connections"]:
        if str(item.get("scm_connection_id") or "") == connection_id:
            return item
    return None


def list_repositories(root_dir: Path, workspace_id: str) -> dict[str, Any]:
    document = _read_document(root_dir)
    items = [item for item in document["repositories"] if str(item.get("workspace_id") or "") == workspace_id]
    return {"items": items}


def create_repository(root_dir: Path, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    connection_id = str(payload.get("scm_connection_id") or "").strip()
    if not connection_id:
        raise ValueError("scm_connection_id is required")
    repo_full_name = str(payload.get("repo_full_name") or "").strip()
    if not repo_full_name:
        raise ValueError("repo_full_name is required")
    delivery_mode = str(payload.get("delivery_mode") or "gitops_commit").strip()
    manifest_kind = str(payload.get("manifest_kind") or "config_yaml").strip()
    if delivery_mode not in _DELIVERY_MODES:
        raise ValueError("delivery_mode must be gitops_commit or cicd_pipeline")
    if manifest_kind not in _MANIFEST_KINDS:
        raise ValueError("manifest_kind must be config_yaml, helm_values, or kustomize")
    connection = get_connection(root_dir, connection_id)
    if connection is None:
        raise LookupError("SCM connection not found.")
    default_branch = str(payload.get("default_branch") or "main").strip() or "main"
    config_path = str(payload.get("config_path") or "config.yaml").strip() or "config.yaml"
    sync_status = "connected"
    if str(connection.get("provider") or "") == "github" and str(connection.get("host_url") or "").rstrip("/") == "https://github.com":
        repo_payload = _fetch_github_repo(root_dir, repo_full_name)
        default_branch = str(repo_payload.get("default_branch") or default_branch).strip() or default_branch
        sync_status = "config_found" if _github_content_exists(root_dir, repo_full_name, default_branch, config_path) else "config_missing"
    timestamp = _now_iso()
    item = {
        "repository_id": f"repo-{uuid.uuid4().hex}",
        "workspace_id": workspace_id,
        "scm_connection_id": connection_id,
        "repo_full_name": repo_full_name,
        "default_branch": default_branch,
        "config_path": config_path,
        "delivery_mode": delivery_mode,
        "manifest_kind": manifest_kind,
        "target_cluster_url": str(payload.get("target_cluster_url") or "").strip(),
        "target_namespace": str(payload.get("target_namespace") or "default").strip() or "default",
        "auto_deploy_enabled": bool(payload.get("auto_deploy_enabled", True)),
        "sync_status": sync_status,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    document = _read_document(root_dir)
    document["repositories"].insert(0, item)
    document["updated_at"] = timestamp
    _write_document(root_dir, document)
    return item


def get_repository(root_dir: Path, repository_id: str) -> dict[str, Any] | None:
    document = _read_document(root_dir)
    for item in document["repositories"]:
        if str(item.get("repository_id") or "") == repository_id:
            return item
    return None


def update_repository(root_dir: Path, repository_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    document = _read_document(root_dir)
    for item in document["repositories"]:
        if str(item.get("repository_id") or "") != repository_id:
            continue
        for source_key, target_key in (
            ("default_branch", "default_branch"),
            ("config_path", "config_path"),
            ("delivery_mode", "delivery_mode"),
            ("manifest_kind", "manifest_kind"),
            ("target_cluster_url", "target_cluster_url"),
            ("target_namespace", "target_namespace"),
        ):
            value = payload.get(source_key)
            if isinstance(value, str) and value.strip():
                item[target_key] = value.strip()
        if isinstance(payload.get("auto_deploy_enabled"), bool):
            item["auto_deploy_enabled"] = bool(payload["auto_deploy_enabled"])
        connection = get_connection(root_dir, str(item.get("scm_connection_id") or ""))
        if connection and str(connection.get("provider") or "") == "github" and str(connection.get("host_url") or "").rstrip("/") == "https://github.com":
            repo_payload = _fetch_github_repo(root_dir, str(item.get("repo_full_name") or ""))
            item["default_branch"] = str(repo_payload.get("default_branch") or item.get("default_branch") or "main").strip() or "main"
            item["sync_status"] = (
                "config_found"
                if _github_content_exists(root_dir, str(item.get("repo_full_name") or ""), str(item.get("default_branch") or "main"), str(item.get("config_path") or ""))
                else "config_missing"
            )
        item["updated_at"] = _now_iso()
        document["updated_at"] = item["updated_at"]
        _write_document(root_dir, document)
        return item
    raise LookupError("Repository not found.")


def build_deployment_plan(repository: dict[str, Any], workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    target_namespace = str(payload.get("target_namespace") or repository.get("target_namespace") or "default").strip() or "default"
    resource_kind = str(payload.get("resource_kind") or "Deployment").strip() or "Deployment"
    resource_name = str(payload.get("resource_name") or "").strip()
    replicas = payload.get("replicas")
    image_tag = str(payload.get("image_tag") or "").strip()
    config_key = str(payload.get("config_key") or "replicas").strip() or "replicas"
    delivery_mode = str(repository.get("delivery_mode") or "gitops_commit")
    trigger_kind = "gitops_sync" if delivery_mode == "gitops_commit" else "cicd_pipeline"

    suggested_updates: list[str] = []
    if replicas is not None:
        suggested_updates.append(f"Set `{config_key}: {replicas}` in `{repository['config_path']}`.")
    if image_tag:
        suggested_updates.append(f"Update image tag to `{image_tag}` in `{repository['config_path']}`.")
    if not suggested_updates:
        suggested_updates.append(f"Update `{repository['config_path']}` for `{resource_kind}/{resource_name}`.")

    return {
        "repository_id": repository["repository_id"],
        "workspace_id": workspace_id,
        "repo_full_name": repository["repo_full_name"],
        "default_branch": repository["default_branch"],
        "config_path": repository["config_path"],
        "delivery_mode": repository["delivery_mode"],
        "manifest_kind": repository["manifest_kind"],
        "target_cluster_url": repository["target_cluster_url"],
        "target_namespace": target_namespace,
        "auto_deploy_enabled": repository["auto_deploy_enabled"],
        "files_to_change": [repository["config_path"]],
        "suggested_updates": suggested_updates,
        "trigger_kind": trigger_kind,
        "summary": f"Modify `{repository['repo_full_name']}` so {resource_kind} `{resource_name}` deploys into `{target_namespace}` via {trigger_kind}.",
        "commit_title": f"deploy: update {resource_name} delivery config",
        "commit_body": f"Workspace `{workspace_id}` uses repo-driven delivery.\nUpdate `{repository['config_path']}` instead of applying live cluster YAML.",
        "requires_pull_request": True,
        "next_step": "Open a commit or pull request so the repository-driven delivery lane can roll the change forward.",
    }


__all__ = [
    "build_deployment_plan",
    "create_connection",
    "create_repository",
    "get_connection",
    "get_repository",
    "list_connections",
    "list_repositories",
    "update_repository",
]
