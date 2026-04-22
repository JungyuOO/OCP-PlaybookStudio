from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from play_book_studio.config.settings import load_settings

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _workspace_store_path(root_dir: Path) -> Path:
    settings = load_settings(root_dir)
    target_dir = settings.artifacts_dir / "ops"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "workspaces.json"


def _normalize_slug(value: str) -> str:
    normalized = _SLUG_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return normalized or "workspace"


def _workspace_document(root_dir: Path) -> dict[str, Any]:
    path = _workspace_store_path(root_dir)
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


def _save_workspace_document(root_dir: Path, payload: dict[str, Any]) -> None:
    path = _workspace_store_path(root_dir)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _workspace_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("name") or "").lower(), str(item.get("workspace_id") or "").lower())


def list_workspaces(root_dir: Path) -> dict[str, Any]:
    document = _workspace_document(root_dir)
    items = sorted(document["items"], key=_workspace_sort_key)
    return {
        "items": items,
        "updated_at": str(document.get("updated_at") or ""),
        "count": len(items),
    }


def get_workspace(root_dir: Path, workspace_id: str) -> dict[str, Any] | None:
    target_id = str(workspace_id or "").strip()
    if not target_id:
        return None
    document = _workspace_document(root_dir)
    for item in document["items"]:
        if str(item.get("workspace_id") or "") == target_id:
            return item
    return None


def create_workspace(root_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    environment = str(payload.get("environment") or "dev").strip().lower() or "dev"
    if environment not in _VALID_ENVIRONMENTS:
        raise ValueError("environment must be one of dev, staging, prod")

    document = _workspace_document(root_dir)
    items = document["items"]

    base_slug = _normalize_slug(str(payload.get("slug") or name))
    existing_slugs = {str(item.get("slug") or "").strip().lower() for item in items}
    slug = base_slug
    suffix = 2
    while slug in existing_slugs:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    timestamp = _now_iso()
    item = {
        "workspace_id": str(uuid.uuid4()),
        "name": name,
        "slug": slug,
        "industry": str(payload.get("industry") or "").strip(),
        "environment": environment,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    items.append(item)
    document["updated_at"] = timestamp
    _save_workspace_document(root_dir, document)
    return item


__all__ = ["create_workspace", "get_workspace", "list_workspaces"]
