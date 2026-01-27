"""Scene Lore Cache Manager - Materializes retrieved lore for scene injection.

Structures raw retrieved chunks into categorized lore sections:
  - atmosphere: Environmental/setting details
  - npc_briefings: NPC backstory and connection info
  - discoverable: Hidden or discoverable content
  - thread_connections: Lore relevant to active threads
"""

import logging
from typing import Optional

from ..db.state_store import StateStore, new_id
from .retriever import RetrievalResult

logger = logging.getLogger(__name__)

# Chunk types that map to each lore category
_TYPE_CATEGORY = {
    "location": "atmosphere",
    "culture": "atmosphere",
    "npc": "npc_briefings",
    "faction": "thread_connections",
    "item": "discoverable",
    "general": "atmosphere",
}


class SceneLoreCacheManager:
    """Manages materialized lore caches for scenes."""

    def __init__(self, state_store: StateStore):
        self.store = state_store

    def materialize(
        self,
        result: RetrievalResult,
        scene_id: str,
        session_id: Optional[str],
        campaign_id: str
    ) -> dict:
        """Structure retrieved chunks into categorized lore sections.

        Returns the lore dict and persists it to scene_lore table.
        """
        lore = {
            "atmosphere": [],
            "npc_briefings": {},
            "discoverable": [],
            "thread_connections": [],
        }

        chunk_ids = []
        for chunk in result.chunks:
            chunk_ids.append(chunk["id"])
            chunk_type = chunk.get("chunk_type", "general")
            category = _TYPE_CATEGORY.get(chunk_type, "atmosphere")

            entry = {
                "chunk_id": chunk["id"],
                "title": chunk.get("section_title", ""),
                "content": chunk.get("content", ""),
                "entity_refs": chunk.get("entity_refs", []),
            }

            if category == "npc_briefings":
                # Key by first entity ref (the NPC ID)
                refs = chunk.get("entity_refs", [])
                npc_id = refs[0] if refs else chunk.get("section_title", "unknown")
                if npc_id not in lore["npc_briefings"]:
                    lore["npc_briefings"][npc_id] = []
                lore["npc_briefings"][npc_id].append(entry)
            elif category == "thread_connections":
                lore["thread_connections"].append(entry)
            elif category == "discoverable":
                lore["discoverable"].append(entry)
            else:
                lore["atmosphere"].append(entry)

        # Persist to DB
        self.store.set_scene_lore(
            lore_id=new_id(),
            campaign_id=campaign_id,
            lore=lore,
            scene_id=scene_id,
            session_id=session_id,
            chunk_ids=chunk_ids
        )

        return lore

    def append_npc(
        self,
        scene_id: str,
        campaign_id: str,
        npc_lore: RetrievalResult
    ) -> dict | None:
        """Append NPC lore to an existing scene cache.

        Returns the updated lore dict, or None if no cache exists.
        """
        existing = self.store.get_scene_lore(campaign_id, scene_id)
        if not existing:
            return None

        lore = existing["lore"]
        chunk_ids = list(existing.get("chunk_ids", []))

        for chunk in npc_lore.chunks:
            chunk_ids.append(chunk["id"])
            refs = chunk.get("entity_refs", [])
            npc_id = refs[0] if refs else chunk.get("section_title", "unknown")

            entry = {
                "chunk_id": chunk["id"],
                "title": chunk.get("section_title", ""),
                "content": chunk.get("content", ""),
                "entity_refs": refs,
            }

            if npc_id not in lore.get("npc_briefings", {}):
                lore.setdefault("npc_briefings", {})[npc_id] = []
            lore["npc_briefings"][npc_id].append(entry)

        # Update in DB
        self.store.set_scene_lore(
            lore_id=existing["id"],
            campaign_id=campaign_id,
            lore=lore,
            scene_id=scene_id,
            session_id=existing.get("session_id"),
            chunk_ids=chunk_ids
        )

        return lore

    def get(self, campaign_id: str, scene_id: str) -> dict | None:
        """Get the cached lore for a scene.

        Returns the lore dict or None if not cached.
        """
        cached = self.store.get_scene_lore(campaign_id, scene_id)
        if not cached:
            return None
        return cached["lore"]

    def invalidate(self, scene_id: str, campaign_id: str) -> None:
        """Invalidate (delete) the lore cache for a scene."""
        with self.store.connect() as conn:
            conn.execute(
                "DELETE FROM scene_lore WHERE campaign_id = ? AND scene_id = ?",
                (campaign_id, scene_id)
            )
            conn.commit()
