"""Lore Indexer - Indexes content pack chunks into FTS5 and optional vector store.

Orchestrates the full indexing pipeline:
  1. Register the pack in content_packs table
  2. Insert chunks into pack_chunks + FTS5
  3. Optionally embed chunks into vector store
"""

import logging
from dataclasses import dataclass

from ..db.state_store import StateStore
from .chunker import ContentChunk
from .pack_loader import PackManifest
from .vector_store import VectorStore, NullVectorStore

logger = logging.getLogger(__name__)


@dataclass
class IndexStats:
    """Statistics from an indexing operation."""
    pack_id: str
    chunks_indexed: int
    fts_indexed: int
    vector_indexed: int


class LoreIndexer:
    """Indexes content pack chunks into FTS5 and optional vector store."""

    def __init__(
        self,
        state_store: StateStore,
        vector_store: VectorStore | None = None
    ):
        self.store = state_store
        self.vector = vector_store or NullVectorStore()

    def index_pack(
        self,
        manifest: PackManifest,
        chunks: list[ContentChunk]
    ) -> IndexStats:
        """Index a content pack: register, insert chunks, build indices.

        This is idempotent: re-indexing a pack replaces its chunks.
        """
        pack_id = manifest.id

        # Register the pack
        self.store.create_content_pack(
            pack_id=pack_id,
            name=manifest.name,
            path="",  # Path is set by caller if needed
            description=manifest.description,
            version=manifest.version,
            layer=manifest.layer,
            chunk_count=len(chunks),
            metadata={
                "author": manifest.author,
                "tags": manifest.tags,
                **manifest.metadata
            }
        )

        # Insert chunks into SQLite + FTS5
        fts_count = 0
        for chunk in chunks:
            self.store.insert_pack_chunk(
                chunk_id=chunk.id,
                pack_id=chunk.pack_id,
                file_path=chunk.file_path,
                section_title=chunk.section_title,
                content=chunk.content,
                chunk_type=chunk.chunk_type,
                entity_refs=chunk.entity_refs,
                tags=chunk.tags,
                metadata=chunk.metadata,
                token_estimate=chunk.token_estimate
            )
            fts_count += 1

        # Index into vector store
        vector_count = self.vector.add_chunks(chunks, collection=pack_id)

        logger.info(
            "Indexed pack '%s': %d chunks (FTS5: %d, vector: %d)",
            pack_id, len(chunks), fts_count, vector_count
        )

        return IndexStats(
            pack_id=pack_id,
            chunks_indexed=len(chunks),
            fts_indexed=fts_count,
            vector_indexed=vector_count
        )

    def reindex_pack(self, pack_id: str) -> IndexStats | None:
        """Re-index an existing pack by clearing and re-inserting its chunks.

        Returns None if pack not found.
        """
        pack = self.store.get_content_pack(pack_id)
        if not pack:
            return None

        # Clear existing FTS entries for this pack
        with self.store.connect() as conn:
            # Get existing chunk IDs
            rows = conn.execute(
                "SELECT id FROM pack_chunks WHERE pack_id = ?",
                (pack_id,)
            ).fetchall()
            old_ids = [row["id"] for row in rows]

            # Delete from FTS5
            for cid in old_ids:
                conn.execute(
                    "DELETE FROM pack_chunks_fts WHERE chunk_id = ?",
                    (cid,)
                )

            # Delete from pack_chunks
            conn.execute(
                "DELETE FROM pack_chunks WHERE pack_id = ?",
                (pack_id,)
            )
            conn.commit()

        # Clear vector store collection
        self.vector.delete_collection(pack_id)

        # Note: actual re-indexing requires reloading from disk,
        # which the caller handles by calling index_pack() again
        return IndexStats(
            pack_id=pack_id,
            chunks_indexed=0,
            fts_indexed=0,
            vector_indexed=0
        )

    def get_index_stats(self, pack_id: str) -> IndexStats | None:
        """Get indexing statistics for a pack."""
        pack = self.store.get_content_pack(pack_id)
        if not pack:
            return None

        chunks = self.store.get_pack_chunks(pack_id)
        return IndexStats(
            pack_id=pack_id,
            chunks_indexed=len(chunks),
            fts_indexed=len(chunks),  # FTS5 mirrors pack_chunks
            vector_indexed=0  # Can't query vector store count easily
        )
