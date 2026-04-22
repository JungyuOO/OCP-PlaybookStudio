"""모든 파이프라인 단계가 공유하는 런타임 설정 계약.

`cli.py` 다음으로 이 파일을 보면, 나머지 시스템이 어떤 path, endpoint,
pack 메타데이터, artifact 위치를 바라보는지 빠르게 잡을 수 있다.
"""

from __future__ import annotations

import os
import re
import shutil
import json
from dataclasses import dataclass, field
from pathlib import Path

from .packs import (
    APP_ID,
    APP_LABEL,
    DEFAULT_DOCS_LANGUAGE,
    DEFAULT_OCP_VERSION,
    GLOBAL_SOURCE_CATALOG_NAME,
    SUPPORTED_SOURCE_CRAWLER_KINDS,
    SUPPORTED_SOURCE_CRAWLER_LANGUAGES,
    SUPPORTED_SOURCE_CRAWLER_VERSIONS,
    default_core_pack,
    resolve_ocp_core_pack,
    source_crawler_packs,
)
from .settings_paths import SettingsPathMixin


HIGH_VALUE_SLUGS = (
    "overview",
    "architecture",
    "installation_overview",
    "installing_on_any_platform",
    "disconnected_environments",
    "postinstallation_configuration",
    "updating_clusters",
    "release_notes",
    "nodes",
    "etcd",
    "operators",
    "authentication_and_authorization",
    "security_and_compliance",
    "cli_tools",
    "networking_overview",
    "advanced_networking",
    "ingress_and_load_balancing",
    "storage",
    "monitoring",
    "logging",
    "support",
    "validation_and_troubleshooting",
    "backup_and_restore",
    "machine_management",
    "machine_configuration",
    "images",
    "registry",
    "web_console",
    "observability_overview",
)
ENV_REFERENCE_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
DEFAULT_CORE_PACK = default_core_pack()
DEFAULT_BOOK_URL_TEMPLATE = DEFAULT_CORE_PACK.book_url_template
DEFAULT_VIEWER_PATH_TEMPLATE = DEFAULT_CORE_PACK.viewer_path_template
_OFFICIAL_LANE_SEED_STATE: dict[str, tuple[tuple[str, bool, int, int], ...]] = {}


def _parse_csv_tuple(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    parts = tuple(item.strip() for item in value.split(",") if item.strip())
    return parts or default


@dataclass(slots=True)
class Settings(SettingsPathMixin):
    """프로세스 한 번의 시작 기준으로 해석된 불변 런타임 설정.

    direct `Settings(...)` 생성은 고정 기본값만 사용한다.
    ambient env / `.env` 해석은 `load_settings(...)`만 담당한다.
    """

    root_dir: Path
    artifacts_dir_override: str = ""
    raw_html_dir_override: str = ""
    source_catalog_path_override: str = ""
    source_manifest_path_override: str = ""
    source_catalog_versions_override: str = ""
    source_catalog_languages_override: str = ""
    source_catalog_kinds_override: str = ""
    ocp_version: str = DEFAULT_OCP_VERSION
    docs_language: str = DEFAULT_DOCS_LANGUAGE
    docs_index_url_template: str = DEFAULT_CORE_PACK.docs_index_url_template
    book_url_template_str: str = DEFAULT_BOOK_URL_TEMPLATE
    viewer_path_template_str: str = DEFAULT_VIEWER_PATH_TEMPLATE
    user_agent: str = "Mozilla/5.0 (compatible; OCPBookStudio/1.0)"
    request_timeout_seconds: int = 30
    request_retries: int = 3
    request_backoff_seconds: int = 2
    chunk_size: int = 160
    chunk_overlap: int = 32
    embedding_base_url: str = ""
    embedding_model: str = "dragonkue/bge-m3-ko"
    embedding_device: str = "auto"
    embedding_api_key: str = ""
    embedding_batch_size: int = 32
    embedding_timeout_seconds: float = 8
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = DEFAULT_CORE_PACK.qdrant_collection
    qdrant_vector_size: int = 1024
    qdrant_distance: str = "Cosine"
    qdrant_upsert_batch_size: int = 128
    qdrant_recreate_collection: bool = False
    graph_enabled: bool = True
    graph_backend: str = "local"
    graph_uri: str = ""
    graph_username: str = ""
    graph_password: str = ""
    graph_database: str = ""
    graph_boost_top_n: int = 8
    graph_max_edge_fanout: int = 12
    llm_endpoint: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1100
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    reranker_top_n: int = 12
    reranker_batch_size: int = 8
    reranker_device: str = "auto"
    graph_runtime_mode: str = "auto"
    graph_endpoint: str = ""
    graph_api_key: str = ""
    graph_timeout_seconds: float = 5.0
    graph_sidecar_path_override: str = ""
    customer_pack_pdf_fallback_backend: str = ""
    official_html_fallback_allowed: bool = False
    allow_stale_full_rebuild_export: bool = False
    surya_ocr_endpoint: str = ""
    surya_health_endpoint: str = ""
    surya_timeout_seconds: float = 30.0

    @property
    def app_id(self) -> str:
        return APP_ID

    @property
    def app_label(self) -> str:
        return APP_LABEL

    @property
    def active_pack(self):
        return resolve_ocp_core_pack(version=self.ocp_version, language=self.docs_language)

    @property
    def active_pack_id(self) -> str:
        return self.active_pack.pack_id

    @property
    def active_pack_label(self) -> str:
        return self.active_pack.pack_label

    @property
    def viewer_path_prefix(self) -> str:
        return self.active_pack.viewer_path_prefix

    @property
    def supported_ocp_versions(self) -> tuple[str, ...]:
        return _parse_csv_tuple(
            self.source_catalog_versions_override,
            SUPPORTED_SOURCE_CRAWLER_VERSIONS,
        )

    @property
    def supported_docs_languages(self) -> tuple[str, ...]:
        return _parse_csv_tuple(
            self.source_catalog_languages_override,
            SUPPORTED_SOURCE_CRAWLER_LANGUAGES,
        )

    @property
    def supported_source_kinds(self) -> tuple[str, ...]:
        return _parse_csv_tuple(
            self.source_catalog_kinds_override,
            SUPPORTED_SOURCE_CRAWLER_KINDS,
        )

    @property
    def source_catalog_scope(self):
        return source_crawler_packs(
            versions=self.supported_ocp_versions,
            languages=self.supported_docs_languages,
        )

    @property
    def docs_index_url(self) -> str:
        return self.docs_index_url_template.format(
            version=self.ocp_version,
            lang=self.docs_language
        )

    @property
    def book_url_template(self) -> str:
        return self.book_url_template_str.format(
            version=self.ocp_version,
            lang=self.docs_language,
            slug="{slug}"
        )

    @property
    def viewer_path_template(self) -> str:
        return self.viewer_path_template_str.format(
            version=self.ocp_version,
            lang=self.docs_language,
            slug="{slug}"
        )

    @property
    def graph_sidecar_path(self) -> Path:
        return self._resolve_optional_path(
            self.graph_sidecar_path_override,
            self.retrieval_dir / "graph_sidecar.json",
        )

    @property
    def graph_sidecar_compact_path(self) -> Path:
        return self.graph_sidecar_path.with_name("graph_sidecar_compact.json")


def _path_state_signature(path: Path) -> tuple[str, bool, int, int]:
    target = Path(path).resolve()
    try:
        stat = target.stat()
    except FileNotFoundError:
        return (str(target), False, 0, 0)
    size = int(stat.st_size) if target.is_file() else 0
    return (str(target), True, int(stat.st_mtime_ns), size)


def _official_lane_source_signature(settings: Settings) -> tuple[tuple[str, bool, int, int], ...]:
    tracked_official_seed = settings.data_dir / "official_lane" / "repo_wide_official_source"
    watched_paths = (
        tracked_official_seed / "chunks.jsonl",
        tracked_official_seed / "bm25_corpus.jsonl",
        tracked_official_seed / "playbook_documents.jsonl",
        tracked_official_seed / "normalized_docs.jsonl",
        tracked_official_seed / "playbooks",
        settings.gold_corpus_ko_dir / "chunks.jsonl",
        settings.gold_corpus_ko_dir / "bm25_corpus.jsonl",
        settings.gold_manualbook_ko_dir / "playbook_documents.jsonl",
        settings.gold_manualbook_ko_dir / "playbooks",
    )
    return tuple(_path_state_signature(path) for path in watched_paths)

def load_effective_env(root_dir: str | Path) -> dict[str, str]:
    """`.env` overlay를 반영한 환경 맵을 반환한다.

    전역 `os.environ`은 건드리지 않고, 호출자가 필요한 곳에만 같은 해석 결과를
    재사용할 수 있게 만든다.
    """

    root_path = Path(root_dir)
    env_path = root_path / ".env"
    effective_env: dict[str, str] = dict(os.environ)
    if not env_path.exists():
        return effective_env

    raw_values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        raw_values[key.strip()] = value.strip().strip('"').strip("'")

    resolved_values: dict[str, str] = {}

    def resolve_value(key: str, stack: set[str]) -> str:
        cached = resolved_values.get(key)
        if cached is not None:
            return cached
        raw_value = raw_values.get(key, "")
        if key in stack:
            return raw_value

        def replace_reference(match: re.Match[str]) -> str:
            reference = match.group(1) or match.group(2) or ""
            if reference in raw_values:
                return resolve_value(reference, stack | {key})
            return effective_env.get(reference, "")

        resolved = ENV_REFERENCE_RE.sub(replace_reference, raw_value)
        resolved_values[key] = resolved
        return resolved

    for key in raw_values:
        effective_env[key] = resolve_value(key, set())
    return effective_env


def _copy_missing_tree(src_root: Path, dst_root: Path) -> bool:
    if not src_root.exists() or not src_root.is_dir():
        return False
    copied = False
    for src_path in src_root.rglob("*"):
        if not src_path.is_file():
            continue
        relative = src_path.relative_to(src_root)
        dst_path = dst_root / relative
        if dst_path.exists():
            continue
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        copied = True
    return copied


def _copy_missing_file(src_path: Path, dst_path: Path) -> bool:
    if not src_path.exists() or not src_path.is_file() or dst_path.exists():
        return False
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dst_path)
    return True


def _append_missing_jsonl_book_rows(src_path: Path, dst_path: Path) -> bool:
    if not src_path.exists() or not src_path.is_file():
        return False
    existing_slugs: set[str] = set()
    if dst_path.exists() and dst_path.is_file():
        for raw_line in dst_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except Exception:
                continue
            slug = str(payload.get("book_slug") or "").strip()
            if slug:
                existing_slugs.add(slug)

    appended = False
    rows_to_append: list[str] = []
    for raw_line in src_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except Exception:
            continue
        slug = str(payload.get("book_slug") or "").strip()
        if not slug or slug in existing_slugs:
            continue
        existing_slugs.add(slug)
        rows_to_append.append(raw_line)
    if not rows_to_append:
        return False
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with dst_path.open("a", encoding="utf-8") as handle:
        for raw_line in rows_to_append:
            handle.write(raw_line)
            if not raw_line.endswith("\n"):
                handle.write("\n")
    return True


def _has_official_lane_seed(target_root: Path) -> bool:
    return (
        (target_root / "chunks.jsonl").exists()
        and (target_root / "bm25_corpus.jsonl").exists()
        and (target_root / "playbook_documents.jsonl").exists()
        and any((target_root / "playbooks").glob("*.json"))
    )


def _ensure_official_lane_seed(settings: Settings) -> None:
    target_root = settings.artifacts_dir / "official_lane" / "repo_wide_official_source"
    target_root.mkdir(parents=True, exist_ok=True)
    seed_key = str(target_root.resolve())
    source_signature = _official_lane_source_signature(settings)
    if _OFFICIAL_LANE_SEED_STATE.get(seed_key) == source_signature and _has_official_lane_seed(target_root):
        return

    tracked_official_seed = settings.data_dir / "official_lane" / "repo_wide_official_source"
    if tracked_official_seed.exists() and tracked_official_seed.is_dir():
        _append_missing_jsonl_book_rows(
            tracked_official_seed / "chunks.jsonl",
            target_root / "chunks.jsonl",
        )
        _append_missing_jsonl_book_rows(
            tracked_official_seed / "bm25_corpus.jsonl",
            target_root / "bm25_corpus.jsonl",
        )
        _append_missing_jsonl_book_rows(
            tracked_official_seed / "playbook_documents.jsonl",
            target_root / "playbook_documents.jsonl",
        )
        _copy_missing_file(
            tracked_official_seed / "normalized_docs.jsonl",
            target_root / "normalized_docs.jsonl",
        )
        _copy_missing_tree(
            tracked_official_seed / "playbooks",
            target_root / "playbooks",
        )
        if _has_official_lane_seed(target_root):
            _OFFICIAL_LANE_SEED_STATE[seed_key] = source_signature
            return

    _append_missing_jsonl_book_rows(
        settings.gold_corpus_ko_dir / "chunks.jsonl",
        target_root / "chunks.jsonl",
    )
    _append_missing_jsonl_book_rows(
        settings.gold_corpus_ko_dir / "bm25_corpus.jsonl",
        target_root / "bm25_corpus.jsonl",
    )
    _append_missing_jsonl_book_rows(
        settings.gold_manualbook_ko_dir / "playbook_documents.jsonl",
        target_root / "playbook_documents.jsonl",
    )
    _copy_missing_tree(
        settings.gold_manualbook_ko_dir / "playbooks",
        target_root / "playbooks",
    )
    _OFFICIAL_LANE_SEED_STATE[seed_key] = source_signature


def load_settings(root_dir: str | Path) -> Settings:
    # `.env`를 읽어 별도 overlay로 해석하고, `os.environ` 자체는 건드리지 않는다.
    # 그래야 endpoint 변경이 재현 가능하고 숨은 전역 부작용을 막을 수 있다.
    # 여기서 해석하는 endpoint는 main chat/runtime용이다.
    # RAGAS judge용 OPENAI_* 설정은 evals/ragas_eval.py가 별도로 읽는다.
    root_path = Path(root_dir)
    effective_env = load_effective_env(root_path)

    settings = Settings(
        root_dir=root_path,
        artifacts_dir_override=effective_env.get("ARTIFACTS_DIR", "").strip(),
        raw_html_dir_override=effective_env.get("RAW_HTML_DIR", "").strip(),
        source_catalog_path_override=effective_env.get("SOURCE_CATALOG_PATH", "").strip(),
        source_manifest_path_override=effective_env.get("SOURCE_MANIFEST_PATH", "").strip(),
        source_catalog_versions_override=effective_env.get("SOURCE_CATALOG_VERSIONS", "").strip(),
        source_catalog_languages_override=effective_env.get("SOURCE_CATALOG_LANGUAGES", "").strip(),
        source_catalog_kinds_override=effective_env.get("SOURCE_CATALOG_KINDS", "").strip(),
        ocp_version=effective_env.get("OCP_VERSION", DEFAULT_OCP_VERSION).strip(),
        docs_language=effective_env.get("DOCS_LANGUAGE", DEFAULT_DOCS_LANGUAGE).strip(),
        book_url_template_str=effective_env.get("BOOK_URL_TEMPLATE", DEFAULT_BOOK_URL_TEMPLATE),
        viewer_path_template_str=effective_env.get("VIEWER_PATH_TEMPLATE", DEFAULT_VIEWER_PATH_TEMPLATE),
        embedding_base_url=effective_env.get("EMBEDDING_BASE_URL", "").strip().rstrip("/"),
        embedding_model=effective_env.get("EMBEDDING_MODEL", "dragonkue/bge-m3-ko"),
        embedding_device=effective_env.get("EMBEDDING_DEVICE", "auto").strip(),
        embedding_api_key=effective_env.get("EMBEDDING_API_KEY", "").strip(),
        embedding_batch_size=int(effective_env.get("EMBEDDING_BATCH_SIZE", "32")),
        embedding_timeout_seconds=float(effective_env.get("EMBEDDING_TIMEOUT_SECONDS", "8")),
        qdrant_url=effective_env.get("QDRANT_URL", "http://localhost:6333").rstrip("/"),
        qdrant_collection=effective_env.get("QDRANT_COLLECTION", DEFAULT_CORE_PACK.qdrant_collection),
        qdrant_vector_size=int(effective_env.get("QDRANT_VECTOR_SIZE", "1024")),
        qdrant_distance=effective_env.get("QDRANT_DISTANCE", "Cosine"),
        qdrant_upsert_batch_size=int(effective_env.get("QDRANT_UPSERT_BATCH_SIZE", "128")),
        qdrant_recreate_collection=effective_env.get("QDRANT_RECREATE_COLLECTION", "false").lower()
        in {"1", "true", "yes", "on"},
        graph_enabled=effective_env.get("GRAPH_ENABLED", "true").lower()
        in {"1", "true", "yes", "on"},
        graph_backend=effective_env.get("GRAPH_BACKEND", "local").strip().lower() or "local",
        graph_uri=effective_env.get("GRAPH_URI", "").strip(),
        graph_username=effective_env.get("GRAPH_USERNAME", "").strip(),
        graph_password=effective_env.get("GRAPH_PASSWORD", "").strip(),
        graph_database=effective_env.get("GRAPH_DATABASE", "").strip(),
        graph_boost_top_n=int(effective_env.get("GRAPH_BOOST_TOP_N", "8")),
        graph_max_edge_fanout=int(effective_env.get("GRAPH_MAX_EDGE_FANOUT", "12")),
        llm_endpoint=effective_env.get("LLM_ENDPOINT", "").strip().rstrip("/"),
        llm_api_key=effective_env.get("LLM_API_KEY", "").strip(),
        llm_model=effective_env.get("LLM_MODEL", "").strip(),
        llm_temperature=float(effective_env.get("LLM_TEMPERATURE", "0.2")),
        llm_max_tokens=int(effective_env.get("LLM_MAX_TOKENS", "1100")),
        reranker_enabled=effective_env.get("RERANKER_ENABLED", "false").lower()
        in {"1", "true", "yes", "on"},
        reranker_model=effective_env.get(
            "RERANKER_MODEL",
            "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        ).strip(),
        reranker_top_n=int(effective_env.get("RERANKER_TOP_N", "12")),
        reranker_batch_size=int(effective_env.get("RERANKER_BATCH_SIZE", "8")),
        reranker_device=effective_env.get("RERANKER_DEVICE", "auto").strip(),
        graph_runtime_mode=effective_env.get("GRAPH_RUNTIME_MODE", "auto").strip().lower() or "auto",
        graph_endpoint=effective_env.get("GRAPH_ENDPOINT", "").strip().rstrip("/"),
        graph_api_key=effective_env.get("GRAPH_API_KEY", "").strip(),
        graph_timeout_seconds=float(effective_env.get("GRAPH_TIMEOUT_SECONDS", "5")),
        graph_sidecar_path_override=effective_env.get("GRAPH_SIDECAR_PATH", "").strip(),
        customer_pack_pdf_fallback_backend=effective_env.get(
            "PBS_CUSTOMER_PACK_PDF_FALLBACK_BACKEND",
            "",
        ).strip().lower(),
        official_html_fallback_allowed=effective_env.get(
            "PBS_OFFICIAL_HTML_FALLBACK_ALLOWED",
            "false",
        ).lower() in {"1", "true", "yes", "on"},
        allow_stale_full_rebuild_export=effective_env.get(
            "PBS_ALLOW_STALE_FULL_REBUILD_EXPORT",
            "false",
        ).lower() in {"1", "true", "yes", "on"},
        surya_ocr_endpoint=effective_env.get("SURYA_OCR", "").strip().rstrip("/"),
        surya_health_endpoint=effective_env.get("SURYA_HEALTH", "").strip().rstrip("/"),
        surya_timeout_seconds=float(effective_env.get("SURYA_TIMEOUT_SECONDS", "30")),
    )
    _ensure_official_lane_seed(settings)
    return settings
