from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from play_book_studio.config.settings import load_effective_env, load_settings

_PROVIDERS = {"github", "gitlab"}
_DELIVERY_MODES = {"gitops_commit", "cicd_pipeline"}
_MANIFEST_KINDS = {"config_yaml", "helm_values", "kustomize"}
_GITHUB_TOKEN_ENV_KEYS = ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_CLASSIC_TOKEN", "GITHUB_PAT")
_SCM_GITHUB_CLIENT_ID = "SCM_GITHUB_CLIENT_ID"
_SCM_GITHUB_CLIENT_SECRET = "SCM_GITHUB_CLIENT_SECRET"
_SCM_GITHUB_SCOPE = "SCM_GITHUB_SCOPE"
_SCM_GITHUB_AUTHORIZE_URL = "SCM_GITHUB_AUTHORIZE_URL"
_SCM_GITHUB_TOKEN_URL = "SCM_GITHUB_TOKEN_URL"
_SCM_GITHUB_USER_URL = "SCM_GITHUB_USER_URL"
_SCM_GITLAB_CLIENT_ID = "SCM_GITLAB_CLIENT_ID"
_SCM_GITLAB_CLIENT_SECRET = "SCM_GITLAB_CLIENT_SECRET"
_SCM_GITLAB_SCOPE = "SCM_GITLAB_SCOPE"
_SCM_GITLAB_AUTHORIZE_URL = "SCM_GITLAB_AUTHORIZE_URL"
_SCM_GITLAB_TOKEN_URL = "SCM_GITLAB_TOKEN_URL"
_SCM_GITLAB_USER_URL = "SCM_GITLAB_USER_URL"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ops_dir(root_dir: Path) -> Path:
    settings = load_settings(root_dir)
    target_dir = settings.artifacts_dir / "ops"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _document_path(root_dir: Path) -> Path:
    return _ops_dir(root_dir) / "scm.json"


def _secrets_path(root_dir: Path) -> Path:
    return _ops_dir(root_dir) / "scm-secrets.json"


def _oauth_state_path(root_dir: Path) -> Path:
    return _ops_dir(root_dir) / "scm-oauth-state.json"


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
    _secrets_path(root_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _store_secret(root_dir: Path, payload: dict[str, str]) -> str:
    secret_ref = f"ops://scm/secret/{uuid.uuid4().hex}"
    document = _read_secrets(root_dir)
    document[secret_ref] = payload
    _write_secrets(root_dir, document)
    return secret_ref


def _load_secret(root_dir: Path, secret_ref: str) -> dict[str, str]:
    return _read_secrets(root_dir).get(secret_ref, {})


def _read_oauth_state(root_dir: Path) -> dict[str, dict[str, str]]:
    path = _oauth_state_path(root_dir)
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


def _write_oauth_state(root_dir: Path, payload: dict[str, dict[str, str]]) -> None:
    _oauth_state_path(root_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _create_oauth_state(root_dir: Path, *, workspace_id: str, provider: str) -> str:
    state = f"scm-oauth-{uuid.uuid4().hex}"
    document = _read_oauth_state(root_dir)
    document[state] = {
        "workspace_id": workspace_id,
        "provider": provider,
        "created_at": _now_iso(),
    }
    _write_oauth_state(root_dir, document)
    return state


def _pop_oauth_state(root_dir: Path, state: str) -> dict[str, str] | None:
    document = _read_oauth_state(root_dir)
    payload = document.pop(state, None)
    _write_oauth_state(root_dir, document)
    return payload


def _oauth_provider_config(root_dir: Path, provider: str) -> dict[str, str]:
    env = load_effective_env(root_dir)
    if provider == "github":
        return {
            "client_id": str(env.get(_SCM_GITHUB_CLIENT_ID) or "").strip(),
            "client_secret": str(env.get(_SCM_GITHUB_CLIENT_SECRET) or "").strip(),
            "scope": str(env.get(_SCM_GITHUB_SCOPE) or "read:user repo").strip(),
            "authorize_url": str(env.get(_SCM_GITHUB_AUTHORIZE_URL) or "https://github.com/login/oauth/authorize").strip(),
            "token_url": str(env.get(_SCM_GITHUB_TOKEN_URL) or "https://github.com/login/oauth/access_token").strip(),
            "user_url": str(env.get(_SCM_GITHUB_USER_URL) or "https://api.github.com/user").strip(),
            "host_url": "https://github.com",
        }
    return {
        "client_id": str(env.get(_SCM_GITLAB_CLIENT_ID) or "").strip(),
        "client_secret": str(env.get(_SCM_GITLAB_CLIENT_SECRET) or "").strip(),
        "scope": str(env.get(_SCM_GITLAB_SCOPE) or "read_user api").strip(),
        "authorize_url": str(env.get(_SCM_GITLAB_AUTHORIZE_URL) or "https://gitlab.com/oauth/authorize").strip(),
        "token_url": str(env.get(_SCM_GITLAB_TOKEN_URL) or "https://gitlab.com/oauth/token").strip(),
        "user_url": str(env.get(_SCM_GITLAB_USER_URL) or "https://gitlab.com/api/v4/user").strip(),
        "host_url": "https://gitlab.com",
    }


def oauth_is_configured(root_dir: Path, provider: str) -> bool:
    config = _oauth_provider_config(root_dir, provider)
    return bool(config["client_id"] and config["client_secret"])


def build_oauth_authorize_url(root_dir: Path, *, provider: str, workspace_id: str, callback_url: str) -> tuple[str, str]:
    config = _oauth_provider_config(root_dir, provider)
    if not config["client_id"] or not config["client_secret"]:
        raise ValueError(f"{provider} OAuth is not configured.")
    state = _create_oauth_state(root_dir, workspace_id=workspace_id, provider=provider)
    query = urlencode(
        {
            "client_id": config["client_id"],
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": config["scope"],
            "state": state,
        }
    )
    return f"{config['authorize_url']}?{query}", state


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


def _github_headers_for_connection(root_dir: Path, connection: dict[str, Any]) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OCP-PlaybookStudio/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    secret = _load_secret(root_dir, str(connection.get("secret_ref") or ""))
    token = str(secret.get("access_token") or "").strip() or _github_token(root_dir)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _gitlab_headers_for_connection(root_dir: Path, connection: dict[str, Any]) -> dict[str, str]:
    secret = _load_secret(root_dir, str(connection.get("secret_ref") or ""))
    token = str(secret.get("access_token") or secret.get("token") or "").strip()
    headers = {
        "Accept": "application/json",
        "User-Agent": "OCP-PlaybookStudio/1.0",
    }
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


def _fetch_github_repo_for_connection(root_dir: Path, connection: dict[str, Any], repo_full_name: str) -> dict[str, Any]:
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}",
        headers=_github_headers_for_connection(root_dir, connection),
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


def _github_content_exists_for_connection(root_dir: Path, connection: dict[str, Any], repo_full_name: str, ref: str, path: str) -> bool:
    target_path = str(path or "").strip().strip("/")
    if not target_path:
        return False
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/contents/{target_path}",
        headers=_github_headers_for_connection(root_dir, connection),
        params={"ref": ref},
        timeout=15,
    )
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def discover_repositories(
    root_dir: Path,
    *,
    workspace_id: str,
    connection_id: str,
    query: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    connection = get_connection(root_dir, connection_id)
    if connection is None or str(connection.get("workspace_id") or "") != workspace_id:
        raise LookupError("SCM connection not found.")

    provider = str(connection.get("provider") or "").strip().lower()
    normalized_query = str(query or "").strip().lower()
    max_items = max(1, min(limit, 100))

    if provider == "github" and str(connection.get("host_url") or "").rstrip("/") == "https://github.com":
        response = requests.get(
            "https://api.github.com/user/repos",
            headers=_github_headers_for_connection(root_dir, connection),
            params={"per_page": max_items, "sort": "updated", "affiliation": "owner,collaborator,organization_member"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json() if response.content else []
        repos = payload if isinstance(payload, list) else []
        items = []
        for repo in repos:
            if not isinstance(repo, dict):
                continue
            full_name = str(repo.get("full_name") or "").strip()
            if not full_name:
                continue
            if normalized_query and normalized_query not in full_name.lower() and normalized_query not in str(repo.get("name") or "").lower():
                continue
            items.append(
                {
                    "provider": "github",
                    "external_id": str(repo.get("id") or ""),
                    "full_name": full_name,
                    "name": str(repo.get("name") or ""),
                    "default_branch": str(repo.get("default_branch") or "main"),
                    "web_url": str(repo.get("html_url") or ""),
                    "visibility": "private" if bool(repo.get("private")) else "public",
                }
            )
        return {"items": items[:max_items]}

    if provider == "gitlab":
        base = str(connection.get("host_url") or "").rstrip("/")
        response = requests.get(
            f"{base}/api/v4/projects",
            headers=_gitlab_headers_for_connection(root_dir, connection),
            params={"membership": "true", "simple": "true", "per_page": max_items, "search": query},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json() if response.content else []
        repos = payload if isinstance(payload, list) else []
        items = []
        for repo in repos:
            if not isinstance(repo, dict):
                continue
            full_name = str(repo.get("path_with_namespace") or "").strip()
            if not full_name:
                continue
            items.append(
                {
                    "provider": "gitlab",
                    "external_id": str(repo.get("id") or ""),
                    "full_name": full_name,
                    "name": str(repo.get("name") or ""),
                    "default_branch": str(repo.get("default_branch") or "main"),
                    "web_url": str(repo.get("web_url") or ""),
                    "visibility": str(repo.get("visibility") or ""),
                }
            )
        return {"items": items[:max_items]}

    raise ValueError("Real repository discovery is currently supported for GitHub.com and GitLab OAuth connections.")


def _candidate_manifest_kind(path: str) -> str:
    normalized = str(path or "").strip().lower()
    if normalized.endswith(("values.yaml", "values.yml")):
        return "helm_values"
    if normalized.endswith(("kustomization.yaml", "kustomization.yml")):
        return "kustomize"
    return "config_yaml"


def _candidate_score(path: str) -> int:
    normalized = str(path or "").strip().lower()
    score = 0
    if normalized == "config.yaml" or normalized == "config.yml":
        score += 200
    if normalized.endswith("config.yaml") or normalized.endswith("config.yml"):
        score += 100
    if normalized.endswith("values.yaml") or normalized.endswith("values.yml"):
        score += 90
    if normalized.endswith("kustomization.yaml") or normalized.endswith("kustomization.yml"):
        score += 85
    if "/deploy/" in normalized or "/deployment/" in normalized:
        score += 25
    if "/charts/" in normalized or "/helm/" in normalized:
        score += 20
    if "/kustomize/" in normalized or "/overlays/" in normalized:
        score += 20
    if normalized.count("/") < 4:
        score += 10
    return score


def discover_config_paths(
    root_dir: Path,
    *,
    workspace_id: str,
    connection_id: str,
    repo_full_name: str,
    ref: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    connection = get_connection(root_dir, connection_id)
    if connection is None or str(connection.get("workspace_id") or "") != workspace_id:
        raise LookupError("SCM connection not found.")

    provider = str(connection.get("provider") or "").strip().lower()
    branch = ref.strip() or "main"
    candidates: list[dict[str, Any]] = []
    max_items = max(1, min(limit, 50))

    if provider == "github" and str(connection.get("host_url") or "").rstrip("/") == "https://github.com":
        tree_response = requests.get(
            f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}",
            headers=_github_headers_for_connection(root_dir, connection),
            params={"recursive": "1"},
            timeout=20,
        )
        tree_response.raise_for_status()
        payload = tree_response.json() if tree_response.content else {}
        entries = payload.get("tree") if isinstance(payload, dict) else []
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict) or str(entry.get("type") or "") != "blob":
                continue
            path = str(entry.get("path") or "").strip()
            if not path:
                continue
            manifest_kind = _candidate_manifest_kind(path)
            if manifest_kind == "config_yaml" and not path.lower().endswith((".yaml", ".yml")):
                continue
            candidates.append(
                {
                    "path": path,
                    "manifest_kind": manifest_kind,
                    "score": _candidate_score(path),
                }
            )
    elif provider == "gitlab":
        base = str(connection.get("host_url") or "").rstrip("/")
        project_id = requests.utils.quote(repo_full_name, safe="")
        tree_response = requests.get(
            f"{base}/api/v4/projects/{project_id}/repository/tree",
            headers=_gitlab_headers_for_connection(root_dir, connection),
            params={"recursive": "true", "ref": branch, "per_page": 100},
            timeout=20,
        )
        tree_response.raise_for_status()
        entries = tree_response.json() if tree_response.content else []
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict) or str(entry.get("type") or "") != "blob":
                continue
            path = str(entry.get("path") or "").strip()
            if not path:
                continue
            manifest_kind = _candidate_manifest_kind(path)
            if manifest_kind == "config_yaml" and not path.lower().endswith((".yaml", ".yml")):
                continue
            candidates.append(
                {
                    "path": path,
                    "manifest_kind": manifest_kind,
                    "score": _candidate_score(path),
                }
            )
    else:
        raise ValueError("Real config-path discovery is currently supported for GitHub.com and GitLab OAuth connections.")

    candidates.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("path") or "")))
    return {
        "items": candidates[:max_items],
    }


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


def complete_oauth_callback(root_dir: Path, *, provider: str, code: str, state: str, callback_url: str) -> dict[str, Any]:
    pending = _pop_oauth_state(root_dir, state)
    if pending is None or str(pending.get("provider") or "") != provider:
        raise ValueError("OAuth state is invalid or expired.")

    config = _oauth_provider_config(root_dir, provider)
    if not config["client_id"] or not config["client_secret"]:
        raise ValueError(f"{provider} OAuth is not configured.")

    token_response = requests.post(
        config["token_url"],
        headers={"Accept": "application/json"},
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": callback_url,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    token_response.raise_for_status()
    token_payload = token_response.json() if token_response.content else {}
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise ValueError("OAuth token exchange did not return an access token.")

    user_response = requests.get(
        config["user_url"],
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    user_response.raise_for_status()
    user_payload = user_response.json() if user_response.content else {}
    login_name = str(user_payload.get("login") or user_payload.get("username") or "").strip()
    account_label = str(user_payload.get("name") or login_name or f"{provider} account").strip()
    scopes = [scope for scope in str(token_payload.get("scope") or config["scope"]).replace(",", " ").split() if scope]
    secret_ref = _store_secret(
        root_dir,
        {
          "provider": provider,
          "access_token": access_token,
          "refresh_token": str(token_payload.get("refresh_token") or "").strip(),
          "token_type": str(token_payload.get("token_type") or "Bearer").strip(),
          "scope": str(token_payload.get("scope") or config["scope"]).strip(),
        },
    )

    timestamp = _now_iso()
    item = {
        "scm_connection_id": f"scm-{uuid.uuid4().hex}",
        "workspace_id": str(pending.get("workspace_id") or "").strip(),
        "provider": provider,
        "host_url": config["host_url"],
        "auth_type": "oauth",
        "account_label": account_label,
        "login_name": login_name,
        "scopes": scopes,
        "secret_ref": secret_ref,
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
        repo_payload = _fetch_github_repo_for_connection(root_dir, connection, repo_full_name)
        default_branch = str(repo_payload.get("default_branch") or default_branch).strip() or default_branch
        sync_status = "config_found" if _github_content_exists_for_connection(root_dir, connection, repo_full_name, default_branch, config_path) else "config_missing"
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
            repo_payload = _fetch_github_repo_for_connection(root_dir, connection, str(item.get("repo_full_name") or ""))
            item["default_branch"] = str(repo_payload.get("default_branch") or item.get("default_branch") or "main").strip() or "main"
            item["sync_status"] = (
                "config_found"
                if _github_content_exists_for_connection(root_dir, connection, str(item.get("repo_full_name") or ""), str(item.get("default_branch") or "main"), str(item.get("config_path") or ""))
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
    "build_oauth_authorize_url",
    "build_deployment_plan",
    "complete_oauth_callback",
    "create_connection",
    "create_repository",
    "discover_config_paths",
    "discover_repositories",
    "get_connection",
    "get_repository",
    "list_connections",
    "list_repositories",
    "oauth_is_configured",
    "update_repository",
]
