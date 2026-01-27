"""Tests for content chunker."""

import pytest
from pathlib import Path

from src.content.pack_loader import PackLoader, ContentFile
from src.content.chunker import Chunker, ContentChunk, estimate_tokens, _slugify, _split_by_headers


TEST_PACK_DIR = Path(__file__).parent.parent / "content_packs" / "test_pack"


class TestChunking:
    """Test markdown chunking into sections."""

    def test_chunk_location_file(self):
        loader = PackLoader()
        cf = loader.parse_content_file(
            TEST_PACK_DIR / "locations" / "neon_dragon.md",
            "location"
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "test_pack")

        # Should have overview (H1) + 3 H2 sections
        assert len(chunks) >= 3
        titles = [c.section_title for c in chunks]
        assert "Atmosphere" in titles
        assert "Regular Crowd" in titles
        assert "Back Room" in titles

    def test_chunk_npc_file(self):
        loader = PackLoader()
        cf = loader.parse_content_file(
            TEST_PACK_DIR / "npcs" / "viktor.md",
            "npc"
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "test_pack")

        assert len(chunks) >= 3
        titles = [c.section_title for c in chunks]
        assert "Background" in titles
        assert "Connections" in titles
        assert "Secrets" in titles

    def test_chunk_ids_namespaced(self):
        loader = PackLoader()
        cf = loader.parse_content_file(
            TEST_PACK_DIR / "locations" / "neon_dragon.md",
            "location"
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "test_pack")

        for chunk in chunks:
            assert chunk.id.startswith("test_pack:neon_dragon:")
            assert chunk.pack_id == "test_pack"

    def test_chunk_inherits_frontmatter(self):
        loader = PackLoader()
        cf = loader.parse_content_file(
            TEST_PACK_DIR / "npcs" / "viktor.md",
            "npc"
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "test_pack")

        for chunk in chunks:
            assert chunk.chunk_type == "npc"
            assert "npc" in chunk.tags
            assert "viktor" in chunk.entity_refs

    def test_chunk_entity_refs(self):
        loader = PackLoader()
        cf = loader.parse_content_file(
            TEST_PACK_DIR / "npcs" / "viktor.md",
            "npc"
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "test_pack")

        # Viktor's frontmatter has entity_refs to viktor, neon_dragon, zenith_industries
        for chunk in chunks:
            assert "viktor" in chunk.entity_refs

    def test_chunk_has_token_estimate(self):
        loader = PackLoader()
        cf = loader.parse_content_file(
            TEST_PACK_DIR / "locations" / "neon_dragon.md",
            "location"
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "test_pack")

        for chunk in chunks:
            assert chunk.token_estimate > 0

    def test_chunk_files_multiple(self):
        loader = PackLoader()
        _, files = loader.load_pack(TEST_PACK_DIR)
        chunker = Chunker()
        all_chunks = chunker.chunk_files(files, "test_pack")

        # At least 6 chunks (3 from each file, roughly)
        assert len(all_chunks) >= 6


class TestChunkingEdgeCases:
    """Test edge cases in chunking."""

    def test_no_headers(self):
        cf = ContentFile(
            path="test.md",
            file_type="general",
            title="Plain",
            body="Just some text without any headers at all."
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "pk")
        assert len(chunks) == 1
        assert chunks[0].section_title == "Plain"

    def test_h3_merges_into_h2(self):
        cf = ContentFile(
            path="test.md",
            file_type="location",
            title="Test",
            body="## Main Section\n\nIntro.\n\n### Subsection\n\nSub content.\n\n## Another\n\nMore."
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "pk")

        # H3 should merge into H2, so we get 2 chunks (not 3)
        assert len(chunks) == 2
        main_chunk = [c for c in chunks if c.section_title == "Main Section"][0]
        assert "Sub content" in main_chunk.content
        assert "### Subsection" in main_chunk.content

    def test_h1_overview_chunk(self):
        cf = ContentFile(
            path="test.md",
            file_type="location",
            title="My Place",
            body="# My Place\n\nOverview text here.\n\n## Details\n\nDetail text."
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "pk")

        assert len(chunks) == 2
        overview = chunks[0]
        assert overview.section_title == "My Place"
        assert "Overview text" in overview.content

    def test_empty_sections_skipped(self):
        cf = ContentFile(
            path="test.md",
            file_type="general",
            title="Test",
            body="## Empty Section\n\n## Real Section\n\nContent here."
        )
        chunker = Chunker()
        chunks = chunker.chunk_file(cf, "pk")

        # Empty section should be skipped
        titles = [c.section_title for c in chunks]
        assert "Real Section" in titles


class TestEstimateTokens:
    """Test token estimation."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        tokens = estimate_tokens("Hello world")
        assert tokens > 0
        assert tokens < 10

    def test_long_text(self):
        text = " ".join(["word"] * 100)
        tokens = estimate_tokens(text)
        assert 100 < tokens < 200


class TestSlugify:
    """Test slug generation."""

    def test_basic(self):
        assert _slugify("Hello World") == "hello_world"

    def test_special_chars(self):
        assert _slugify("The Neon Dragon!") == "the_neon_dragon"

    def test_dashes(self):
        assert _slugify("some-thing") == "some_thing"

    def test_empty(self):
        assert _slugify("") == "untitled"


class TestSplitByHeaders:
    """Test header-based splitting."""

    def test_no_headers(self):
        sections = _split_by_headers("Just text.")
        assert len(sections) == 1
        assert sections[0]["title"] == ""

    def test_single_h2(self):
        sections = _split_by_headers("## Section\n\nContent.")
        assert len(sections) == 1
        assert sections[0]["title"] == "Section"

    def test_multiple_h2(self):
        sections = _split_by_headers("## A\n\nFoo.\n\n## B\n\nBar.")
        assert len(sections) == 2
        assert sections[0]["title"] == "A"
        assert sections[1]["title"] == "B"

    def test_h1_then_h2(self):
        sections = _split_by_headers("# Overview\n\nIntro.\n\n## Detail\n\nStuff.")
        assert len(sections) == 2
        assert sections[0]["title"] == "Overview"
        assert sections[1]["title"] == "Detail"

    def test_h3_stays_in_parent(self):
        sections = _split_by_headers("## Parent\n\nText.\n\n### Child\n\nMore.")
        assert len(sections) == 1
        assert "### Child" in sections[0]["content"]
