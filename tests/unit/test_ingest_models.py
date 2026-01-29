"""Tests for ingest pipeline data models."""

import pytest
from src.ingest.models import (
    ContentType, EntityEntry, EntityRegistry, ExtractionResult,
    IngestConfig, PageEntry, Route, SectionNode, SegmentEntry,
    SegmentManifest, SystemsExtractionManifest,
)


class TestPageEntry:
    def test_defaults(self):
        p = PageEntry(page_num=1, text="Hello world")
        assert p.page_num == 1
        assert p.text == "Hello world"
        assert p.has_images is False
        assert p.image_paths == []
        assert p.ocr_used is False

    def test_char_count(self):
        p = PageEntry(page_num=1, text="test", char_count=4)
        assert p.char_count == 4


class TestExtractionResult:
    def test_defaults(self):
        r = ExtractionResult(pdf_path="/tmp/test.pdf", total_pages=10)
        assert r.pdf_path == "/tmp/test.pdf"
        assert r.total_pages == 10
        assert r.pages == []
        assert r.metadata == {}


class TestSectionNode:
    def test_creation(self):
        node = SectionNode(title="Chapter 1", level=1, page_start=1, page_end=10)
        assert node.title == "Chapter 1"
        assert node.level == 1
        assert node.children == []

    def test_children(self):
        child = SectionNode(title="Section 1.1", level=2, page_start=1, page_end=5)
        parent = SectionNode(
            title="Chapter 1", level=1, page_start=1, page_end=10,
            children=[child]
        )
        assert len(parent.children) == 1
        assert parent.children[0].title == "Section 1.1"


class TestContentType:
    def test_values(self):
        assert ContentType.LOCATION.value == "location"
        assert ContentType.NPC.value == "npc"
        assert ContentType.RULES.value == "rules"

    def test_from_string(self):
        assert ContentType("location") == ContentType.LOCATION


class TestRoute:
    def test_values(self):
        assert Route.LORE.value == "lore"
        assert Route.SYSTEMS.value == "systems"
        assert Route.BOTH.value == "both"


class TestSegmentEntry:
    def test_creation(self):
        s = SegmentEntry(
            id="seg_0001", title="The Neon Dragon",
            content="A seedy bar...", source_section="Locations",
            page_start=1, page_end=3, word_count=50,
        )
        assert s.id == "seg_0001"
        assert s.content_type is None
        assert s.route is None
        assert s.tags == []


class TestSegmentManifest:
    def test_empty(self):
        m = SegmentManifest()
        assert m.segments == []
        assert m.total_words == 0


class TestEntityRegistry:
    def test_add_and_get(self):
        reg = EntityRegistry()
        entity = EntityEntry(id="neon_dragon", name="The Neon Dragon", entity_type="location")
        reg.add(entity)

        assert reg.get("neon_dragon") is entity
        assert reg.get("nonexistent") is None

    def test_list_by_type(self):
        reg = EntityRegistry()
        reg.add(EntityEntry(id="bar", name="Bar", entity_type="location"))
        reg.add(EntityEntry(id="npc1", name="Viktor", entity_type="npc"))
        reg.add(EntityEntry(id="club", name="Club", entity_type="location"))

        locations = reg.list_by_type("location")
        assert len(locations) == 2

        npcs = reg.list_by_type("npc")
        assert len(npcs) == 1


class TestIngestConfig:
    def test_defaults(self):
        c = IngestConfig()
        assert c.use_ocr is False
        assert c.min_segment_words == 100
        assert c.max_segment_words == 1500

    def test_work_dir(self):
        c = IngestConfig(pdf_path="/tmp/sourcebook.pdf", output_dir="/tmp/out")
        wd = c.get_work_dir()
        assert "sourcebook" in str(wd)

    def test_explicit_work_dir(self):
        c = IngestConfig(work_dir="/tmp/my_work")
        assert str(c.get_work_dir()) == "/tmp/my_work"


class TestSystemsExtractionManifest:
    def test_defaults(self):
        m = SystemsExtractionManifest()
        assert m.extractions == {}
        assert m.source_segments == []
