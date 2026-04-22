from __future__ import annotations

from play_book_studio.ingestion.json_io import dump_compact_json
from play_book_studio.ingestion.models import ChunkRecord, chunk_corpus_bm25_row


def _chunk_record() -> ChunkRecord:
    return ChunkRecord(
        chunk_id="chunk-1",
        book_slug="advanced_networking",
        book_title="Advanced Networking",
        chapter="Networking",
        section="Egress IP",
        anchor="egress-ip",
        source_url="https://docs.example/advanced-networking",
        viewer_path="/docs/ocp/4.20/ko/advanced_networking/index.html#egress-ip",
        text="Egress IP lets you pin egress traffic to selected node addresses.",
        token_count=17,
        ordinal=0,
        section_id="section-egress-ip",
        section_path=("Networking", "Egress IP"),
        chunk_type="procedure",
        source_id="official:advanced_networking",
        source_lane="official_ko",
        source_type="official_doc",
        source_collection="core",
        product="openshift",
        version="4.20",
        locale="ko",
        source_language="ko",
        display_language="ko",
        translation_status="approved_ko",
        translation_stage="approved_ko",
        translation_source_language="en",
        translation_source_url="https://docs.example/en/advanced-networking",
        translation_source_fingerprint="fingerprint-1",
        original_title="Advanced networking",
        legal_notice_url="https://docs.example/legal",
        license_or_terms="Apache License 2.0",
        review_status="approved",
        trust_score=0.98,
        verifiability="anchor_backed",
        updated_at="2026-04-22T00:00:00Z",
        parsed_artifact_id="parsed:advanced_networking",
        tenant_id="public",
        workspace_id="core",
        parent_pack_id="openshift-4.20-core",
        pack_version="4.20",
        bundle_scope="official",
        classification="public",
        access_groups=("public",),
        provider_egress_policy="unspecified",
        approval_state="approved",
        publication_state="published",
        redaction_state="not_required",
        citation_eligible=True,
        citation_block_reason="",
        cli_commands=("oc get egressip",),
        verification_hints=("check assigned node",),
    )


def test_chunk_record_to_corpus_row_drops_redundant_metadata() -> None:
    row = _chunk_record().to_corpus_row()

    assert "anchor_id" not in row
    assert "translation_source_url" not in row
    assert "translation_source_fingerprint" not in row
    assert "translation_status" not in row
    assert "translation_stage" not in row
    assert "product" not in row
    assert "version" not in row
    assert "locale" not in row
    assert "citation_eligible" not in row
    assert "citation_block_reason" not in row

    assert row["chunk_id"] == "chunk-1"
    assert row["book_slug"] == "advanced_networking"
    assert row["token_count"] == 17
    assert row["ordinal"] == 0
    assert row["parsed_artifact_id"] == "parsed:advanced_networking"
    assert row["approval_state"] == "approved"
    assert row["publication_state"] == "published"


def test_chunk_corpus_bm25_row_backfills_defaults_for_compact_rows() -> None:
    row = _chunk_record().to_corpus_row()

    bm25_row = chunk_corpus_bm25_row(row)

    assert bm25_row["chunk_id"] == "chunk-1"
    assert bm25_row["book_slug"] == "advanced_networking"
    assert "translation_status" not in bm25_row
    assert "product" not in bm25_row
    assert "version" not in bm25_row
    assert "locale" not in bm25_row
    assert bm25_row["semantic_role"] == "procedure"


def test_dump_compact_json_uses_compact_separators() -> None:
    payload = {
        "book_slug": "advanced_networking",
        "section_path": ["Networking", "Egress IP"],
        "trust_score": 0.98,
    }

    assert dump_compact_json(payload) == (
        '{"book_slug":"advanced_networking","section_path":["Networking","Egress IP"],'
        '"trust_score":0.98}'
    )
