"""Vector Store - Abstraction for vector similarity search.

Provides ChromaDB integration when available, with NullVectorStore fallback.
"""

import logging
from typing import Protocol, runtime_checkable

from .chunker import ContentChunk

logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector similarity search backends."""

    def add_chunks(self, chunks: list[ContentChunk], collection: str) -> int:
        """Add chunks to the vector store. Returns count added."""
        ...

    def query(
        self,
        text: str,
        collection: str,
        n_results: int = 10,
        where: dict | None = None
    ) -> list[dict]:
        """Query for similar chunks. Returns list of {id, distance, metadata}."""
        ...

    def delete_collection(self, collection: str) -> None:
        """Delete a collection and all its data."""
        ...


class NullVectorStore:
    """No-op vector store when ChromaDB is not available."""

    def add_chunks(self, chunks: list[ContentChunk], collection: str) -> int:
        return 0

    def query(
        self,
        text: str,
        collection: str,
        n_results: int = 10,
        where: dict | None = None
    ) -> list[dict]:
        return []

    def delete_collection(self, collection: str) -> None:
        pass


class ChromaVectorStore:
    """ChromaDB-backed vector store for semantic similarity search."""

    def __init__(self, persist_directory: str | None = None):
        import chromadb

        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()

    def add_chunks(self, chunks: list[ContentChunk], collection: str) -> int:
        if not chunks:
            return 0

        coll = self.client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"}
        )

        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "pack_id": c.pack_id,
                "chunk_type": c.chunk_type,
                "section_title": c.section_title,
                "file_path": c.file_path,
                "tags": ",".join(c.tags),
                "entity_refs": ",".join(c.entity_refs),
            }
            for c in chunks
        ]

        coll.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def query(
        self,
        text: str,
        collection: str,
        n_results: int = 10,
        where: dict | None = None
    ) -> list[dict]:
        try:
            coll = self.client.get_collection(collection)
        except Exception:
            return []

        query_args = {"query_texts": [text], "n_results": n_results}
        if where:
            query_args["where"] = where

        results = coll.query(**query_args)

        output = []
        if results and results.get("ids"):
            for i, chunk_id in enumerate(results["ids"][0]):
                entry = {
                    "id": chunk_id,
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                }
                output.append(entry)
        return output

    def delete_collection(self, collection: str) -> None:
        try:
            self.client.delete_collection(collection)
        except Exception:
            pass


def create_vector_store(persist_directory: str | None = None) -> VectorStore:
    """Factory: create ChromaVectorStore if available, else NullVectorStore."""
    try:
        store = ChromaVectorStore(persist_directory)
        logger.info("ChromaDB vector store initialized")
        return store
    except ImportError:
        logger.info("ChromaDB not installed; using FTS5-only retrieval")
        return NullVectorStore()
    except Exception as e:
        logger.warning("ChromaDB init failed (%s); using FTS5-only retrieval", e)
        return NullVectorStore()
