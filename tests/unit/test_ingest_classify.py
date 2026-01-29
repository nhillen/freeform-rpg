"""Tests for Stage 4: Content Classification."""

import pytest
from pathlib import Path

from src.ingest.models import ContentType, Route, SegmentEntry, SegmentManifest
from src.ingest.classify import ContentClassifier


def _make_segment(title, content, word_count=100):
    return SegmentEntry(
        id=f"seg_{title.lower().replace(' ', '_')}",
        title=title,
        content=content,
        source_section="Test",
        page_start=1,
        page_end=1,
        word_count=word_count,
    )


class TestContentClassifier:
    def test_location_classification(self, tmp_path):
        seg = _make_segment(
            "The Neon Dragon",
            "A seedy bar in the neon district. The building has three floors "
            "with a hidden entrance in the alley behind the club."
        )
        manifest = SegmentManifest(segments=[seg], total_words=100)

        classifier = ContentClassifier()
        classifier.classify(manifest, tmp_path / "output")

        assert seg.content_type == ContentType.LOCATION
        assert seg.route == Route.LORE

    def test_npc_classification(self, tmp_path):
        seg = _make_segment(
            "Viktor Kozlov",
            "A dangerous man with a scarred face. Age: 45. His personality "
            "is cold and calculating. Background: former military. "
            "Motivation: revenge against the corporation."
        )
        manifest = SegmentManifest(segments=[seg], total_words=100)

        classifier = ContentClassifier()
        classifier.classify(manifest, tmp_path / "output")

        assert seg.content_type == ContentType.NPC

    def test_rules_routed_to_systems(self, tmp_path):
        seg = _make_segment(
            "Resolution Mechanics",
            "Roll 2d6 + modifier. On 10+: critical success. "
            "On 7-9: mixed success. On 6-: failure. "
            "Threshold triggers at DC 10. Save DC 15."
        )
        manifest = SegmentManifest(segments=[seg], total_words=100)

        classifier = ContentClassifier()
        classifier.classify(manifest, tmp_path / "output")

        assert seg.route in (Route.SYSTEMS, Route.BOTH)

    def test_faction_classification(self, tmp_path):
        seg = _make_segment(
            "The Red Dragons",
            "A powerful faction that controls the territory of the lower "
            "district. Their organization has a strict hierarchy with "
            "leadership changing through challenge. They rival the "
            "Black Snakes corporation."
        )
        manifest = SegmentManifest(segments=[seg], total_words=100)

        classifier = ContentClassifier()
        classifier.classify(manifest, tmp_path / "output")

        assert seg.content_type == ContentType.FACTION

    def test_mixed_content_routes_both(self, tmp_path):
        seg = _make_segment(
            "Combat in the Undercity",
            "The streets of the district are dangerous. "
            "Roll 2d6 to resolve combat. On 10+: critical hit. "
            "The neon lights of the building flicker as gang members patrol. "
            "Escalation threshold at 5 triggers reinforcements."
        )
        manifest = SegmentManifest(segments=[seg], total_words=100)

        classifier = ContentClassifier()
        classifier.classify(manifest, tmp_path / "output")

        assert seg.route in (Route.BOTH, Route.SYSTEMS)

    def test_writes_manifest(self, tmp_path):
        seg = _make_segment("Test", "Some generic content here.")
        manifest = SegmentManifest(segments=[seg], total_words=50)

        classifier = ContentClassifier()
        output_dir = tmp_path / "output"
        classifier.classify(manifest, output_dir)

        assert (output_dir / "segment_manifest.json").exists()
        assert (output_dir / "stage_meta.json").exists()

    def test_culture_classification(self, tmp_path):
        seg = _make_segment(
            "Street Culture",
            "The slang of the neon district reflects a rich culture "
            "where fashion meets tradition. Social customs include "
            "ritual greetings and music that blends old and new."
        )
        manifest = SegmentManifest(segments=[seg], total_words=100)

        classifier = ContentClassifier()
        classifier.classify(manifest, tmp_path / "output")

        assert seg.content_type == ContentType.CULTURE
