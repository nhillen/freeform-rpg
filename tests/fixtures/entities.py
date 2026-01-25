"""
Factory functions for creating test entities.

These create entity dicts (not database records) for use in tests.
Use state.py functions to populate the database.
"""

from typing import Optional


def make_player(
    id: str = "player",
    name: str = "Test Player",
    background: str = "A test character",
    skills: Optional[list] = None,
    weakness: str = "Testing limitations",
    **attr_overrides
) -> dict:
    """
    Create a player character entity.

    Args:
        id: Entity ID (default: "player")
        name: Character name
        background: Character background
        skills: List of skills
        weakness: Character weakness
        **attr_overrides: Additional attrs to merge

    Returns:
        Entity dict ready for database insertion
    """
    attrs = {
        "background": background,
        "skills": skills or ["testing", "debugging"],
        "weakness": weakness,
        **attr_overrides
    }

    return {
        "id": id,
        "type": "pc",
        "name": name,
        "attrs": attrs,
        "tags": ["player"]
    }


def make_npc(
    id: str,
    name: str,
    role: str = "generic",
    description: str = None,
    agenda: str = None,
    location: str = None,
    tags: Optional[list] = None,
    **attr_overrides
) -> dict:
    """
    Create an NPC entity.

    Args:
        id: Unique entity ID
        name: NPC name
        role: NPC role (e.g., "fixer", "enemy", "witness")
        description: Physical/personality description
        agenda: What the NPC wants
        location: Where they're usually found
        tags: Additional tags
        **attr_overrides: Additional attrs to merge

    Returns:
        Entity dict ready for database insertion
    """
    attrs = {
        "role": role,
        "description": description or f"A {role}",
        **attr_overrides
    }

    if agenda:
        attrs["agenda"] = agenda
    if location:
        attrs["location"] = location

    return {
        "id": id,
        "type": "npc",
        "name": name,
        "attrs": attrs,
        "tags": tags or []
    }


def make_location(
    id: str,
    name: str,
    description: str = None,
    atmosphere: str = None,
    features: Optional[list] = None,
    tags: Optional[list] = None,
    **attr_overrides
) -> dict:
    """
    Create a location entity.

    Args:
        id: Unique entity ID
        name: Location name
        description: Location description
        atmosphere: Mood/atmosphere
        features: Notable features
        tags: Additional tags
        **attr_overrides: Additional attrs to merge

    Returns:
        Entity dict ready for database insertion
    """
    attrs = {
        "description": description or f"A place called {name}",
        **attr_overrides
    }

    if atmosphere:
        attrs["atmosphere"] = atmosphere
    if features:
        attrs["features"] = features

    return {
        "id": id,
        "type": "location",
        "name": name,
        "attrs": attrs,
        "tags": tags or []
    }


def make_item(
    id: str,
    name: str,
    description: str = None,
    value: int = 0,
    tags: Optional[list] = None,
    **attr_overrides
) -> dict:
    """
    Create an item entity.

    Args:
        id: Unique entity ID
        name: Item name
        description: Item description
        value: Item value in cred
        tags: Additional tags
        **attr_overrides: Additional attrs to merge

    Returns:
        Entity dict ready for database insertion
    """
    attrs = {
        "description": description or f"A {name}",
        "value": value,
        **attr_overrides
    }

    return {
        "id": id,
        "type": "item",
        "name": name,
        "attrs": attrs,
        "tags": tags or []
    }


# =============================================================================
# Pre-built entities for common test scenarios
# =============================================================================

def hostile_npc() -> dict:
    """A hostile NPC for combat testing."""
    return make_npc(
        id="hostile_npc",
        name="Hostile Goon",
        role="enemy",
        description="A threatening figure",
        agenda="Cause trouble",
        tags=["hostile", "combat"]
    )


def friendly_npc() -> dict:
    """A friendly NPC for social testing."""
    return make_npc(
        id="friendly_npc",
        name="Friendly Contact",
        role="ally",
        description="Someone who might help",
        agenda="Stay out of trouble",
        tags=["friendly", "social"]
    )


def test_location() -> dict:
    """A generic test location."""
    return make_location(
        id="test_location",
        name="Test Room",
        description="A nondescript room for testing",
        features=["door", "window", "table"],
        tags=["interior"]
    )
