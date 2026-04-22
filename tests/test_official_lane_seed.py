from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from play_book_studio.app.data_control_room import build_data_control_room_payload
from play_book_studio.config.settings import load_settings


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_tracked_gold(
    root: Path,
    *,
    slug: str,
    title: str,
    label: str,
) -> None:
    _write_text(
        root / "data" / "gold_corpus_ko" / "chunks.jsonl",
        json.dumps(
            {
                "book_slug": slug,
                "book_title": title,
                "anchor_id": f"{label}-anchor",
                "chunk_type": "paragraph",
                "token_count": 12,
            },
            ensure_ascii=False,
        )
        + "\n",
    )
    _write_text(
        root / "data" / "gold_corpus_ko" / "bm25_corpus.jsonl",
        json.dumps(
            {
                "book_slug": slug,
                "text": f"{label} bm25",
            },
            ensure_ascii=False,
        )
        + "\n",
    )
    _write_text(
        root / "data" / "gold_manualbook_ko" / "playbook_documents.jsonl",
        json.dumps(
            {
                "book_slug": slug,
                "title": title,
                "review_status": "approved",
                "translation_status": "approved_ko",
                "source_metadata": {
                    "approval_state": "approved",
                    "publication_state": "published",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
    )
    _write_json(
        root / "data" / "gold_manualbook_ko" / "playbooks" / f"{slug}.json",
        {
            "book_slug": slug,
            "title": title,
            "viewer_path": f"/viewer/{slug}",
            "review_status": "approved",
            "translation_status": "approved_ko",
            "sections": [],
            "source_metadata": {
                "approval_state": "approved",
                "publication_state": "published",
            },
        },
    )


def _write_tracked_official_seed(
    root: Path,
    *,
    slug: str,
    title: str,
) -> None:
    seed_root = root / "data" / "official_lane" / "repo_wide_official_source"
    _write_text(
        seed_root / "chunks.jsonl",
        json.dumps(
            {
                "book_slug": slug,
                "book_title": title,
                "anchor_id": "official-anchor",
                "chunk_type": "paragraph",
                "token_count": 21,
            },
            ensure_ascii=False,
        )
        + "\n",
    )
    _write_text(
        seed_root / "bm25_corpus.jsonl",
        json.dumps(
            {
                "book_slug": slug,
                "text": "official bm25",
            },
            ensure_ascii=False,
        )
        + "\n",
    )
    _write_text(
        seed_root / "playbook_documents.jsonl",
        json.dumps(
            {
                "book_slug": slug,
                "title": title,
                "review_status": "approved",
                "translation_status": "approved_ko",
                "source_metadata": {
                    "approval_state": "approved",
                    "publication_state": "published",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
    )
    _write_json(
        seed_root / "playbooks" / f"{slug}.json",
        {
            "book_slug": slug,
            "title": title,
            "sections": [],
            "source_metadata": {
                "approval_state": "approved",
                "publication_state": "published",
            },
        },
    )


def _write_source_manifest(root: Path, *, slug: str, title: str) -> None:
    _write_json(
        root / "manifests" / "source_manifest.json",
        {
            "entries": [
                {
                    "book_slug": slug,
                    "title": title,
                    "content_status": "approved_ko",
                    "translation_status": "approved_ko",
                    "review_status": "approved",
                    "approval_state": "approved",
                    "approval_status": "approved",
                    "publication_state": "published",
                    "source_type": "official_doc",
                    "source_lane": "official_lane",
                    "viewer_path": f"/docs/{slug}",
                }
            ]
        },
    )
    _write_text(root / ".env", "SOURCE_MANIFEST_PATH=manifests/source_manifest.json\n")


def test_load_settings_seeds_official_lane_from_tracked_gold() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_tracked_gold(root, slug="legacy-book", title="Legacy Book", label="legacy")

        settings = load_settings(root)
        official_root = settings.official_lane_repo_wide_dir

        assert (official_root / "chunks.jsonl").exists()
        assert (official_root / "bm25_corpus.jsonl").exists()
        assert (official_root / "playbook_documents.jsonl").exists()
        assert (official_root / "playbooks" / "legacy-book.json").exists()
        assert settings.chunks_path == (official_root / "chunks.jsonl").resolve()
        assert settings.playbook_documents_path == (official_root / "playbook_documents.jsonl").resolve()
        assert settings.playbook_books_dir == (official_root / "playbooks").resolve()


def test_load_settings_prefers_tracked_official_seed_when_present() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_tracked_gold(root, slug="legacy-book", title="Legacy Book", label="legacy")
        _write_tracked_official_seed(root, slug="official-book", title="Official Book")

        settings = load_settings(root)
        official_root = settings.official_lane_repo_wide_dir

        assert "official-book" in (official_root / "chunks.jsonl").read_text(encoding="utf-8")
        assert "legacy-book" not in (official_root / "chunks.jsonl").read_text(encoding="utf-8")
        assert (official_root / "playbooks" / "official-book.json").exists()
        assert not (official_root / "playbooks" / "legacy-book.json").exists()


def test_load_settings_backfills_stale_official_lane_from_tracked_gold() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_tracked_gold(root, slug="missing-book", title="Missing Book", label="missing")
        stale_root = root / "artifacts" / "official_lane" / "repo_wide_official_source"
        _write_text(
            stale_root / "chunks.jsonl",
            json.dumps(
                {
                    "book_slug": "stale-book",
                    "book_title": "Stale Book",
                    "anchor_id": "stale-anchor",
                    "chunk_type": "paragraph",
                    "token_count": 7,
                },
                ensure_ascii=False,
            )
            + "\n",
        )
        _write_text(
            stale_root / "bm25_corpus.jsonl",
            json.dumps(
                {
                    "book_slug": "stale-book",
                    "text": "stale bm25",
                },
                ensure_ascii=False,
            )
            + "\n",
        )
        _write_text(
            stale_root / "playbook_documents.jsonl",
            json.dumps(
                {
                    "book_slug": "stale-book",
                    "title": "Stale Book",
                    "review_status": "approved",
                    "translation_status": "approved_ko",
                    "source_metadata": {
                        "approval_state": "approved",
                        "publication_state": "published",
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
        )
        _write_json(
            stale_root / "playbooks" / "stale-book.json",
            {
                "book_slug": "stale-book",
                "title": "Stale Book",
                "sections": [],
                "source_metadata": {
                    "approval_state": "approved",
                    "publication_state": "published",
                },
            },
        )

        settings = load_settings(root)
        official_root = settings.official_lane_repo_wide_dir

        chunks_text = (official_root / "chunks.jsonl").read_text(encoding="utf-8")
        playbook_documents_text = (official_root / "playbook_documents.jsonl").read_text(encoding="utf-8")
        assert "stale-book" in chunks_text
        assert "missing-book" in chunks_text
        assert "missing-book" in playbook_documents_text
        assert (official_root / "playbooks" / "missing-book.json").exists()


def test_load_settings_skips_reseeding_when_sources_are_unchanged() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_tracked_gold(root, slug="cached-book", title="Cached Book", label="cached")

        settings = load_settings(root)
        official_root = settings.official_lane_repo_wide_dir

        assert (official_root / "chunks.jsonl").exists()
        assert (official_root / "playbooks" / "cached-book.json").exists()

        with (
            patch(
                "play_book_studio.config.settings._append_missing_jsonl_book_rows",
                side_effect=AssertionError("seed refresh should be skipped"),
            ),
            patch(
                "play_book_studio.config.settings._copy_missing_tree",
                side_effect=AssertionError("seed refresh should be skipped"),
            ),
            patch(
                "play_book_studio.config.settings._copy_missing_file",
                side_effect=AssertionError("seed refresh should be skipped"),
            ),
        ):
            repeat_settings = load_settings(root)

        assert repeat_settings.official_lane_repo_wide_dir == official_root


def test_data_control_room_uses_manifest_runtime_fallback_without_source_report() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_source_manifest(root, slug="demo-book", title="Demo Book")
        _write_tracked_gold(root, slug="demo-book", title="Demo Book", label="demo")

        payload = build_data_control_room_payload(root)

        assert payload["summary"]["gold_book_count"] == 1
        assert payload["summary"]["known_book_count"] == 1
        assert payload["gold_books"][0]["book_slug"] == "demo-book"
        assert payload["gold_books"][0]["title"] == "Demo Book"


def test_data_control_room_hides_manifest_only_books_without_materialized_assets() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write_source_manifest(root, slug="demo-book", title="Demo Book")

        payload = build_data_control_room_payload(root)

        assert payload["summary"]["approved_runtime_count"] == 0
        assert payload["summary"]["known_book_count"] == 0
        assert payload["summary"]["gold_book_count"] == 0
        assert payload["summary"]["approved_wiki_runtime_book_count"] == 0
        assert payload["gold_books"] == []
        assert payload["known_books"] == []
        assert payload["manualbooks"]["books"] == []
        assert payload["corpus"]["books"] == []
        assert payload["materialization"]["missing_corpus_books"] == ["demo-book"]
        assert payload["materialization"]["missing_manualbook_books"] == ["demo-book"]
