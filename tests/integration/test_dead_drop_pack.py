"""
Integration tests for the Undercity Sourcebook content pack.

Loads the pack, indexes it, and verifies retrieval quality:
  1. Scene at neon_dragon + Viktor → returns atmosphere + Viktor briefing
  2. Scene at alley → returns crime scene content
  3. Keyword "Zenith" → returns faction info
  4. NPC introduction for agent_chen → returns Chen briefing
  5. Thread main_case → returns thread-connected lore
"""

import pytest
from pathlib import Path

from src.db.state_store import StateStore
from src.content.pack_loader import PackLoader
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.retriever import LoreRetriever, LoreQuery
from src.content.scene_cache import SceneLoreCacheManager


UNDERCITY_PATH = Path(__file__).parent.parent.parent / "content_packs" / "undercity_sourcebook"


@pytest.fixture
def indexed_store(state_store):
    """State store with the Undercity Sourcebook pack loaded and indexed."""
    loader = PackLoader()
    manifest, files = loader.load_pack(UNDERCITY_PATH)

    chunker = Chunker()
    chunks = chunker.chunk_files(files, manifest.id)

    indexer = LoreIndexer(state_store)
    stats = indexer.index_pack(manifest, chunks)

    assert stats.chunks_indexed > 0
    return state_store, manifest, stats


@pytest.fixture
def retriever(indexed_store):
    """LoreRetriever backed by the indexed store."""
    store, manifest, _stats = indexed_store
    return LoreRetriever(store)


@pytest.fixture
def cache(indexed_store):
    """SceneLoreCacheManager backed by the indexed store."""
    store, _manifest, _stats = indexed_store
    return SceneLoreCacheManager(store)


class TestPackLoadAndIndex:
    """Tests for loading and indexing the Undercity Sourcebook pack."""

    def test_pack_loads_successfully(self):
        """Undercity Sourcebook pack loads without errors."""
        loader = PackLoader()
        manifest, files = loader.load_pack(UNDERCITY_PATH)

        assert manifest.id == "undercity_sourcebook"
        assert manifest.name == "Undercity Sourcebook"
        assert manifest.layer == "setting"
        assert len(files) == 8  # 3 locations + 3 npcs + 1 faction + 1 culture

    def test_pack_validates_clean(self):
        """Undercity Sourcebook pack passes validation."""
        loader = PackLoader()
        result = loader.validate_pack(UNDERCITY_PATH)

        assert result.valid
        assert len(result.errors) == 0

    def test_chunking_produces_expected_count(self):
        """Chunking produces a reasonable number of chunks."""
        loader = PackLoader()
        manifest, files = loader.load_pack(UNDERCITY_PATH)

        chunker = Chunker()
        chunks = chunker.chunk_files(files, manifest.id)

        # Each file has H1 + 2-3 H2 sections, so ~3-4 chunks per file × 8 files
        assert len(chunks) >= 20
        assert len(chunks) <= 60

    def test_index_stats(self, indexed_store):
        """Index stats reflect the indexed chunks."""
        store, manifest, stats = indexed_store

        assert stats.pack_id == "undercity_sourcebook"
        assert stats.chunks_indexed >= 20
        assert stats.fts_indexed == stats.chunks_indexed


class TestSceneRetrieval:
    """Tests for scene-boundary lore retrieval."""

    def test_neon_dragon_scene_returns_atmosphere(self, retriever):
        """Scene at neon_dragon returns atmosphere chunks."""
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test",
            present_entities=[
                {"id": "player", "name": "Kira"},
                {"id": "viktor", "name": "Viktor"},
            ],
            pack_ids=["undercity_sourcebook"],
        )

        assert len(result.chunks) > 0

        # Should find neon_dragon location content
        chunk_texts = " ".join(c["content"] for c in result.chunks)
        assert "neon" in chunk_texts.lower() or "dragon" in chunk_texts.lower()

    def test_neon_dragon_with_viktor_returns_npc_lore(self, retriever, cache):
        """Scene at neon_dragon with Viktor returns both atmosphere and NPC briefings."""
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test_camp",
            present_entities=[
                {"id": "player", "name": "Kira"},
                {"id": "viktor", "name": "Viktor"},
            ],
            pack_ids=["undercity_sourcebook"],
        )

        assert len(result.chunks) > 0

        # Entity refs across all returned chunks
        all_entity_refs = set()
        for chunk in result.chunks:
            all_entity_refs.update(chunk.get("entity_refs", []))

        # Should reference Viktor and/or neon_dragon
        assert "viktor" in all_entity_refs or "neon_dragon" in all_entity_refs

    def test_alley_scene_returns_crime_scene_content(self, retriever):
        """Scene at alley_behind_dragon returns crime scene details."""
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "alley_behind_dragon"},
            active_threads=[],
            campaign_id="test",
            present_entities=[{"id": "player", "name": "Kira"}],
            pack_ids=["undercity_sourcebook"],
        )

        assert len(result.chunks) > 0

        chunk_texts = " ".join(c["content"] for c in result.chunks).lower()
        # Should contain crime scene / alley content
        assert "alley" in chunk_texts or "body" in chunk_texts or "crime" in chunk_texts


class TestKeywordRetrieval:
    """Tests for keyword-based lore retrieval."""

    def test_zenith_keyword_returns_faction(self, retriever):
        """Searching for 'Zenith' returns Zenith Industries faction info."""
        query = LoreQuery(
            keywords=["Zenith"],
            pack_ids=["undercity_sourcebook"],
            max_tokens=3000,
        )
        result = retriever.query(query)

        assert len(result.chunks) > 0

        chunk_texts = " ".join(c["content"] for c in result.chunks).lower()
        assert "zenith" in chunk_texts

    def test_datahaven_keyword_returns_location(self, retriever):
        """Searching for 'DataHaven' returns the cafe location."""
        query = LoreQuery(
            keywords=["DataHaven"],
            pack_ids=["undercity_sourcebook"],
            max_tokens=3000,
        )
        result = retriever.query(query)

        assert len(result.chunks) > 0

        all_entity_refs = set()
        for chunk in result.chunks:
            all_entity_refs.update(chunk.get("entity_refs", []))
        assert "datahaven" in all_entity_refs or "mira" in all_entity_refs


class TestNPCRetrieval:
    """Tests for entity-level NPC lore retrieval."""

    def test_agent_chen_retrieval(self, retriever):
        """Retrieving lore for corpo_agent returns Agent Chen briefing."""
        result = retriever.retrieve_for_entity(
            "corpo_agent", pack_ids=["undercity_sourcebook"]
        )

        assert len(result.chunks) > 0

        all_entity_refs = set()
        for chunk in result.chunks:
            all_entity_refs.update(chunk.get("entity_refs", []))

        assert "corpo_agent" in all_entity_refs

    def test_viktor_retrieval(self, retriever):
        """Retrieving lore for viktor returns Viktor briefing."""
        result = retriever.retrieve_for_entity(
            "viktor", pack_ids=["undercity_sourcebook"]
        )

        assert len(result.chunks) > 0

        chunk_texts = " ".join(c["content"] for c in result.chunks).lower()
        assert "viktor" in chunk_texts or "fixer" in chunk_texts

    def test_mira_retrieval(self, retriever):
        """Retrieving lore for mira returns Mira's profile."""
        result = retriever.retrieve_for_entity(
            "mira", pack_ids=["undercity_sourcebook"]
        )

        assert len(result.chunks) > 0


class TestThreadConnectedLore:
    """Tests for thread-connected lore retrieval."""

    def test_main_thread_returns_connected_lore(self, retriever):
        """Scene retrieval with active main thread returns relevant lore."""
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[
                {
                    "id": "main_thread",
                    "title": "Find out what happened to Jin and the package",
                    "status": "active",
                    "related_entity_ids": ["dead_courier", "package", "viktor"],
                }
            ],
            campaign_id="test",
            present_entities=[
                {"id": "player", "name": "Kira"},
                {"id": "viktor", "name": "Viktor"},
            ],
            pack_ids=["undercity_sourcebook"],
        )

        assert len(result.chunks) > 0

        # The thread keywords (Jin, package) and entity refs (viktor)
        # should pull in relevant lore
        chunk_texts = " ".join(c["content"] for c in result.chunks).lower()
        # Should contain references to the investigation
        assert any(
            term in chunk_texts
            for term in ["jin", "package", "courier", "viktor", "fixer"]
        )


class TestSceneCacheMaterialization:
    """Tests for materializing retrieved lore into scene cache."""

    def test_materialize_categorizes_chunks(self, retriever, cache, indexed_store):
        """Materialized lore is categorized into atmosphere/npc_briefings/etc."""
        store, manifest, _stats = indexed_store

        # Create a campaign for caching
        store.create_campaign("lore_test", "Lore Test")

        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="lore_test",
            present_entities=[
                {"id": "player", "name": "Kira"},
                {"id": "viktor", "name": "Viktor"},
            ],
            pack_ids=["undercity_sourcebook"],
        )

        lore = cache.materialize(result, "neon_dragon", None, "lore_test")

        assert "atmosphere" in lore
        assert "npc_briefings" in lore
        assert "discoverable" in lore
        assert "thread_connections" in lore

        # Should have at least some atmosphere (location chunks)
        assert len(lore["atmosphere"]) > 0

    def test_cached_lore_retrievable(self, retriever, cache, indexed_store):
        """Materialized lore can be retrieved from cache."""
        store, _manifest, _stats = indexed_store
        store.create_campaign("cache_test", "Cache Test")

        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="cache_test",
            present_entities=[{"id": "player", "name": "Kira"}],
            pack_ids=["undercity_sourcebook"],
        )

        cache.materialize(result, "neon_dragon", None, "cache_test")

        cached = cache.get("cache_test", "neon_dragon")
        assert cached is not None
        assert "atmosphere" in cached


class TestLoreManifest:
    """Tests for the entity lore manifest built at scenario load."""

    def test_manifest_maps_entities_to_chunks(self, indexed_store):
        """Scenario loader builds manifest from installed pack."""
        from src.setup.scenario_loader import ScenarioLoader

        store, _manifest, _stats = indexed_store

        loader = ScenarioLoader(store)
        result = loader.load_scenario("dead_drop", campaign_id="manifest_test")

        assert result["pack_ids"] == ["undercity_sourcebook"]
        assert result["manifest_entries"] > 0

        # Verify manifest stored on campaign
        campaign = store.get_campaign("manifest_test")
        manifest = campaign["lore_manifest"]

        # Viktor should be in the manifest (has entity_refs in pack chunks)
        assert "viktor" in manifest
        assert len(manifest["viktor"]) > 0

        # neon_dragon should be in the manifest
        assert "neon_dragon" in manifest
        assert len(manifest["neon_dragon"]) > 0

    def test_manifest_retriever_uses_direct_lookup(self, indexed_store):
        """Retriever with manifest finds chunks by direct ID lookup."""
        store, _manifest, _stats = indexed_store

        # Build a manifest manually for a known entity
        all_chunks = store.get_pack_chunks("undercity_sourcebook")
        viktor_chunks = [
            c["id"] for c in all_chunks
            if "viktor" in c.get("entity_refs", [])
        ]

        manifest = {"viktor": viktor_chunks}
        retriever = LoreRetriever(store, entity_manifest=manifest)

        # Retrieve for Viktor — should use manifest
        result = retriever.retrieve_for_entity(
            "viktor", pack_ids=["undercity_sourcebook"]
        )

        assert len(result.chunks) > 0
        # Manifest chunks should appear in results (token budget may cap total)
        returned_ids = {c["id"] for c in result.chunks}
        manifest_hits = returned_ids & set(viktor_chunks)
        assert len(manifest_hits) > 0, "Expected manifest chunks in results"

    def test_campaign_stores_pack_ids(self, indexed_store):
        """Campaign record stores declared pack_ids."""
        from src.setup.scenario_loader import ScenarioLoader

        store, _manifest, _stats = indexed_store

        loader = ScenarioLoader(store)
        loader.load_scenario("dead_drop", campaign_id="pack_test")

        campaign = store.get_campaign("pack_test")
        assert campaign["pack_ids"] == ["undercity_sourcebook"]
