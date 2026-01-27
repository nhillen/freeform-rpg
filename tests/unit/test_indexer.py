"""Tests for the lore indexer."""

import pytest
from pathlib import Path

from src.content.pack_loader import PackLoader
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.vector_store import NullVectorStore


TEST_PACK_DIR = Path(__file__).parent.parent / "content_packs" / "test_pack"


@pytest.fixture
def loader():
    return PackLoader()


@pytest.fixture
def chunker():
    return Chunker()


@pytest.fixture
def indexer(state_store):
    return LoreIndexer(state_store, NullVectorStore())


class TestIndexPack:
    """Test pack indexing pipeline."""

    def test_index_pack(self, indexer, loader, chunker, state_store):
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        chunks = chunker.chunk_files(files, manifest.id)
        stats = indexer.index_pack(manifest, chunks)

        assert stats.pack_id == "test_pack"
        assert stats.chunks_indexed >= 6
        assert stats.fts_indexed >= 6
        assert stats.vector_indexed == 0  # NullVectorStore

    def test_pack_registered_in_db(self, indexer, loader, chunker, state_store):
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        chunks = chunker.chunk_files(files, manifest.id)
        indexer.index_pack(manifest, chunks)

        pack = state_store.get_content_pack("test_pack")
        assert pack is not None
        assert pack["name"] == "Test Pack"
        assert pack["chunk_count"] >= 6

    def test_chunks_searchable_after_index(self, indexer, loader, chunker, state_store):
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        chunks = chunker.chunk_files(files, manifest.id)
        indexer.index_pack(manifest, chunks)

        # FTS5 search should find chunks
        results = state_store.search_chunks_fts("neon")
        assert len(results) >= 1

        results = state_store.search_chunks_fts("fixer")
        assert len(results) >= 1

    def test_chunks_stored_in_db(self, indexer, loader, chunker, state_store):
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        chunks = chunker.chunk_files(files, manifest.id)
        indexer.index_pack(manifest, chunks)

        stored = state_store.get_pack_chunks("test_pack")
        assert len(stored) >= 6
        # Verify structure
        for chunk in stored:
            assert chunk["pack_id"] == "test_pack"
            assert chunk["content"]
            assert chunk["section_title"]


class TestGetIndexStats:
    """Test index statistics retrieval."""

    def test_stats_after_index(self, indexer, loader, chunker, state_store):
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        chunks = chunker.chunk_files(files, manifest.id)
        indexer.index_pack(manifest, chunks)

        stats = indexer.get_index_stats("test_pack")
        assert stats is not None
        assert stats.chunks_indexed >= 6

    def test_stats_not_found(self, indexer):
        stats = indexer.get_index_stats("nonexistent")
        assert stats is None


class TestReindexPack:
    """Test pack re-indexing."""

    def test_reindex_clears_chunks(self, indexer, loader, chunker, state_store):
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        chunks = chunker.chunk_files(files, manifest.id)
        indexer.index_pack(manifest, chunks)

        # Verify chunks exist
        assert len(state_store.get_pack_chunks("test_pack")) >= 6

        # Reindex (just clears)
        result = indexer.reindex_pack("test_pack")
        assert result is not None
        assert result.chunks_indexed == 0

        # Chunks should be gone
        assert len(state_store.get_pack_chunks("test_pack")) == 0

    def test_reindex_not_found(self, indexer):
        result = indexer.reindex_pack("nonexistent")
        assert result is None
