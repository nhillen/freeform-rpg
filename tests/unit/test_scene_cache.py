"""Tests for the scene lore cache manager."""

import pytest
from pathlib import Path

from src.content.pack_loader import PackLoader
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.retriever import LoreRetriever, RetrievalResult
from src.content.scene_cache import SceneLoreCacheManager
from src.content.vector_store import NullVectorStore


TEST_PACK_DIR = Path(__file__).parent.parent / "content_packs" / "test_pack"


@pytest.fixture
def indexed_store(state_store):
    """State store with test pack loaded and indexed."""
    loader = PackLoader()
    chunker = Chunker()
    indexer = LoreIndexer(state_store, NullVectorStore())
    manifest, files = loader.load_pack(TEST_PACK_DIR)
    chunks = chunker.chunk_files(files, manifest.id)
    indexer.index_pack(manifest, chunks)
    state_store.create_campaign("test_campaign", "Test")
    return state_store


@pytest.fixture
def retriever(indexed_store):
    return LoreRetriever(indexed_store, NullVectorStore())


@pytest.fixture
def cache_manager(indexed_store):
    return SceneLoreCacheManager(indexed_store)


class TestMaterialize:
    """Test lore materialization."""

    def test_materialize_creates_cache(self, retriever, cache_manager):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_campaign",
            pack_ids=["test_pack"]
        )
        lore = cache_manager.materialize(
            result, "neon_dragon", None, "test_campaign"
        )
        assert "atmosphere" in lore
        assert "npc_briefings" in lore
        assert "discoverable" in lore
        assert "thread_connections" in lore

    def test_location_chunks_in_atmosphere(self, retriever, cache_manager):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_campaign",
            pack_ids=["test_pack"]
        )
        lore = cache_manager.materialize(
            result, "neon_dragon", None, "test_campaign"
        )
        # Location chunks should be in atmosphere
        assert len(lore["atmosphere"]) > 0

    def test_npc_chunks_in_briefings(self, retriever, cache_manager):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_campaign",
            present_entities=[{"id": "viktor", "name": "Viktor"}],
            pack_ids=["test_pack"]
        )
        lore = cache_manager.materialize(
            result, "neon_dragon", None, "test_campaign"
        )
        # Viktor's chunks should appear in npc_briefings
        assert "viktor" in lore["npc_briefings"]

    def test_persists_to_db(self, retriever, cache_manager, indexed_store):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_campaign",
            pack_ids=["test_pack"]
        )
        cache_manager.materialize(result, "neon_dragon", None, "test_campaign")

        # Should be retrievable from DB
        cached = indexed_store.get_scene_lore("test_campaign", "neon_dragon")
        assert cached is not None
        assert "atmosphere" in cached["lore"]


class TestAppendNpc:
    """Test appending NPC lore to existing cache."""

    def test_append_npc_to_cache(self, retriever, cache_manager):
        # First materialize scene
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_campaign",
            pack_ids=["test_pack"]
        )
        cache_manager.materialize(result, "neon_dragon", None, "test_campaign")

        # Then append NPC lore
        npc_result = retriever.retrieve_for_entity("viktor", pack_ids=["test_pack"])
        lore = cache_manager.append_npc("neon_dragon", "test_campaign", npc_result)

        assert lore is not None
        assert "viktor" in lore.get("npc_briefings", {})

    def test_append_npc_no_cache(self, retriever, cache_manager):
        npc_result = retriever.retrieve_for_entity("viktor", pack_ids=["test_pack"])
        lore = cache_manager.append_npc("nonexistent", "test_campaign", npc_result)
        assert lore is None


class TestGetAndInvalidate:
    """Test cache retrieval and invalidation."""

    def test_get_cached_lore(self, retriever, cache_manager):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_campaign",
            pack_ids=["test_pack"]
        )
        cache_manager.materialize(result, "neon_dragon", None, "test_campaign")

        lore = cache_manager.get("test_campaign", "neon_dragon")
        assert lore is not None
        assert "atmosphere" in lore

    def test_get_uncached_returns_none(self, cache_manager):
        assert cache_manager.get("test_campaign", "nonexistent") is None

    def test_invalidate(self, retriever, cache_manager):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_campaign",
            pack_ids=["test_pack"]
        )
        cache_manager.materialize(result, "neon_dragon", None, "test_campaign")

        cache_manager.invalidate("neon_dragon", "test_campaign")
        assert cache_manager.get("test_campaign", "neon_dragon") is None
