"""Tests for vector store abstraction."""

import pytest

from src.content.vector_store import (
    NullVectorStore,
    VectorStore,
    create_vector_store,
)
from src.content.chunker import ContentChunk


def _make_chunk(id: str, content: str, **kwargs) -> ContentChunk:
    return ContentChunk(
        id=id,
        pack_id=kwargs.get("pack_id", "test"),
        file_path=kwargs.get("file_path", "test.md"),
        section_title=kwargs.get("section_title", "Test"),
        content=content,
        chunk_type=kwargs.get("chunk_type", "general"),
        entity_refs=kwargs.get("entity_refs", []),
        tags=kwargs.get("tags", []),
        metadata=kwargs.get("metadata", {}),
        token_estimate=kwargs.get("token_estimate", 10),
    )


class TestNullVectorStore:
    """Test the no-op fallback vector store."""

    def test_implements_protocol(self):
        store = NullVectorStore()
        assert isinstance(store, VectorStore)

    def test_add_chunks_returns_zero(self):
        store = NullVectorStore()
        chunks = [_make_chunk("c1", "Hello world")]
        assert store.add_chunks(chunks, "test") == 0

    def test_query_returns_empty(self):
        store = NullVectorStore()
        assert store.query("test", "test") == []

    def test_delete_collection_no_error(self):
        store = NullVectorStore()
        store.delete_collection("test")  # Should not raise


class TestCreateVectorStore:
    """Test the factory function."""

    def test_factory_returns_vector_store(self):
        store = create_vector_store()
        assert isinstance(store, VectorStore)

    def test_factory_returns_something_usable(self):
        store = create_vector_store()
        # Should work regardless of whether ChromaDB is installed
        result = store.query("test", "nonexistent")
        assert isinstance(result, list)


class TestChromaVectorStore:
    """Test ChromaDB vector store (only runs if chromadb is installed)."""

    @pytest.fixture
    def chroma_store(self):
        try:
            from src.content.vector_store import ChromaVectorStore
            return ChromaVectorStore()  # In-memory
        except ImportError:
            pytest.skip("chromadb not installed")

    def test_add_and_query(self, chroma_store):
        chunks = [
            _make_chunk("c1", "A cyberpunk bar with neon lights", chunk_type="location"),
            _make_chunk("c2", "Viktor is a grizzled fixer", chunk_type="npc"),
        ]
        count = chroma_store.add_chunks(chunks, "test_coll")
        assert count == 2

        results = chroma_store.query("neon bar", "test_coll", n_results=1)
        assert len(results) >= 1
        assert results[0]["id"] == "c1"

    def test_query_nonexistent_collection(self, chroma_store):
        results = chroma_store.query("test", "no_such_collection")
        assert results == []

    def test_delete_collection(self, chroma_store):
        chunks = [_make_chunk("c1", "test content")]
        chroma_store.add_chunks(chunks, "to_delete")
        chroma_store.delete_collection("to_delete")
        results = chroma_store.query("test", "to_delete")
        assert results == []
