from __future__ import annotations

import json
import socket
import time
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import requests

from play_book_studio.config.settings import Settings, load_effective_env
from play_book_studio.ingestion.embedding import EmbeddingClient
from play_book_studio.ingestion.models import ChunkRecord
from play_book_studio.ingestion.qdrant_store import ensure_collection, upsert_chunks


def _wait_for_tcp(host: str, port: int, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def _wait_for_qdrant(settings: Settings, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    url = f"{settings.qdrant_url}/collections"
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=min(settings.request_timeout_seconds, 5))
            if response.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def _qdrant_point_count(settings: Settings) -> int:
    response = requests.post(
        f"{settings.qdrant_url}/collections/{settings.qdrant_collection}/points/count",
        json={"exact": True},
        timeout=max(settings.request_timeout_seconds, 30),
    )
    if response.status_code == 404:
        return 0
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") if isinstance(payload, dict) else {}
    return int((result or {}).get("count") or 0)


def _coerce_chunk_record(row: dict[str, Any]) -> ChunkRecord:
    allowed = {field.name for field in fields(ChunkRecord)}
    payload = {key: value for key, value in row.items() if key in allowed}
    payload["section_path"] = tuple(payload.get("section_path", []))
    payload["access_groups"] = tuple(payload.get("access_groups", []))
    payload["cli_commands"] = tuple(payload.get("cli_commands", []))
    payload["error_strings"] = tuple(payload.get("error_strings", []))
    payload["k8s_objects"] = tuple(payload.get("k8s_objects", []))
    payload["operator_names"] = tuple(payload.get("operator_names", []))
    payload["verification_hints"] = tuple(payload.get("verification_hints", []))
    return ChunkRecord(**payload)


def _load_chunk_records(path: Path) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            normalized = line.strip()
            if not normalized:
                continue
            records.append(_coerce_chunk_record(json.loads(normalized)))
    return records


def _bootstrap_report_path(settings: Settings) -> Path:
    return settings.runtime_dir / "bootstrap_runtime.json"


def bootstrap_runtime_dependencies(
    settings: Settings,
    *,
    root_dir: Path,
    postgres_timeout_seconds: float = 60,
    qdrant_timeout_seconds: float = 60,
) -> dict[str, Any]:
    effective_env = load_effective_env(root_dir)
    db_host = str(effective_env.get("DB_HOST") or "").strip()
    db_port = int(str(effective_env.get("DB_PORT") or "5432").strip() or "5432")

    report: dict[str, Any] = {
        "postgres": {
            "configured": bool(db_host),
            "host": db_host,
            "port": db_port,
            "ready": False,
        },
        "qdrant": {
            "url": settings.qdrant_url,
            "collection": settings.qdrant_collection,
            "ready": False,
            "point_count_before": 0,
            "point_count_after": 0,
            "upserted_count": 0,
            "bootstrap_source": str(settings.chunks_path),
        },
    }

    if db_host:
        report["postgres"]["ready"] = _wait_for_tcp(
            db_host,
            db_port,
            timeout_seconds=postgres_timeout_seconds,
        )
        if not report["postgres"]["ready"]:
            raise RuntimeError(f"Postgres is not reachable at {db_host}:{db_port}")

    if not _wait_for_qdrant(settings, timeout_seconds=qdrant_timeout_seconds):
        raise RuntimeError(f"Qdrant is not reachable at {settings.qdrant_url}")

    qdrant_settings = replace(settings, qdrant_recreate_collection=False)
    ensure_collection(qdrant_settings)
    report["qdrant"]["ready"] = True
    report["qdrant"]["point_count_before"] = _qdrant_point_count(qdrant_settings)

    if report["qdrant"]["point_count_before"] == 0:
        chunk_path = settings.chunks_path
        if not chunk_path.exists():
            raise FileNotFoundError(f"Runtime chunk corpus is missing: {chunk_path}")
        records = _load_chunk_records(chunk_path)
        if not records:
            raise RuntimeError(f"Runtime chunk corpus is empty: {chunk_path}")
        vectors = EmbeddingClient(settings).embed_texts((record.text for record in records))
        report["qdrant"]["upserted_count"] = upsert_chunks(qdrant_settings, records, vectors)

    report["qdrant"]["point_count_after"] = _qdrant_point_count(qdrant_settings)
    output_path = _bootstrap_report_path(settings)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(output_path)
    return report


__all__ = [
    "bootstrap_runtime_dependencies",
]
