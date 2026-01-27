"""Lore Retriever - Hybrid retrieval pipeline for content pack lore.

Three-stage retrieval:
  1. Metadata filter (pack_id, chunk_type)
  2. FTS5 keyword search + optional vector semantic search
  3. Token budget cap and deduplication
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..db.state_store import StateStore
from .vector_store import VectorStore, NullVectorStore

logger = logging.getLogger(__name__)


@dataclass
class LoreQuery:
    """Structured query for lore retrieval."""
    keywords: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    chunk_types: list[str] = field(default_factory=list)
    pack_ids: list[str] = field(default_factory=list)
    semantic_text: str = ""
    max_tokens: int = 2000
    max_chunks: int = 15


@dataclass
class RetrievalResult:
    """Result of a lore retrieval operation."""
    chunks: list[dict] = field(default_factory=list)
    total_tokens: int = 0
    query_used: Optional[LoreQuery] = None


class LoreRetriever:
    """Hybrid retrieval pipeline combining FTS5 and optional vector search.

    When an entity_manifest is provided (entity_id → [chunk_ids]), known
    entities are resolved by direct chunk lookup instead of FTS5 search.
    FTS5 remains the fallback for dynamic/unexpected queries.
    """

    def __init__(
        self,
        state_store: StateStore,
        vector_store: VectorStore | None = None,
        entity_manifest: dict[str, list[str]] | None = None
    ):
        self.store = state_store
        self.vector = vector_store or NullVectorStore()
        self.entity_manifest = entity_manifest or {}

    def build_query(
        self,
        scene: dict,
        entities: list[dict],
        threads: list[dict],
        player_input: str = "",
        pack_ids: list[str] | None = None
    ) -> LoreQuery:
        """Construct a structured query from game state signals.

        Extracts keywords and entity references from:
          - Current scene location
          - Present entities
          - Active threads
          - Player input text
        """
        keywords = []
        entity_ids = []

        # Scene location
        location_id = scene.get("location_id", "")
        if location_id and location_id != "unknown":
            keywords.append(location_id.replace("-", " ").replace("_", " "))
            entity_ids.append(location_id)

        # Present entities
        for entity in entities:
            entity_ids.append(entity.get("id", ""))
            name = entity.get("name", "")
            if name:
                keywords.append(name)

        # Active threads
        for thread in threads:
            title = thread.get("title", "")
            if title:
                keywords.append(title)
            for eid in thread.get("related_entity_ids", []):
                entity_ids.append(eid)

        # Player input keywords (simple extraction)
        if player_input:
            # Filter out common words
            stop_words = {
                "i", "the", "a", "an", "to", "at", "in", "on", "is", "it",
                "do", "go", "my", "me", "and", "or", "but", "not", "can",
                "with", "for", "of", "this", "that", "what", "want", "look",
            }
            words = player_input.lower().split()
            input_keywords = [w for w in words if w not in stop_words and len(w) > 2]
            keywords.extend(input_keywords[:5])

        # Build semantic text for vector search
        semantic_parts = []
        if location_id:
            semantic_parts.append(location_id.replace("_", " "))
        for e in entities[:3]:
            semantic_parts.append(e.get("name", ""))
        if player_input:
            semantic_parts.append(player_input)

        # Deduplicate
        keywords = list(dict.fromkeys(k for k in keywords if k))
        entity_ids = list(dict.fromkeys(e for e in entity_ids if e))

        return LoreQuery(
            keywords=keywords,
            entity_ids=entity_ids,
            chunk_types=[],  # No type restriction by default
            pack_ids=pack_ids or [],
            semantic_text=" ".join(semantic_parts),
            max_tokens=2000,
            max_chunks=15
        )

    def query(self, lore_query: LoreQuery) -> RetrievalResult:
        """Execute a lore query using the three-stage pipeline.

        Stage 1: Metadata filter (pack_id, chunk_type)
        Stage 2: FTS5 keyword + optional vector semantic search
        Stage 3: Token budget cap and deduplication
        """
        seen_ids = set()
        candidates = []

        # Stage 1: Manifest lookup (pre-computed entity → chunk_id mapping)
        if self.entity_manifest and lore_query.entity_ids:
            manifest_chunk_ids = []
            for eid in lore_query.entity_ids:
                manifest_chunk_ids.extend(self.entity_manifest.get(eid, []))
            if manifest_chunk_ids:
                # Deduplicate while preserving order
                unique_ids = list(dict.fromkeys(manifest_chunk_ids))
                manifest_chunks = self.store.get_chunks_by_ids(unique_ids)
                for chunk in manifest_chunks:
                    if chunk["id"] not in seen_ids:
                        seen_ids.add(chunk["id"])
                        candidates.append(chunk)

        # Stage 2a: FTS5 keyword search (across all declared packs)
        if lore_query.keywords:
            fts_query = " OR ".join(lore_query.keywords)
            chunk_type = lore_query.chunk_types[0] if lore_query.chunk_types else None
            search_packs = lore_query.pack_ids if lore_query.pack_ids else [None]

            for pid in search_packs:
                try:
                    fts_results = self.store.search_chunks_fts(
                        fts_query,
                        pack_id=pid,
                        chunk_type=chunk_type,
                        limit=lore_query.max_chunks * 2
                    )
                    for chunk in fts_results:
                        if chunk["id"] not in seen_ids:
                            seen_ids.add(chunk["id"])
                            candidates.append(chunk)
                except Exception as e:
                    logger.warning("FTS5 search failed for pack %s: %s", pid, e)

        # Stage 2b: Entity-ref matching (direct lookup)
        if lore_query.entity_ids:
            for pid in (lore_query.pack_ids or [None]):
                if pid:
                    all_chunks = self.store.get_pack_chunks(pid)
                else:
                    # If no pack specified, skip direct entity lookup
                    # (FTS should have found them)
                    break
                for chunk in all_chunks:
                    if chunk["id"] in seen_ids:
                        continue
                    chunk_refs = set(chunk.get("entity_refs", []))
                    if chunk_refs & set(lore_query.entity_ids):
                        seen_ids.add(chunk["id"])
                        candidates.append(chunk)

        # Stage 2c: Vector semantic search (if available)
        if lore_query.semantic_text and not isinstance(self.vector, NullVectorStore):
            for pid in (lore_query.pack_ids or ["default"]):
                vec_results = self.vector.query(
                    lore_query.semantic_text,
                    collection=pid,
                    n_results=lore_query.max_chunks
                )
                for vr in vec_results:
                    chunk_id = vr["id"]
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        # Fetch full chunk data from SQLite
                        with self.store.connect() as conn:
                            row = conn.execute(
                                "SELECT * FROM pack_chunks WHERE id = ?",
                                (chunk_id,)
                            ).fetchone()
                        if row:
                            from ..db.state_store import _parse_pack_chunk_row
                            candidates.append(_parse_pack_chunk_row(row))

        # Stage 3: Token budget cap
        selected = []
        total_tokens = 0
        for chunk in candidates[:lore_query.max_chunks]:
            chunk_tokens = chunk.get("token_estimate", 0)
            if total_tokens + chunk_tokens > lore_query.max_tokens and selected:
                break
            selected.append(chunk)
            total_tokens += chunk_tokens

        return RetrievalResult(
            chunks=selected,
            total_tokens=total_tokens,
            query_used=lore_query
        )

    def retrieve_for_scene(
        self,
        scene_state: dict,
        active_threads: list[dict],
        campaign_id: str,
        present_entities: list[dict] | None = None,
        pack_ids: list[str] | None = None
    ) -> RetrievalResult:
        """High-level scene-boundary retrieval.

        Called when the player enters a new scene to fetch relevant lore.
        """
        lore_query = self.build_query(
            scene=scene_state,
            entities=present_entities or [],
            threads=active_threads,
            pack_ids=pack_ids
        )
        return self.query(lore_query)

    def retrieve_for_entity(
        self,
        entity_id: str,
        pack_ids: list[str] | None = None
    ) -> RetrievalResult:
        """Retrieve lore for a specific entity (e.g., NPC introduction)."""
        query = LoreQuery(
            keywords=[entity_id.replace("_", " ").replace("-", " ")],
            entity_ids=[entity_id],
            pack_ids=pack_ids or [],
            max_tokens=800,
            max_chunks=5
        )
        return self.query(query)
