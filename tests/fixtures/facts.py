"""
Factory functions for creating test facts.
"""

from typing import Any, Optional
import uuid


def make_fact(
    subject_id: str,
    predicate: str,
    obj: Any,
    visibility: str = "world",
    confidence: float = 1.0,
    tags: Optional[list] = None,
    fact_id: Optional[str] = None,
    discovered_turn: Optional[int] = None,
    discovery_method: Optional[str] = None
) -> dict:
    """
    Create a fact dict.

    Args:
        subject_id: Entity the fact is about
        predicate: What kind of fact (e.g., "status", "location", "knows")
        obj: The fact's value (can be any JSON-serializable type)
        visibility: "known" (player knows) or "world" (hidden)
        confidence: How certain (0-1)
        tags: Additional tags
        fact_id: Optional ID (auto-generated if not provided)
        discovered_turn: Turn when discovered (if known)
        discovery_method: How discovered (if known)

    Returns:
        Fact dict ready for database insertion
    """
    return {
        "id": fact_id or f"fact_{uuid.uuid4().hex[:8]}",
        "subject_id": subject_id,
        "predicate": predicate,
        "object": obj,
        "visibility": visibility,
        "confidence": confidence,
        "tags": tags or [],
        "discovered_turn": discovered_turn,
        "discovery_method": discovery_method
    }


def make_known_fact(
    subject_id: str,
    predicate: str,
    obj: Any,
    discovered_turn: int = 0,
    discovery_method: str = "initial",
    **kwargs
) -> dict:
    """
    Create a fact the player already knows.

    Shorthand for make_fact with visibility="known".
    """
    return make_fact(
        subject_id=subject_id,
        predicate=predicate,
        obj=obj,
        visibility="known",
        discovered_turn=discovered_turn,
        discovery_method=discovery_method,
        **kwargs
    )


def make_world_fact(
    subject_id: str,
    predicate: str,
    obj: Any,
    **kwargs
) -> dict:
    """
    Create a fact the player doesn't know yet.

    Shorthand for make_fact with visibility="world".
    """
    return make_fact(
        subject_id=subject_id,
        predicate=predicate,
        obj=obj,
        visibility="world",
        **kwargs
    )


# =============================================================================
# Pre-built facts for common test scenarios
# =============================================================================

def npc_is_dead(npc_id: str, known: bool = True) -> dict:
    """Fact that an NPC is dead."""
    return make_fact(
        subject_id=npc_id,
        predicate="status",
        obj="dead",
        visibility="known" if known else "world",
        tags=["status", "death"]
    )


def npc_is_hostile(npc_id: str, known: bool = True) -> dict:
    """Fact that an NPC is hostile."""
    return make_fact(
        subject_id=npc_id,
        predicate="disposition",
        obj="hostile",
        visibility="known" if known else "world",
        tags=["disposition"]
    )


def npc_knows_secret(npc_id: str, secret: str, known: bool = False) -> dict:
    """Fact that an NPC knows a secret (usually hidden from player)."""
    return make_fact(
        subject_id=npc_id,
        predicate="knows",
        obj={"secret": secret},
        visibility="known" if known else "world",
        tags=["information", "secret"]
    )


def location_has_clue(location_id: str, clue: str, known: bool = False) -> dict:
    """Fact that a location contains a clue."""
    return make_fact(
        subject_id=location_id,
        predicate="contains_clue",
        obj={"description": clue},
        visibility="known" if known else "world",
        tags=["clue", "investigation"]
    )
