from __future__ import annotations

import json
from pathlib import Path
import shutil
from unittest.mock import patch

from play_book_studio.app.runtime_bootstrap import bootstrap_runtime_dependencies
from play_book_studio.config.settings import load_settings


class _FakeEmbeddingClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    def embed_texts(self, texts):
        return [[0.1, 0.2] for _ in texts]


def _write_chunk_corpus(root: Path) -> None:
    target = root / "data" / "gold_corpus_ko" / "chunks.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "chunk_id": "chunk-1",
        "book_slug": "overview",
        "book_title": "Overview",
        "chapter": "Chapter 1",
        "section": "Section A",
        "anchor": "section-a",
        "source_url": "https://example.com",
        "viewer_path": "/docs/ocp/4.20/ko/overview/index.html#section-a",
        "text": "OpenShift overview",
        "token_count": 2,
        "ordinal": 1,
        "section_path": ["Chapter 1", "Section A"],
        "access_groups": ["public"],
    }
    target.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _fresh_test_root(name: str) -> Path:
    root = Path.cwd() / ".tmp-test-runtime-bootstrap" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_bootstrap_runtime_upserts_qdrant_when_collection_is_empty() -> None:
    root = _fresh_test_root("upserts-when-empty")
    (root / ".env").write_text(
        "\n".join(
            [
                "DB_HOST=postgres",
                "DB_PORT=5432",
                "EMBEDDING_BASE_URL=http://embedding.local/v1",
                "QDRANT_URL=http://qdrant:6333",
            ]
        ),
        encoding="utf-8",
    )
    _write_chunk_corpus(root)
    settings = load_settings(root)

    point_counts = iter((0, 1))
    upsert_calls: list[int] = []

    with (
        patch("play_book_studio.app.runtime_bootstrap._wait_for_tcp", return_value=True),
        patch("play_book_studio.app.runtime_bootstrap._wait_for_qdrant", return_value=True),
        patch("play_book_studio.app.runtime_bootstrap._qdrant_point_count", side_effect=lambda *args, **kwargs: next(point_counts)),
        patch("play_book_studio.app.runtime_bootstrap.ensure_collection"),
        patch("play_book_studio.app.runtime_bootstrap.EmbeddingClient", _FakeEmbeddingClient),
        patch(
            "play_book_studio.app.runtime_bootstrap.upsert_chunks",
            side_effect=lambda settings, records, vectors: upsert_calls.append(len(records)) or len(records),
        ),
    ):
        report = bootstrap_runtime_dependencies(settings, root_dir=root)

        assert report["postgres"]["ready"] is True
        assert report["qdrant"]["point_count_before"] == 0
        assert report["qdrant"]["upserted_count"] == 1
        assert report["qdrant"]["point_count_after"] == 1
        assert upsert_calls == [1]


def test_bootstrap_runtime_skips_qdrant_upsert_when_collection_has_points() -> None:
    root = _fresh_test_root("skips-when-populated")
    (root / ".env").write_text(
        "\n".join(
            [
                "DB_HOST=postgres",
                "DB_PORT=5432",
                "EMBEDDING_BASE_URL=http://embedding.local/v1",
                "QDRANT_URL=http://qdrant:6333",
            ]
        ),
        encoding="utf-8",
    )
    _write_chunk_corpus(root)
    settings = load_settings(root)

    with (
        patch("play_book_studio.app.runtime_bootstrap._wait_for_tcp", return_value=True),
        patch("play_book_studio.app.runtime_bootstrap._wait_for_qdrant", return_value=True),
        patch("play_book_studio.app.runtime_bootstrap._qdrant_point_count", return_value=8),
        patch("play_book_studio.app.runtime_bootstrap.ensure_collection"),
        patch("play_book_studio.app.runtime_bootstrap.EmbeddingClient", _FakeEmbeddingClient),
        patch(
            "play_book_studio.app.runtime_bootstrap.upsert_chunks",
            side_effect=AssertionError("upsert should not run"),
        ),
    ):
        report = bootstrap_runtime_dependencies(settings, root_dir=root)

        assert report["qdrant"]["point_count_before"] == 8
        assert report["qdrant"]["upserted_count"] == 0
        assert report["qdrant"]["point_count_after"] == 8
