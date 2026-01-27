"""Integration tests for retrieval quality.

Loads the test pack, indexes it, and verifies that known queries
return expected chunks.
"""

import pytest
from pathlib import Path

from src.content.pack_loader import PackLoader
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.retriever import LoreRetriever, LoreQuery
from src.content.scene_cache import SceneLoreCacheManager
from src.content.vector_store import NullVectorStore


TEST_PACK_DIR = Path(__file__).parent.parent / "content_packs" / "test_pack"


@pytest.fixture
def full_system(state_store):
    """Fully wired content system with test pack indexed."""
    loader = PackLoader()
    chunker = Chunker()
    indexer = LoreIndexer(state_store, NullVectorStore())

    manifest, files = loader.load_pack(TEST_PACK_DIR)
    chunks = chunker.chunk_files(files, manifest.id)
    indexer.index_pack(manifest, chunks)

    state_store.create_campaign("test", "Test Campaign")

    return {
        "store": state_store,
        "retriever": LoreRetriever(state_store, NullVectorStore()),
        "cache": SceneLoreCacheManager(state_store),
        "pack_id": manifest.id,
    }


class TestRetrievalQuality:
    """Verify that known queries surface expected content."""

    def test_neon_dragon_location(self, full_system):
        """Querying for neon_dragon should return location lore."""
        result = full_system["retriever"].retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test",
            pack_ids=[full_system["pack_id"]]
        )
        assert len(result.chunks) >= 1
        # Should include atmosphere content
        all_content = " ".join(c["content"] for c in result.chunks)
        assert "bar" in all_content.lower() or "neon" in all_content.lower()

    def test_viktor_entity(self, full_system):
        """Querying for Viktor should return NPC lore."""
        result = full_system["retriever"].retrieve_for_entity(
            "viktor", pack_ids=[full_system["pack_id"]]
        )
        assert len(result.chunks) >= 1
        all_content = " ".join(c["content"] for c in result.chunks)
        assert "fixer" in all_content.lower() or "viktor" in all_content.lower()

    def test_keyword_zenith(self, full_system):
        """Searching for 'zenith' should find Viktor's connections."""
        query = LoreQuery(
            keywords=["zenith"],
            pack_ids=[full_system["pack_id"]]
        )
        result = full_system["retriever"].query(query)
        assert len(result.chunks) >= 1
        all_content = " ".join(c["content"] for c in result.chunks)
        assert "zenith" in all_content.lower()

    def test_scene_with_npc_returns_both(self, full_system):
        """Scene at neon_dragon with Viktor should return both location and NPC lore."""
        result = full_system["retriever"].retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test",
            present_entities=[{"id": "viktor", "name": "Viktor"}],
            pack_ids=[full_system["pack_id"]]
        )
        chunk_types = {c["chunk_type"] for c in result.chunks}
        assert "location" in chunk_types
        assert "npc" in chunk_types

    def test_materialized_lore_structure(self, full_system):
        """Materialized lore should have proper structure."""
        result = full_system["retriever"].retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test",
            present_entities=[{"id": "viktor", "name": "Viktor"}],
            pack_ids=[full_system["pack_id"]]
        )
        lore = full_system["cache"].materialize(
            result, "neon_dragon", None, "test"
        )
        assert len(lore["atmosphere"]) > 0
        assert "viktor" in lore["npc_briefings"]

    def test_end_to_end_cache_flow(self, full_system):
        """Full flow: retrieve → materialize → get from cache."""
        retriever = full_system["retriever"]
        cache = full_system["cache"]

        # Retrieve
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test",
            pack_ids=[full_system["pack_id"]]
        )

        # Materialize
        cache.materialize(result, "neon_dragon", None, "test")

        # Fetch from cache
        cached = cache.get("test", "neon_dragon")
        assert cached is not None
        assert len(cached["atmosphere"]) > 0

        # Append NPC
        npc_result = retriever.retrieve_for_entity(
            "viktor", pack_ids=[full_system["pack_id"]]
        )
        updated = cache.append_npc("neon_dragon", "test", npc_result)
        assert updated is not None
        assert "viktor" in updated["npc_briefings"]
