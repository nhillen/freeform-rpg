"""Tests for Stage 5: Lore Enrichment."""

import pytest
from pathlib import Path

from src.ingest.models import (
    ContentType, EntityRegistry, Route,
    SegmentEntry, SegmentManifest,
)
from src.ingest.enrich import LoreEnricher


def _make_lore_manifest():
    """Create a manifest with lore-routed segments."""
    segments = [
        SegmentEntry(
            id="seg_0001",
            title="The Neon Dragon Bar",
            content="A seedy bar in the heart of the neon district. "
                    "Viktor Kozlov runs the back room operations. "
                    "The bar is known for its cheap synth-beer.",
            source_section="Locations",
            page_start=1, page_end=3,
            word_count=50,
            content_type=ContentType.LOCATION,
            route=Route.LORE,
        ),
        SegmentEntry(
            id="seg_0002",
            title="Viktor Kozlov",
            content="A dangerous enforcer with connections to the "
                    "Red Dragon syndicate. Age 45. Background: ex-military.",
            source_section="NPCs",
            page_start=4, page_end=5,
            word_count=30,
            content_type=ContentType.NPC,
            route=Route.LORE,
        ),
    ]
    return SegmentManifest(segments=segments, total_words=80)


class TestLoreEnricher:
    def test_enrich_without_llm(self, tmp_path):
        manifest = _make_lore_manifest()

        enricher = LoreEnricher()
        enriched_files, registry = enricher.enrich(manifest, tmp_path / "output")

        assert len(enriched_files) == 2
        assert len(registry.entities) == 2

        # Check entity types
        bar = registry.get("the_neon_dragon_bar")
        assert bar is not None
        assert bar.entity_type == "location"

        viktor = registry.get("viktor_kozlov")
        assert viktor is not None
        assert viktor.entity_type == "npc"

    def test_enriched_files_have_frontmatter(self, tmp_path):
        manifest = _make_lore_manifest()

        enricher = LoreEnricher()
        enriched_files, _ = enricher.enrich(manifest, tmp_path / "output")

        for ef in enriched_files:
            assert "frontmatter" in ef
            assert "title" in ef["frontmatter"]
            assert "type" in ef["frontmatter"]
            assert "entity_id" in ef["frontmatter"]

    def test_enriched_files_written_to_disk(self, tmp_path):
        manifest = _make_lore_manifest()

        enricher = LoreEnricher()
        enriched_files, _ = enricher.enrich(manifest, tmp_path / "output")

        for ef in enriched_files:
            assert Path(ef["path"]).exists()

    def test_entity_registry_written(self, tmp_path):
        manifest = _make_lore_manifest()

        enricher = LoreEnricher()
        enricher.enrich(manifest, tmp_path / "output")

        registry_path = tmp_path / "output" / "entity_registry.json"
        assert registry_path.exists()

    def test_empty_manifest(self, tmp_path):
        manifest = SegmentManifest(segments=[], total_words=0)

        enricher = LoreEnricher()
        enriched_files, registry = enricher.enrich(manifest, tmp_path / "output")

        assert enriched_files == []
        assert len(registry.entities) == 0

    def test_systems_only_segments_skipped(self, tmp_path):
        segments = [
            SegmentEntry(
                id="seg_sys",
                title="Resolution Rules",
                content="Roll 2d6 + modifier.",
                source_section="Rules",
                page_start=1, page_end=1,
                word_count=20,
                content_type=ContentType.RULES,
                route=Route.SYSTEMS,
            ),
        ]
        manifest = SegmentManifest(segments=segments, total_words=20)

        enricher = LoreEnricher()
        enriched_files, registry = enricher.enrich(manifest, tmp_path / "output")

        # Systems-only segments should not be enriched
        assert len(enriched_files) == 0
