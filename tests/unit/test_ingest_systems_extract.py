"""Tests for Stage S1: Systems Extraction."""

import pytest
from pathlib import Path

from src.ingest.models import ContentType, Route, SegmentEntry, SegmentManifest
from src.ingest.systems_extract import SystemsExtractor


def _make_systems_manifest():
    """Create a manifest with systems-routed segments."""
    segments = [
        SegmentEntry(
            id="seg_rules",
            title="Resolution Mechanics",
            content=(
                "Roll 2d6 + modifier to resolve actions.\n"
                "10+: critical success. The action succeeds spectacularly.\n"
                "7-9: mixed success. Success with a complication.\n"
                "6-: failure. The action fails with consequences.\n"
                "+2 to stealth in darkness.\n"
                "-1 to combat when wounded."
            ),
            source_section="Rules",
            page_start=1, page_end=3,
            word_count=100,
            content_type=ContentType.RULES,
            route=Route.SYSTEMS,
        ),
        SegmentEntry(
            id="seg_clocks",
            title="Clock System",
            content=(
                "Heat clock: 0/10\n"
                "Time clock: 0/6\n"
                "Harm clock: 0/4\n"
                "At 5: police response escalates.\n"
                "When 10: SWAT team deployed.\n"
                "Escalation triggers when heat reaches threshold."
            ),
            source_section="Mechanics",
            page_start=4, page_end=5,
            word_count=80,
            content_type=ContentType.RULES,
            route=Route.SYSTEMS,
        ),
    ]
    return SegmentManifest(segments=segments, total_words=180)


class TestSystemsExtractor:
    def test_extract_resolution(self, tmp_path):
        manifest = _make_systems_manifest()

        extractor = SystemsExtractor()
        result = extractor.extract(manifest, tmp_path / "output")

        assert "resolution" in result.extractions
        res = result.extractions["resolution"]
        assert "2d6" in res["dice"]
        assert len(res["outcome_bands"]) > 0

    def test_extract_clocks(self, tmp_path):
        manifest = _make_systems_manifest()

        extractor = SystemsExtractor()
        result = extractor.extract(manifest, tmp_path / "output")

        assert "clocks" in result.extractions
        clocks = result.extractions["clocks"]
        assert len(clocks["clocks"]) > 0

    def test_extract_modifiers(self, tmp_path):
        manifest = _make_systems_manifest()

        extractor = SystemsExtractor()
        result = extractor.extract(manifest, tmp_path / "output")

        res = result.extractions.get("resolution", {})
        modifiers = res.get("modifiers", [])
        assert any("+2" in m.get("value", "") for m in modifiers)

    def test_extract_conditions(self, tmp_path):
        segments = [
            SegmentEntry(
                id="seg_cond",
                title="Conditions",
                content=(
                    "Exposed: enemies can see you and will attack.\n"
                    "Hidden: you are concealed from enemies.\n"
                    "Pursued: enemies are actively chasing you."
                ),
                source_section="Rules",
                page_start=1, page_end=1,
                word_count=50,
                content_type=ContentType.RULES,
                route=Route.SYSTEMS,
            ),
        ]
        manifest = SegmentManifest(segments=segments, total_words=50)

        extractor = SystemsExtractor()
        result = extractor.extract(manifest, tmp_path / "output")

        assert "conditions" in result.extractions
        conditions = result.extractions["conditions"]["conditions"]
        names = [c["name"] for c in conditions]
        assert "exposed" in names
        assert "hidden" in names

    def test_writes_output_files(self, tmp_path):
        manifest = _make_systems_manifest()

        extractor = SystemsExtractor()
        output_dir = tmp_path / "output"
        extractor.extract(manifest, output_dir)

        assert (output_dir / "extraction_manifest.json").exists()
        assert (output_dir / "stage_meta.json").exists()

    def test_empty_systems_manifest(self, tmp_path):
        manifest = SegmentManifest(segments=[], total_words=0)

        extractor = SystemsExtractor()
        result = extractor.extract(manifest, tmp_path / "output")

        assert len(result.extractions) == 0

    def test_source_segments_tracked(self, tmp_path):
        manifest = _make_systems_manifest()

        extractor = SystemsExtractor()
        result = extractor.extract(manifest, tmp_path / "output")

        assert "seg_rules" in result.source_segments
        assert "seg_clocks" in result.source_segments
