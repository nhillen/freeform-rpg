"""Tests for the lore retriever."""

import pytest
from pathlib import Path

from src.content.pack_loader import PackLoader
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.retriever import LoreRetriever, LoreQuery
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
    return state_store


@pytest.fixture
def retriever(indexed_store):
    return LoreRetriever(indexed_store, NullVectorStore())


class TestBuildQuery:
    """Test query construction from game state."""

    def test_builds_from_scene(self, retriever):
        query = retriever.build_query(
            scene={"location_id": "neon_dragon"},
            entities=[],
            threads=[]
        )
        assert "neon dragon" in query.keywords
        assert "neon_dragon" in query.entity_ids

    def test_includes_entities(self, retriever):
        query = retriever.build_query(
            scene={"location_id": "bar"},
            entities=[{"id": "viktor", "name": "Viktor Volkov"}],
            threads=[]
        )
        assert "Viktor Volkov" in query.keywords
        assert "viktor" in query.entity_ids

    def test_includes_threads(self, retriever):
        query = retriever.build_query(
            scene={"location_id": "bar"},
            entities=[],
            threads=[{"id": "main_case", "title": "The Dead Drop", "related_entity_ids": ["jin"]}]
        )
        assert "The Dead Drop" in query.keywords
        assert "jin" in query.entity_ids

    def test_includes_player_input(self, retriever):
        query = retriever.build_query(
            scene={"location_id": "bar"},
            entities=[],
            threads=[],
            player_input="ask about zenith industries"
        )
        assert "zenith" in query.keywords or "industries" in query.keywords

    def test_pack_ids_passed_through(self, retriever):
        query = retriever.build_query(
            scene={"location_id": "bar"},
            entities=[],
            threads=[],
            pack_ids=["dead_drop_lore"]
        )
        assert "dead_drop_lore" in query.pack_ids


class TestQueryExecution:
    """Test the query execution pipeline."""

    def test_keyword_search(self, retriever):
        query = LoreQuery(
            keywords=["neon", "dragon"],
            pack_ids=["test_pack"]
        )
        result = retriever.query(query)
        assert len(result.chunks) > 0
        assert result.total_tokens > 0

    def test_entity_ref_search(self, retriever):
        query = LoreQuery(
            keywords=[],
            entity_ids=["viktor"],
            pack_ids=["test_pack"]
        )
        result = retriever.query(query)
        assert len(result.chunks) > 0
        # Should find Viktor's chunks
        all_refs = []
        for c in result.chunks:
            all_refs.extend(c.get("entity_refs", []))
        assert "viktor" in all_refs

    def test_token_budget_cap(self, retriever):
        query = LoreQuery(
            keywords=["neon", "dragon", "bar", "fixer", "undercity"],
            pack_ids=["test_pack"],
            max_tokens=50  # Very small budget
        )
        result = retriever.query(query)
        # Should have limited results due to token budget
        assert result.total_tokens <= 100  # Some slack for chunk granularity

    def test_empty_query(self, retriever):
        query = LoreQuery()
        result = retriever.query(query)
        assert len(result.chunks) == 0


class TestRetrieveForScene:
    """Test scene-level retrieval."""

    def test_retrieve_for_neon_dragon(self, retriever):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test",
            pack_ids=["test_pack"]
        )
        assert len(result.chunks) > 0

    def test_retrieve_with_entities(self, retriever):
        result = retriever.retrieve_for_scene(
            scene_state={"location_id": "neon_dragon"},
            active_threads=[],
            campaign_id="test",
            present_entities=[{"id": "viktor", "name": "Viktor"}],
            pack_ids=["test_pack"]
        )
        assert len(result.chunks) > 0


class TestRetrieveForEntity:
    """Test entity-specific retrieval."""

    def test_retrieve_for_viktor(self, retriever):
        result = retriever.retrieve_for_entity("viktor", pack_ids=["test_pack"])
        assert len(result.chunks) > 0
        # Should find Viktor-related chunks
        all_refs = []
        for c in result.chunks:
            all_refs.extend(c.get("entity_refs", []))
        assert "viktor" in all_refs

    def test_retrieve_for_unknown_entity(self, retriever):
        result = retriever.retrieve_for_entity("nobody_here", pack_ids=["test_pack"])
        # Might return 0 or some fuzzy matches
        assert isinstance(result.chunks, list)
