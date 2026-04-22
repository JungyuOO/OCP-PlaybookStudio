from __future__ import annotations

import json
import re
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import requests

from play_book_studio.app.customer_pack_read_boundary import (
    blocked_customer_pack_draft_ids_from_payload,
    sanitize_debug_chat_log_entry,
)
from play_book_studio.app.data_control_room import build_data_control_room_payload
from play_book_studio.app.data_control_room_detail import (
    build_data_control_room_chunk_payload,
)
from play_book_studio.app.server_routes_customer_pack import (
    _customer_pack_read_allowed,
    _send_customer_pack_read_blocked,
)
from play_book_studio.app.repository_registry import (
    list_repository_favorites as _list_repository_favorites,
    remove_repository_favorite as _remove_repository_favorite,
    save_repository_favorites as _save_repository_favorites,
    search_github_repositories as _search_github_repositories,
)
from play_book_studio.app.connection_store import (
    build_dashboard_metrics as _build_ocp_dashboard_metrics,
    build_lease_status as _build_ocp_lease_status,
    build_namespaces as _build_ocp_namespaces,
    build_ops_chat_response as _build_ops_chat_response,
    build_overview as _build_ocp_overview,
    build_status_response as _build_ocp_status_response,
    build_test_result as _build_ocp_test_result,
    create_profile as _create_ocp_profile,
    disconnect_profile as _disconnect_ocp_profile,
    get_resource_detail as _get_ocp_resource_detail,
    get_profile as _get_ocp_profile,
    list_resources as _list_ocp_resources,
    list_profiles as _list_ocp_profiles,
)
from play_book_studio.app.action_store import (
    approve_request as _approve_action_request,
    create_request as _create_action_request,
    execute_request as _execute_action_request,
    list_audit as _list_action_audit,
    list_executions as _list_action_executions,
    list_requests as _list_action_requests,
    preview_action as _preview_action,
    reject_request as _reject_action_request,
)
from play_book_studio.app.scm_store import (
    build_oauth_authorize_url as _build_scm_oauth_authorize_url,
    build_deployment_plan as _build_scm_deployment_plan,
    complete_oauth_callback as _complete_scm_oauth_callback,
    create_connection as _create_scm_connection,
    create_repository as _create_scm_repository,
    discover_repositories as _discover_scm_repositories,
    get_connection as _get_scm_connection,
    get_repository as _get_scm_repository,
    list_connections as _list_scm_connections,
    list_repositories as _list_scm_repositories,
    oauth_is_configured as _scm_oauth_is_configured,
    update_repository as _update_scm_repository,
)
from play_book_studio.app.workspace_store import (
    create_workspace as _create_workspace,
    get_workspace as _get_workspace,
    list_workspaces as _list_workspaces,
)
from play_book_studio.app.server_routes_viewer import (
    _viewer_source_meta as _viewer_source_meta_payload,
    resolve_viewer_html as _resolve_viewer_html,
)
from play_book_studio.app.wiki_user_overlay import (
    build_wiki_overlay_signal_payload as _build_wiki_overlay_signal_payload,
    list_wiki_user_overlays as _list_wiki_user_overlays,
    remove_wiki_user_overlay as _remove_wiki_user_overlay,
    save_wiki_user_overlay as _save_wiki_user_overlay,
)
from play_book_studio.config.settings import load_settings
from play_book_studio.ingestion.manifest import (
    _source_fingerprint,
    read_manifest,
    write_manifest,
)
from play_book_studio.ingestion.models import (
    CONTENT_STATUS_APPROVED_KO,
    CONTENT_STATUS_TRANSLATED_KO_DRAFT,
    SOURCE_STATE_PUBLISHED_NATIVE,
    SourceManifestEntry,
)
from play_book_studio.ingestion.source_first import (
    derive_official_docs_legal_notice_url,
    derive_official_docs_license_or_terms,
    source_mirror_root,
)
from play_book_studio.ingestion.translation_draft_generation import (
    _source_repo_runtime_entry,
    generate_translation_drafts,
)
from play_book_studio.ingestion.translation_gold_promotion import promote_translation_gold


_QUERY_TOKEN_RE = re.compile(r"[^\w가-힣]+", re.UNICODE)


def _safe_read_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_entries(path: Path | None) -> list[dict[str, Any]]:
    payload = _safe_read_json_object(path)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    return [dict(item) for item in entries if isinstance(item, dict)]


def _first_nonempty(*values: Any) -> str:
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _normalize_repo_relative_path(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return ""
    if Path(normalized).suffix:
        return normalized
    return f"{normalized.rstrip('/')}/index.adoc"


def _repo_blob_href(*, repo_url: str, branch: str, relative_path: str) -> str:
    repo = str(repo_url or "").strip().rstrip("/")
    path = _normalize_repo_relative_path(relative_path)
    branch_name = str(branch or "").strip() or "main"
    if not repo or not path:
        return ""
    return f"{repo}/blob/{branch_name}/{path}"


def _search_query_tokens(query: str) -> list[str]:
    tokens = [
        token
        for token in _QUERY_TOKEN_RE.split(str(query or "").lower())
        if token and len(token) > 1
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def _official_candidate_source_payload(entry: dict[str, Any], settings: Any) -> dict[str, Any]:
    slug = str(entry.get("book_slug") or "").strip()
    current_source_url = _first_nonempty(entry.get("source_url"), entry.get("resolved_source_url"))
    homepage_url = _first_nonempty(
        current_source_url if "docs.redhat.com" in current_source_url else "",
        settings.book_url_template.format(slug=slug) if slug else "",
    )
    repo_relative_path = _first_nonempty(
        entry.get("source_relative_path"),
        *(entry.get("source_relative_paths") or []),
    )
    repo_url = _first_nonempty(entry.get("source_repo"))
    repo_branch = _first_nonempty(entry.get("source_branch"), f"enterprise-{settings.ocp_version}")
    repo_href = _first_nonempty(
        current_source_url if "github.com" in current_source_url else "",
        _repo_blob_href(repo_url=repo_url, branch=repo_branch, relative_path=repo_relative_path),
    )
    primary_input_kind = _first_nonempty(entry.get("primary_input_kind"))
    source_kind = _first_nonempty(entry.get("source_kind"))
    current_basis = "unknown"
    if "github.com" in current_source_url or primary_input_kind == "source_repo" or source_kind == "source-first":
        current_basis = "official_repo"
    elif "docs.redhat.com" in current_source_url or primary_input_kind == "html_single" or source_kind == "html-single":
        current_basis = "official_homepage"
    elif repo_href and not homepage_url:
        current_basis = "official_repo"
    elif homepage_url and not repo_href:
        current_basis = "official_homepage"
    current_label = {
        "official_homepage": "공식 홈페이지 기준",
        "official_repo": "공식 레포 기준",
    }.get(current_basis, "원천 기준 미기록")
    return {
        "current_source_basis": current_basis,
        "current_source_label": current_label,
        "source_options": [
            {
                "key": "official_homepage",
                "label": "공식 홈페이지",
                "href": homepage_url,
                "availability": "available" if homepage_url else "missing",
                "note": "공식 KO published manual",
                "is_current": current_basis == "official_homepage",
            },
            {
                "key": "official_repo",
                "label": "공식 레포",
                "href": repo_href,
                "availability": "available" if repo_href else "missing",
                "note": "공식 AsciiDoc 원천",
                "is_current": current_basis == "official_repo",
            },
        ],
    }


def _candidate_match_score(query: str, entry: dict[str, Any]) -> int:
    normalized_query = " ".join(str(query or "").strip().lower().split())
    if not normalized_query:
        return 0
    slug = str(entry.get("book_slug") or "").strip().lower()
    slug_label = slug.replace("_", " ").replace("-", " ")
    title = str(entry.get("title") or "").strip().lower()
    source_relative_path = _first_nonempty(entry.get("source_relative_path"), *(entry.get("source_relative_paths") or [])).lower()
    source_url = str(entry.get("source_url") or "").strip().lower()
    haystack = " ".join([slug, slug_label, title, source_relative_path, source_url])
    tokens = _search_query_tokens(normalized_query)
    if not tokens:
        return 0
    score = 0
    if normalized_query in title or normalized_query in slug_label or normalized_query in slug:
        score += 100
    for token in tokens:
        if token in title:
            score += 25
        elif token in slug_label or token in slug:
            score += 18
        elif token in source_relative_path:
            score += 10
        elif token in haystack:
            score += 6
    return score


def _official_candidate_manifest_paths(root_dir: Path, settings: Any) -> tuple[Path, ...]:
    manifest_dir = settings.manifest_dir
    prefix = settings.active_pack.manifest_prefix
    candidates = [
        manifest_dir / f"{prefix}_translated_ko_draft_all_runtime.json",
        settings.translation_draft_manifest_path,
        settings.source_manifest_path,
    ]
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return tuple(unique)


def _manifest_entry_by_slug(path: Path | None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for entry in _manifest_entries(path):
        slug = str(entry.get("book_slug") or "").strip()
        if slug:
            rows[slug] = entry
    return rows


def _search_official_source_candidates(root_dir: Path, *, query: str, limit: int = 8) -> list[dict[str, Any]]:
    settings = load_settings(root_dir)
    approved_entries_by_slug = _manifest_entry_by_slug(settings.source_manifest_path)
    approved_slugs = set(approved_entries_by_slug)
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    seen_slugs: set[str] = set()
    for path in _official_candidate_manifest_paths(root_dir, settings):
        for entry in _manifest_entries(path):
            slug = str(entry.get("book_slug") or "").strip()
            if not slug or slug in seen_slugs:
                continue
            score = _candidate_match_score(query, entry)
            if score <= 0:
                continue
            seen_slugs.add(slug)
            ranked.append((score, slug, entry))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    rows: list[dict[str, Any]] = []
    for score, slug, entry in ranked[: max(1, min(limit, 12))]:
        display_entry = approved_entries_by_slug.get(slug) if slug in approved_slugs else None
        source_payload = _official_candidate_source_payload(display_entry or entry, settings)
        rows.append(
            {
                "book_slug": slug,
                "title": str((display_entry or entry).get("title") or slug),
                "viewer_path": str((display_entry or entry).get("viewer_path") or settings.viewer_path_template.format(slug=slug)),
                "source_relative_path": _first_nonempty(
                    (display_entry or entry).get("source_relative_path"),
                    *((display_entry or entry).get("source_relative_paths") or []),
                ),
                "source_repo": str((display_entry or entry).get("source_repo") or "").strip(),
                "source_kind": str((display_entry or entry).get("source_kind") or "").strip(),
                "status_kind": "live" if slug in approved_slugs else "candidate",
                "status_label": "이미 Library에 있음" if slug in approved_slugs else "생산 후보",
                "match_score": score,
                **source_payload,
            }
        )
    return rows


def _list_official_source_catalog(root_dir: Path) -> dict[str, Any]:
    settings = load_settings(root_dir)
    manifest_paths = _official_candidate_manifest_paths(root_dir, settings)
    source_truth_path = manifest_paths[0] if manifest_paths else None
    approved_entries_by_slug = _manifest_entry_by_slug(settings.source_manifest_path)
    approved_slugs = set(approved_entries_by_slug)
    rows: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for entry in _manifest_entries(source_truth_path):
        slug = str(entry.get("book_slug") or "").strip()
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        display_entry = approved_entries_by_slug.get(slug) if slug in approved_slugs else None
        resolved_entry = display_entry or entry
        source_payload = _official_candidate_source_payload(resolved_entry, settings)
        rows.append(
            {
                "book_slug": slug,
                "title": str(resolved_entry.get("title") or slug),
                "viewer_path": str(resolved_entry.get("viewer_path") or settings.viewer_path_template.format(slug=slug)),
                "source_relative_path": _first_nonempty(
                    resolved_entry.get("source_relative_path"),
                    *(resolved_entry.get("source_relative_paths") or []),
                ),
                "source_repo": str(resolved_entry.get("source_repo") or "").strip(),
                "source_kind": str(resolved_entry.get("source_kind") or "").strip(),
                "status_kind": "live" if slug in approved_slugs else "candidate",
                "status_label": "이미 Library에 있음" if slug in approved_slugs else "아직 없음",
                "match_score": 0,
                **source_payload,
            }
        )
    rows.sort(key=lambda item: (str(item.get("status_kind") or "") != "live", str(item.get("title") or "").lower(), str(item.get("book_slug") or "").lower()))
    live_count = sum(1 for row in rows if str(row.get("status_kind") or "") == "live")
    return {
        "source": "ocp_4_20_all_runtime_catalog",
        "total_count": len(rows),
        "live_count": live_count,
        "candidate_count": max(len(rows) - live_count, 0),
        "rows": rows,
    }


def _official_materialize_manifest_dir(root_dir: Path) -> Path:
    return root_dir / "tmp" / "book_factory_official_materialize"


def _official_materialize_manifest_path(root_dir: Path, *, slug: str, source_basis: str) -> Path:
    safe_slug = slug.strip().replace("/", "_").replace("\\", "_")
    safe_basis = source_basis.strip().replace("/", "_")
    return _official_materialize_manifest_dir(root_dir) / f"{safe_slug}.{safe_basis}.manifest.json"


def _official_materialize_report_path(root_dir: Path, *, slug: str, source_basis: str) -> Path:
    safe_slug = slug.strip().replace("/", "_").replace("\\", "_")
    safe_basis = source_basis.strip().replace("/", "_")
    return root_dir / "reports" / "build_logs" / f"book_factory_{safe_slug}_{safe_basis}.json"


def _candidate_seed_entry(root_dir: Path, *, slug: str) -> SourceManifestEntry:
    settings = load_settings(root_dir)
    for path in _official_candidate_manifest_paths(root_dir, settings):
        for entry in read_manifest(path):
            if entry.book_slug == slug:
                return entry
    raise ValueError(f"official source candidate not found for {slug}")


def _official_homepage_entry(seed: SourceManifestEntry, *, root_dir: Path) -> SourceManifestEntry:
    settings = load_settings(root_dir)
    source_payload = _official_candidate_source_payload(seed.to_dict(), settings)
    homepage_url = _first_nonempty(
        next(
            (
                option.get("href")
                for option in source_payload.get("source_options", [])
                if isinstance(option, dict) and str(option.get("key") or "").strip() == "official_homepage"
            ),
            "",
        ),
        settings.book_url_template.format(slug=seed.book_slug),
    )
    if not homepage_url:
        raise ValueError(f"official homepage source missing for {seed.book_slug}")
    payload = {
        **seed.to_dict(),
        "source_kind": "html-single",
        "source_url": homepage_url,
        "resolved_source_url": homepage_url,
        "source_lane": "official_ko",
        "source_state": SOURCE_STATE_PUBLISHED_NATIVE,
        "source_state_reason": "official_ko_published_surface_selected_in_book_factory",
        "content_status": CONTENT_STATUS_APPROVED_KO,
        "citation_eligible": True,
        "citation_block_reason": "",
        "approval_status": "approved",
        "approval_state": "approved",
        "publication_state": "published",
        "review_status": "approved",
        "resolved_language": "ko",
        "body_language_guess": "ko",
        "fallback_detected": False,
        "primary_input_kind": "html_single",
        "fallback_input_kind": "",
        "translation_source_language": "ko",
        "translation_target_language": "ko",
        "translation_source_url": homepage_url,
        "translation_source_fingerprint": "",
        "translation_stage": CONTENT_STATUS_APPROVED_KO,
        "legal_notice_url": str(seed.legal_notice_url or derive_official_docs_legal_notice_url(seed)).strip(),
        "license_or_terms": str(
            seed.license_or_terms
            or derive_official_docs_license_or_terms(seed, legal_notice_url=str(seed.legal_notice_url or ""))
        ).strip(),
    }
    payload["source_fingerprint"] = _source_fingerprint(
        product_slug=str(payload.get("product_slug") or seed.product_slug),
        ocp_version=str(payload.get("ocp_version") or seed.ocp_version),
        docs_language=str(payload.get("docs_language") or seed.docs_language),
        source_kind=str(payload.get("source_kind") or "html-single"),
        book_slug=str(payload.get("book_slug") or seed.book_slug),
        source_url=str(payload.get("source_url") or ""),
        resolved_source_url=str(payload.get("resolved_source_url") or ""),
        viewer_path=str(payload.get("viewer_path") or seed.viewer_path),
        resolved_language=str(payload.get("resolved_language") or "ko"),
        source_relative_path="",
        primary_input_kind="html_single",
    )
    return SourceManifestEntry(**payload)


def _official_repo_entry(seed: SourceManifestEntry, *, root_dir: Path) -> SourceManifestEntry:
    settings = load_settings(root_dir)
    runtime_seed = SourceManifestEntry(
        **{
            **seed.to_dict(),
            "source_mirror_root": str(source_mirror_root(settings.root_dir)),
        }
    )
    runtime_entry, _source_paths = _source_repo_runtime_entry(settings, runtime_seed)
    return runtime_entry


def _official_source_entry(root_dir: Path, *, slug: str, source_basis: str) -> SourceManifestEntry:
    seed = _candidate_seed_entry(root_dir, slug=slug)
    basis = str(source_basis or "").strip()
    if basis == "official_homepage":
        return _official_homepage_entry(seed, root_dir=root_dir)
    if basis == "official_repo":
        return _official_repo_entry(seed, root_dir=root_dir)
    raise ValueError("source_basis must be official_homepage or official_repo")


def _official_source_smoke(root_dir: Path, *, viewer_path: str, slug: str) -> dict[str, Any]:
    settings = load_settings(root_dir)
    approved_entries = read_manifest(settings.source_manifest_path) if settings.source_manifest_path.exists() else []
    approved_entry = next((entry for entry in approved_entries if entry.book_slug == slug), None)
    viewer_html = _resolve_viewer_html(root_dir, viewer_path)
    source_meta = _viewer_source_meta_payload(root_dir, viewer_path)
    return {
        "approved_manifest_present": approved_entry is not None,
        "approved_manifest_count": len(approved_entries),
        "approved_source_kind": str(approved_entry.source_kind if approved_entry is not None else ""),
        "approved_source_url": str(approved_entry.source_url if approved_entry is not None else ""),
        "approved_source_lane": str(approved_entry.source_lane if approved_entry is not None else ""),
        "viewer_ready": bool(str(viewer_html or "").strip()),
        "source_meta_ready": bool(source_meta),
        "viewer_path": viewer_path,
    }


def _materialize_official_source(root_dir: Path, *, slug: str, source_basis: str) -> dict[str, Any]:
    settings = load_settings(root_dir)
    entry = _official_source_entry(root_dir, slug=slug, source_basis=source_basis)
    manifest_path = _official_materialize_manifest_path(root_dir, slug=slug, source_basis=source_basis)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest_path, [entry])
    generation_report = generate_translation_drafts(
        settings,
        slugs=[slug],
        force_collect=source_basis == "official_homepage",
        force_regenerate=True,
        manifest_path=manifest_path,
    )
    promotion_report = promote_translation_gold(
        settings,
        slugs=[slug],
        generate_first=False,
        sync_qdrant=True,
        refresh_synthesis_report=True,
        manifest_path=manifest_path,
    )
    smoke = _official_source_smoke(root_dir, viewer_path=entry.viewer_path, slug=slug)
    if not (smoke.get("approved_manifest_present") and smoke.get("viewer_ready") and smoke.get("source_meta_ready")):
        raise RuntimeError(f"post-switch smoke failed for {slug}")
    report = {
        "book_slug": slug,
        "source_basis": source_basis,
        "source_label": "공식 홈페이지 기준" if source_basis == "official_homepage" else "공식 레포 기준",
        "title": entry.title,
        "viewer_path": entry.viewer_path,
        "request_manifest_path": str(manifest_path.resolve()),
        "draft_summary": generation_report.get("summary", {}),
        "gold_summary": promotion_report.get("summary", {}),
        "smoke": smoke,
    }
    report_path = _official_materialize_report_path(root_dir, slug=slug, source_basis=source_basis)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path.resolve())
    return report


def _list_unanswered_questions(root_dir: Path, *, limit: int = 20) -> dict[str, Any]:
    settings = load_settings(root_dir)
    target = settings.unanswered_questions_path
    if not target.exists():
        return {"count": 0, "items": []}
    rows: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    for line in reversed(target.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(payload.get("record_kind") or "") != "unanswered_question":
            continue
        query = str(payload.get("query") or "").strip()
        if not query or query in seen_queries:
            continue
        seen_queries.add(query)
        rows.append(
            {
                "query": query,
                "rewritten_query": str(payload.get("rewritten_query") or "").strip(),
                "timestamp": str(payload.get("timestamp") or "").strip(),
                "response_kind": str(payload.get("response_kind") or "").strip(),
                "warnings": [str(item) for item in (payload.get("warnings") or []) if str(item).strip()],
            }
        )
        if len(rows) >= max(1, limit):
            break
    return {"count": len(rows), "items": rows}


def handle_sessions_list(handler: Any, query: str, *, store: Any) -> None:
    params = parse_qs(query, keep_blank_values=False)
    limit_raw = str((params.get("limit") or ["50"])[0]).strip()
    try:
        limit = max(1, min(200, int(limit_raw)))
    except ValueError:
        limit = 50
    summaries = store.list_summaries(limit=limit)
    handler._send_json({"sessions": summaries, "count": len(summaries)})


def handle_session_load(handler: Any, query: str, *, store: Any) -> None:
    params = parse_qs(query, keep_blank_values=False)
    session_id = str((params.get("session_id") or [""])[0]).strip()
    if not session_id:
        handler._send_json({"error": "session_id is required"}, HTTPStatus.BAD_REQUEST)
        return
    session = store.peek(session_id)
    if session is None:
        handler._send_json({"error": "Session not found"}, HTTPStatus.NOT_FOUND)
        return
    from play_book_studio.app.sessions import serialize_session_snapshot

    payload = serialize_session_snapshot(session)
    blocked = blocked_customer_pack_draft_ids_from_payload(Path(store._root_dir or "."), payload)
    if blocked:
        handler._send_json({"error": "Session not found"}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(payload)


def handle_session_delete(handler: Any, payload: dict[str, Any], *, store: Any) -> None:
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        handler._send_json({"error": "session_id is required"}, HTTPStatus.BAD_REQUEST)
        return
    deleted = bool(store.delete(session_id))
    if not deleted:
        handler._send_json({"error": "Session not found"}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json({"success": True, "session_id": session_id})


def handle_sessions_delete_all(handler: Any, payload: dict[str, Any], *, store: Any) -> None:
    del payload
    deleted_count = int(store.delete_all())
    handler._send_json({"success": True, "deleted_count": deleted_count})


def handle_debug_session(handler: Any, query: str, *, store: Any, build_session_debug_payload: Any) -> None:
    params = parse_qs(query, keep_blank_values=False)
    session_id = str((params.get("session_id") or [""])[0]).strip()
    session = store.peek(session_id) if session_id else store.latest()
    if session is None:
        handler._send_json({"error": "조회할 세션이 없습니다."}, HTTPStatus.NOT_FOUND)
        return
    payload = build_session_debug_payload(session)
    blocked = blocked_customer_pack_draft_ids_from_payload(Path(store._root_dir or "."), payload)
    if blocked:
        handler._send_json({"error": "조회할 세션이 없습니다."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(payload)


def handle_debug_chat_log(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    limit_raw = str((params.get("limit") or ["20"])[0]).strip()
    try:
        limit = max(1, min(200, int(limit_raw or "20")))
    except ValueError:
        handler._send_json({"error": "limit는 정수여야 합니다."}, HTTPStatus.BAD_REQUEST)
        return
    log_path = load_settings(root_dir).chat_log_path
    if not log_path.exists():
        handler._send_json({"entries": [], "count": 0})
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines[-limit:] if line.strip()]
    sanitized_entries = [
        sanitize_debug_chat_log_entry(entry)
        for entry in entries
        if not blocked_customer_pack_draft_ids_from_payload(root_dir, entry)
    ]
    handler._send_json({"entries": sanitized_entries, "count": len(sanitized_entries)})


def handle_data_control_room(handler: Any, query: str, *, root_dir: Path) -> dict[str, Any]:
    del query
    payload = build_data_control_room_payload(root_dir)
    handler._send_json(payload)
    return payload


def handle_data_control_room_chunks(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    scope = str((params.get("scope") or ["runtime"])[0]).strip()
    book_slug = str((params.get("book_slug") or [""])[0]).strip()
    draft_id = str((params.get("draft_id") or [""])[0]).strip()
    if scope == "customer_pack":
        effective_draft_id = draft_id or (book_slug.split("--", 1)[0].strip() if "--" in book_slug else book_slug)
        if not effective_draft_id or not _customer_pack_read_allowed(root_dir, effective_draft_id):
            _send_customer_pack_read_blocked(handler)
            return
        draft_id = effective_draft_id
    try:
        payload = build_data_control_room_chunk_payload(
            root_dir,
            scope=scope,
            book_slug=book_slug,
            draft_id=draft_id,
        )
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    except FileNotFoundError:
        handler._send_json({"error": "chunk detail을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        return
    except Exception as exc:  # noqa: BLE001
        handler._send_json(
            {"error": f"chunk detail 구성 중 오류가 발생했습니다: {exc}"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        return
    handler._send_json(payload)


def handle_buyer_packet(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    packet_id = str((params.get("packet_id") or [""])[0]).strip()
    if not packet_id:
        handler._send_json({"error": "packet_id가 필요합니다."}, HTTPStatus.BAD_REQUEST)
        return
    bundle_path = root_dir / "reports" / "build_logs" / "buyer_packet_bundle_index.json"
    if not bundle_path.exists():
        handler._send_json({"error": "buyer packet bundle이 없습니다."}, HTTPStatus.NOT_FOUND)
        return
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    packets = bundle.get("packets") if isinstance(bundle.get("packets"), list) else []
    match = next(
        (
            entry for entry in packets
            if isinstance(entry, dict) and str(entry.get("id") or "").strip() == packet_id
        ),
        None,
    )
    if not isinstance(match, dict):
        handler._send_json({"error": "buyer packet을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        return
    markdown_path = root_dir / str(match.get("markdown_path") or "")
    json_path = root_dir / str(match.get("json_path") or "")
    if not markdown_path.exists():
        handler._send_json({"error": "buyer packet markdown을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(
        {
            "packet_id": packet_id,
            "title": str(match.get("title") or packet_id),
            "purpose": str(match.get("purpose") or ""),
            "status": str(match.get("status") or ""),
            "markdown_path": str(markdown_path.resolve()),
            "json_path": str(json_path.resolve()) if json_path.exists() else "",
            "body": markdown_path.read_text(encoding="utf-8"),
        }
    )


def handle_repository_search(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    search_query = str((params.get("query") or [""])[0]).strip()
    limit_raw = str((params.get("limit") or ["12"])[0]).strip()
    try:
        limit = int(limit_raw or "12")
    except ValueError:
        handler._send_json({"error": "limit는 정수여야 합니다."}, HTTPStatus.BAD_REQUEST)
        return
    try:
        payload = _search_github_repositories(root_dir, query=search_query, limit=limit)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    except Exception as exc:  # noqa: BLE001
        handler._send_json(
            {"error": f"repository search 중 오류가 발생했습니다: {exc}"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        return
    payload["official_candidates"] = _search_official_source_candidates(
        root_dir,
        query=search_query,
        limit=min(limit, 8),
    )
    handler._send_json(payload)


def handle_repository_official_catalog(handler: Any, query: str, *, root_dir: Path) -> None:
    del query
    try:
        payload = _list_official_source_catalog(root_dir)
    except Exception as exc:  # noqa: BLE001
        handler._send_json(
            {"error": f"official source catalog 구성 중 오류가 발생했습니다: {exc}"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        return
    handler._send_json(payload)


def handle_repository_official_materialize(
    handler: Any,
    payload: dict[str, Any],
    *,
    root_dir: Path,
) -> dict[str, Any] | None:
    slug = str(payload.get("book_slug") or "").strip()
    source_basis = str(payload.get("source_basis") or "").strip()
    if not slug:
        handler._send_json({"error": "book_slug가 필요합니다."}, HTTPStatus.BAD_REQUEST)
        return None
    if source_basis not in {"official_homepage", "official_repo"}:
        handler._send_json(
            {"error": "source_basis는 official_homepage 또는 official_repo 여야 합니다."},
            HTTPStatus.BAD_REQUEST,
        )
        return None
    try:
        report = _materialize_official_source(root_dir, slug=slug, source_basis=source_basis)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return None
    except Exception as exc:  # noqa: BLE001
        handler._send_json(
            {"error": f"official source materialize 중 오류가 발생했습니다: {exc}"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        return None
    handler._send_json(report, HTTPStatus.CREATED)
    return report


def handle_repository_unanswered(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    limit_raw = str((params.get("limit") or ["20"])[0]).strip()
    try:
        limit = int(limit_raw or "20")
    except ValueError:
        handler._send_json({"error": "limit는 정수여야 합니다."}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(_list_unanswered_questions(root_dir, limit=limit))


def handle_repository_favorites(handler: Any, query: str, *, root_dir: Path) -> None:
    del query
    handler._send_json(_list_repository_favorites(root_dir))


def handle_workspaces(handler: Any, query: str, *, root_dir: Path) -> None:
    del query
    handler._send_json(_list_workspaces(root_dir))


def handle_workspaces_create(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        created = _create_workspace(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(created, HTTPStatus.CREATED)


def handle_ocp_profiles(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    workspace_id = str((params.get("workspace_id") or [""])[0]).strip()
    handler._send_json(_list_ocp_profiles(root_dir, workspace_id=workspace_id))


def handle_ocp_connect(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        profile = _create_ocp_profile(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(
        _build_ocp_status_response(profile, message="Connection profile created."),
        HTTPStatus.CREATED,
    )


def handle_ocp_status(handler: Any, connection_id: str, *, root_dir: Path) -> None:
    profile = _get_ocp_profile(root_dir, connection_id)
    handler._send_json(
        _build_ocp_status_response(
            profile,
            message="Connection profile loaded." if profile is not None else "Connection profile not found.",
        )
    )


def handle_ocp_disconnect(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    connection_id = str(payload.get("connection_id") or "").strip()
    if not connection_id:
        handler._send_json({"error": "connection_id is required"}, HTTPStatus.BAD_REQUEST)
        return
    removed = _disconnect_ocp_profile(root_dir, connection_id)
    if removed is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(_build_ocp_status_response(None, message=f"Disconnected from {removed.get('cluster_url') or ''}."))


def handle_ocp_test(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    connection_id = str(payload.get("connection_id") or "").strip()
    if not connection_id:
        handler._send_json({"error": "connection_id is required"}, HTTPStatus.BAD_REQUEST)
        return
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(
        _build_ocp_test_result(
            root_dir,
            profile,
            message="Stored connection profile check completed. Live cluster verification is not wired yet.",
        )
    )


def handle_ocp_lease_status(handler: Any, query: str, *, root_dir: Path) -> None:
    del query, root_dir
    handler._send_json(_build_ocp_lease_status())


def handle_ocp_lease_refresh(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    connection_id = str(payload.get("connection_id") or "").strip()
    if not connection_id:
        handler._send_json({"error": "connection_id is required"}, HTTPStatus.BAD_REQUEST)
        return
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(
        _build_ocp_test_result(
            root_dir,
            profile,
            message="Lease metadata refreshed from the stored profile. Real lease automation is not wired yet.",
        )
    )


def handle_ocp_overview(handler: Any, connection_id: str, *, root_dir: Path) -> None:
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    try:
        handler._send_json(_build_ocp_overview(root_dir, profile))
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def handle_ocp_metrics(handler: Any, connection_id: str, query: str, *, root_dir: Path) -> None:
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    params = parse_qs(query, keep_blank_values=False)
    window = str((params.get("window") or ["1h"])[0]).strip() or "1h"
    step = str((params.get("step") or ["5m"])[0]).strip() or "5m"
    try:
        handler._send_json(_build_ocp_dashboard_metrics(root_dir, profile, window=window, step=step))
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def handle_ocp_namespaces(handler: Any, connection_id: str, *, root_dir: Path) -> None:
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    try:
        handler._send_json(_build_ocp_namespaces(root_dir, profile))
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def handle_ocp_resources(handler: Any, connection_id: str, query: str, *, root_dir: Path) -> None:
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    params = parse_qs(query, keep_blank_values=False)
    resource = str((params.get("resource") or ["pods"])[0]).strip() or "pods"
    namespace = str((params.get("namespace") or [str(profile.get("default_namespace") or "")])[0]).strip()
    if not namespace:
        handler._send_json({"error": "namespace is required"}, HTTPStatus.BAD_REQUEST)
        return
    try:
        handler._send_json(_list_ocp_resources(root_dir, profile, resource=resource, namespace=namespace))
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def handle_ocp_resource_detail(handler: Any, connection_id: str, query: str, *, root_dir: Path) -> None:
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    params = parse_qs(query, keep_blank_values=False)
    resource = str((params.get("resource") or ["pods"])[0]).strip() or "pods"
    namespace = str((params.get("namespace") or [str(profile.get("default_namespace") or "")])[0]).strip()
    name = str((params.get("name") or [""])[0]).strip()
    if not namespace:
        handler._send_json({"error": "namespace is required"}, HTTPStatus.BAD_REQUEST)
        return
    if not name:
        handler._send_json({"error": "name is required"}, HTTPStatus.BAD_REQUEST)
        return
    try:
        payload = _get_ocp_resource_detail(root_dir, profile, resource=resource, namespace=namespace, name=name)
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    except Exception as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        return
    handler._send_json(payload)


def handle_ops_chat(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    connection_id = str(payload.get("connection_id") or "").strip()
    if not connection_id:
        handler._send_json({"error": "connection_id is required"}, HTTPStatus.BAD_REQUEST)
        return
    profile = _get_ocp_profile(root_dir, connection_id)
    if profile is None:
        handler._send_json({"error": "Connection profile not found."}, HTTPStatus.NOT_FOUND)
        return
    message = str(payload.get("message") or "").strip()
    if not message:
        handler._send_json({"error": "message is required"}, HTTPStatus.BAD_REQUEST)
        return
    namespace = str(payload.get("namespace") or "").strip()
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    handler._send_json(
        _build_ops_chat_response(
            root_dir,
            profile,
            message=message,
            namespace=namespace,
            history=[dict(item) for item in history if isinstance(item, dict)],
        )
    )


def handle_actions_preview(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        preview = _preview_action(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(preview)


def handle_actions_requests_create(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        record = _create_action_request(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(record, HTTPStatus.CREATED)


def handle_actions_requests_list(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    limit = int(str((params.get("limit") or ["20"])[0]).strip() or "20")
    handler._send_json(_list_action_requests(root_dir, limit=limit))


def handle_actions_request_approve(handler: Any, request_id: str, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        record = _approve_action_request(root_dir, request_id, payload)
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(record)


def handle_actions_request_reject(handler: Any, request_id: str, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        record = _reject_action_request(root_dir, request_id, payload)
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(record)


def handle_actions_request_execute(handler: Any, request_id: str, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        execution = _execute_action_request(root_dir, request_id, payload)
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(execution)


def handle_actions_executions_list(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    limit = int(str((params.get("limit") or ["20"])[0]).strip() or "20")
    handler._send_json(_list_action_executions(root_dir, limit=limit))


def handle_actions_audit_list(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    limit = int(str((params.get("limit") or ["20"])[0]).strip() or "20")
    handler._send_json(_list_action_audit(root_dir, limit=limit))


def handle_scm_connections_list(handler: Any, workspace_id: str, *, root_dir: Path) -> None:
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(_list_scm_connections(root_dir, workspace_id))


def handle_scm_connection_repositories_discover(handler: Any, workspace_id: str, connection_id: str, query: str, *, root_dir: Path) -> None:
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    params = parse_qs(query, keep_blank_values=False)
    search_query = str((params.get("query") or [""])[0]).strip()
    limit = int(str((params.get("limit") or ["20"])[0]).strip() or "20")
    try:
        payload = _discover_scm_repositories(
            root_dir,
            workspace_id=workspace_id,
            connection_id=connection_id,
            query=search_query,
            limit=limit,
        )
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    except requests.HTTPError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        return
    handler._send_json(payload)


def handle_scm_connections_create(handler: Any, workspace_id: str, payload: dict[str, Any], *, root_dir: Path) -> None:
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    try:
        record = _create_scm_connection(root_dir, workspace_id, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(record, HTTPStatus.CREATED)


def handle_scm_repositories_list(handler: Any, workspace_id: str, *, root_dir: Path) -> None:
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(_list_scm_repositories(root_dir, workspace_id))


def handle_scm_repositories_create(handler: Any, workspace_id: str, payload: dict[str, Any], *, root_dir: Path) -> None:
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    connection_id = str(payload.get("scm_connection_id") or "").strip()
    connection = _get_scm_connection(root_dir, connection_id)
    if connection is None or str(connection.get("workspace_id") or "") != workspace_id:
        handler._send_json({"error": "SCM connection not found."}, HTTPStatus.NOT_FOUND)
        return
    try:
        record = _create_scm_repository(root_dir, workspace_id, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    except requests.HTTPError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        return
    handler._send_json(record, HTTPStatus.CREATED)


def handle_scm_repository_update(handler: Any, workspace_id: str, repository_id: str, payload: dict[str, Any], *, root_dir: Path) -> None:
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    repository = _get_scm_repository(root_dir, repository_id)
    if repository is None or str(repository.get("workspace_id") or "") != workspace_id:
        handler._send_json({"error": "Repository not found."}, HTTPStatus.NOT_FOUND)
        return
    try:
        record = _update_scm_repository(root_dir, repository_id, payload)
    except LookupError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        return
    except requests.HTTPError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        return
    handler._send_json(record)


def handle_scm_deployment_plan(handler: Any, workspace_id: str, repository_id: str, payload: dict[str, Any], *, root_dir: Path) -> None:
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    repository = _get_scm_repository(root_dir, repository_id)
    if repository is None or str(repository.get("workspace_id") or "") != workspace_id:
        handler._send_json({"error": "Repository not found."}, HTTPStatus.NOT_FOUND)
        return
    handler._send_json(_build_scm_deployment_plan(repository, workspace_id, payload))


def handle_scm_oauth_start(handler: Any, provider: str, query: str, *, root_dir: Path) -> None:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider not in {"github", "gitlab"}:
        handler._send_json({"error": "Unsupported OAuth provider."}, HTTPStatus.BAD_REQUEST)
        return
    params = parse_qs(query, keep_blank_values=False)
    workspace_id = str((params.get("workspace_id") or [""])[0]).strip()
    if _get_workspace(root_dir, workspace_id) is None:
        handler._send_json({"error": "Workspace not found."}, HTTPStatus.NOT_FOUND)
        return
    if _scm_oauth_is_configured(root_dir, normalized_provider):
        callback_url = f"http://{handler.headers.get('Host', '127.0.0.1')}/api/v1/oauth/{normalized_provider}/callback"
        authorize_url, state = _build_scm_oauth_authorize_url(
            root_dir,
            provider=normalized_provider,
            workspace_id=workspace_id,
            callback_url=callback_url,
        )
        handler._send_json({"provider": normalized_provider, "authorize_url": authorize_url, "state": state})
        return
    connection = _create_scm_connection(
        root_dir,
        workspace_id,
        {
            "provider": normalized_provider,
            "host_url": "https://gitlab.com" if normalized_provider == "gitlab" else "https://github.com",
            "account_label": f"{normalized_provider}-oauth",
        },
        auth_type_override="oauth",
    )
    authorize_url = f"/ops/scm?oauth_status=connected&provider={normalized_provider}&connection_id={connection['scm_connection_id']}"
    handler._send_json({"provider": normalized_provider, "authorize_url": authorize_url, "state": f"state-{connection['scm_connection_id']}"})


def handle_scm_oauth_callback(handler: Any, provider: str, query: str, *, root_dir: Path) -> None:
    normalized_provider = str(provider or "").strip().lower()
    params = parse_qs(query, keep_blank_values=False)
    code = str((params.get("code") or [""])[0]).strip()
    state = str((params.get("state") or [""])[0]).strip()
    if not _scm_oauth_is_configured(root_dir, normalized_provider):
        _send_redirect(handler, f"/ops/scm?oauth_status=error&message={normalized_provider}-oauth-not-configured")
        return
    if not code or not state:
        _send_redirect(handler, "/ops/scm?oauth_status=error&message=missing-code-or-state")
        return
    callback_url = f"http://{handler.headers.get('Host', '127.0.0.1')}/api/v1/oauth/{normalized_provider}/callback"
    try:
        connection = _complete_scm_oauth_callback(
            root_dir,
            provider=normalized_provider,
            code=code,
            state=state,
            callback_url=callback_url,
        )
        _send_redirect(handler, f"/ops/scm?oauth_status=connected&provider={normalized_provider}&connection_id={connection['scm_connection_id']}")
    except Exception as exc:
        _send_redirect(handler, f"/ops/scm?oauth_status=error&message={str(exc)}")


def _send_redirect(handler: Any, location: str) -> None:
    handler.send_response(HTTPStatus.SEE_OTHER)
    handler.send_header("Location", location)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def handle_repository_favorites_save(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        saved = _save_repository_favorites(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(saved, HTTPStatus.CREATED)


def handle_repository_favorites_remove(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        saved = _remove_repository_favorite(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(saved)


def handle_wiki_user_overlays(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    user_id = str((params.get("user_id") or [""])[0]).strip()
    if not user_id:
        handler._send_json({"error": "user_id가 필요합니다."}, HTTPStatus.BAD_REQUEST)
        return
    try:
        payload = _list_wiki_user_overlays(root_dir, user_id=user_id)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(payload)


def handle_wiki_overlay_signals(handler: Any, query: str, *, root_dir: Path) -> None:
    params = parse_qs(query, keep_blank_values=False)
    user_id = str((params.get("user_id") or [""])[0]).strip()
    handler._send_json(_build_wiki_overlay_signal_payload(root_dir, user_id=user_id or None))


def handle_wiki_user_overlay_save(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        saved = _save_wiki_user_overlay(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(saved, HTTPStatus.CREATED)


def handle_wiki_user_overlay_remove(handler: Any, payload: dict[str, Any], *, root_dir: Path) -> None:
    try:
        saved = _remove_wiki_user_overlay(root_dir, payload)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return
    handler._send_json(saved)


__all__ = [
    "handle_actions_audit_list",
    "handle_actions_executions_list",
    "handle_actions_preview",
    "handle_actions_request_approve",
    "handle_actions_request_execute",
    "handle_actions_request_reject",
    "handle_actions_requests_create",
    "handle_actions_requests_list",
    "handle_buyer_packet",
    "handle_data_control_room",
    "handle_debug_chat_log",
    "handle_debug_session",
    "handle_repository_favorites",
    "handle_repository_favorites_remove",
    "handle_repository_favorites_save",
    "handle_repository_official_materialize",
    "handle_ocp_connect",
    "handle_ocp_disconnect",
    "handle_ocp_lease_refresh",
    "handle_ocp_lease_status",
    "handle_ocp_metrics",
    "handle_ocp_namespaces",
    "handle_ocp_overview",
    "handle_ocp_resource_detail",
    "handle_ocp_resources",
    "handle_ocp_profiles",
    "handle_ocp_status",
    "handle_ocp_test",
    "handle_ops_chat",
    "handle_repository_search",
    "handle_repository_unanswered",
    "handle_scm_connections_create",
    "handle_scm_connection_repositories_discover",
    "handle_scm_connections_list",
    "handle_scm_oauth_callback",
    "handle_scm_deployment_plan",
    "handle_scm_oauth_start",
    "handle_scm_repositories_create",
    "handle_scm_repositories_list",
    "handle_scm_repository_update",
    "handle_session_delete",
    "handle_session_load",
    "handle_sessions_delete_all",
    "handle_sessions_list",
    "handle_workspaces",
    "handle_workspaces_create",
    "handle_wiki_overlay_signals",
    "handle_wiki_user_overlay_remove",
    "handle_wiki_user_overlay_save",
    "handle_wiki_user_overlays",
]
