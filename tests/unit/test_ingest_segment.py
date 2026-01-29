"""Tests for Stage 3: Content Segmentation."""

import pytest
from pathlib import Path

from src.ingest.models import DocumentStructure, SectionNode, SegmentManifest
from src.ingest.segment import ContentSegmenter


def _make_structure(sections: list[dict]) -> DocumentStructure:
    """Helper to build a DocumentStructure."""
    nodes = []
    for s in sections:
        nodes.append(SectionNode(
            title=s["title"],
            level=1,
            page_start=s.get("page_start", 1),
            page_end=s.get("page_end", 1),
            content=s.get("content", ""),
        ))
    return DocumentStructure(title="Test Doc", sections=nodes)


class TestContentSegmenter:
    def test_single_section_fits(self, tmp_path):
        structure = _make_structure([{
            "title": "Small Section",
            "content": "This is a small section with just enough words. " * 20,
        }])

        segmenter = ContentSegmenter(min_words=10, max_words=2000)
        manifest = segmenter.segment(structure, tmp_path / "output")

        assert isinstance(manifest, SegmentManifest)
        assert len(manifest.segments) == 1
        assert manifest.segments[0].title == "Small Section"

    def test_header_splitting(self, tmp_path):
        content = (
            "## The Bar\n\nA dark and smoky bar. " * 10 +
            "\n\n## The Backroom\n\nA hidden room behind the bar. " * 10
        )
        structure = _make_structure([{
            "title": "The Neon Dragon",
            "content": content,
        }])

        segmenter = ContentSegmenter(min_words=10, max_words=2000)
        manifest = segmenter.segment(structure, tmp_path / "output")

        assert len(manifest.segments) >= 2
        titles = [s.title for s in manifest.segments]
        assert "The Bar" in titles
        assert "The Backroom" in titles

    def test_oversized_section_splits(self, tmp_path):
        # Create a section with 3000 words
        big_content = "word " * 3000
        structure = _make_structure([{
            "title": "Big Section",
            "content": big_content,
        }])

        segmenter = ContentSegmenter(min_words=100, max_words=1000)
        manifest = segmenter.segment(structure, tmp_path / "output")

        assert len(manifest.segments) >= 3
        for seg in manifest.segments:
            # Each should be under 1.5x max (with some tolerance for the enforce pass)
            assert seg.word_count <= 1500

    def test_undersized_merge(self, tmp_path):
        structure = _make_structure([
            {"title": "Tiny 1", "content": "A few words only."},
            {"title": "Tiny 2", "content": "Another few words."},
        ])

        segmenter = ContentSegmenter(min_words=50, max_words=2000)
        manifest = segmenter.segment(structure, tmp_path / "output")

        # Should merge the tiny segments
        assert manifest.total_words > 0

    def test_writes_output(self, tmp_path):
        structure = _make_structure([{
            "title": "Test",
            "content": "Content here. " * 30,
        }])

        segmenter = ContentSegmenter(min_words=10, max_words=2000)
        output_dir = tmp_path / "output"
        segmenter.segment(structure, output_dir)

        assert (output_dir / "segment_manifest.json").exists()
        assert (output_dir / "segments").is_dir()
        assert (output_dir / "stage_meta.json").exists()

    def test_empty_structure(self, tmp_path):
        structure = DocumentStructure(title="Empty", sections=[])
        segmenter = ContentSegmenter()
        manifest = segmenter.segment(structure, tmp_path / "output")
        assert len(manifest.segments) == 0


class TestMetaContentFilter:
    """Tests for secondary META content filtering in segments."""

    def _make_segment(self, content, title="Test", word_count=None):
        from src.ingest.models import SegmentEntry
        wc = word_count if word_count is not None else len(content.split())
        return SegmentEntry(
            id="seg_0000", title=title, content=content,
            source_section="Test", page_start=1, page_end=1,
            word_count=wc,
        )

    def test_isbn_and_rights_filtered(self):
        seg = self._make_segment(
            "ISBN 978-1-56504-403-9. All rights reserved. No part may be reproduced.",
            word_count=15,
        )
        segmenter = ContentSegmenter()
        assert segmenter._is_meta_content(seg) is True

    def test_portuguese_disclaimer_filtered(self):
        seg = self._make_segment(
            "Todos os direitos reservados. Proibido reprodução.",
            word_count=8,
        )
        segmenter = ContentSegmenter()
        assert segmenter._is_meta_content(seg) is True

    def test_short_allcaps_filtered(self):
        seg = self._make_segment("PAGE HEADER TEXT", word_count=3)
        segmenter = ContentSegmenter()
        assert segmenter._is_meta_content(seg) is True

    def test_real_content_not_filtered(self):
        seg = self._make_segment(
            "The Akashic Brotherhood is a Tradition of martial artists and scholars. "
            "They believe in the interconnectedness of all things through the Akashic Record, "
            "a vast repository of all human knowledge and experience. " * 5,
        )
        segmenter = ContentSegmenter()
        assert segmenter._is_meta_content(seg) is False

    def test_single_meta_pattern_long_content_not_filtered(self):
        # A single ISBN mention in a long paragraph shouldn't filter it
        seg = self._make_segment(
            "This edition (ISBN 978-1-56504-403-9) was printed in limited quantities. " * 10,
        )
        segmenter = ContentSegmenter()
        assert segmenter._is_meta_content(seg) is False

    def test_ogl_content_filtered(self):
        seg = self._make_segment(
            "Open Game License Version 1.0a. All rights reserved.",
            word_count=10,
        )
        segmenter = ContentSegmenter()
        assert segmenter._is_meta_content(seg) is True
