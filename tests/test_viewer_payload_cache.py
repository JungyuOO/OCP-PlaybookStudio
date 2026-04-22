from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from play_book_studio.app.source_books_viewer_resolver import _load_playbook_book


def test_load_playbook_book_reuses_cached_json_payload() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        playbook_path = root / "data" / "gold_manualbook_ko" / "playbooks" / "cached-book.json"
        playbook_path.parent.mkdir(parents=True, exist_ok=True)
        playbook_path.write_text(
            json.dumps(
                {
                    "book_slug": "cached-book",
                    "title": "Cached Book",
                    "sections": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        first = _load_playbook_book(root, "cached-book")
        assert first is not None
        assert first["title"] == "Cached Book"

        with patch(
            "pathlib.Path.read_text",
            side_effect=AssertionError("cached payload should avoid rereading the playbook json"),
        ):
            second = _load_playbook_book(root, "cached-book")

        assert second is not None
        assert second["title"] == "Cached Book"
