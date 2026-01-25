"""
Factory functions for creating test context packets.

Context packets are what get sent to the LLM prompts.
"""

from typing import Optional
from .entities import make_player, make_npc, make_location, hostile_npc, friendly_npc, test_location
from .facts import make_known_fact, make_world_fact


def minimal_context(
    player_name: str = "Test Player",
    location_name: str = "Test Room"
) -> dict:
    """
    Minimal valid context packet for testing.

    Contains just a player in a location with basic clocks.
    """
    player = make_player(name=player_name)
    location = make_location(
        id="test_location",
        name=location_name,
        description="A simple room for testing"
    )

    return {
        "scene": {
            "location_id": "test_location",
            "time": {"hour": 12, "period": "day"},
            "constraints": {},
            "visibility_conditions": "normal",
            "noise_level": "normal"
        },
        "present_entities": ["player", "test_location"],
        "entities": [player, location],
        "facts": [],
        "threads": [],
        "clocks": [
            {"id": "heat", "name": "Heat", "value": 0, "max": 8, "triggers": {}, "tags": []},
            {"id": "time", "name": "Time", "value": 8, "max": 12, "triggers": {}, "tags": []},
            {"id": "harm", "name": "Harm", "value": 0, "max": 4, "triggers": {}, "tags": []},
        ],
        "inventory": [],
        "summary": {"scene": "", "threads": ""},
        "recent_events": [],
        "calibration": {
            "tone": {},
            "themes": {},
            "risk": {"lethality": "moderate", "failure_mode": "consequential"}
        },
        "genre_rules": {}
    }


def combat_context(
    player_name: str = "Test Player",
    enemy_name: str = "Hostile Goon"
) -> dict:
    """
    Context with player and hostile NPC for combat testing.
    """
    player = make_player(name=player_name)
    enemy = make_npc(
        id="hostile_npc",
        name=enemy_name,
        role="enemy",
        description="A threatening figure looking for trouble",
        tags=["hostile", "combat"]
    )
    location = make_location(
        id="combat_location",
        name="Dark Alley",
        description="A narrow alley with poor lighting",
        atmosphere="Tense and dangerous"
    )

    return {
        "scene": {
            "location_id": "combat_location",
            "time": {"hour": 23, "period": "night"},
            "constraints": {},
            "visibility_conditions": "dim",
            "noise_level": "quiet"
        },
        "present_entities": ["player", "hostile_npc", "combat_location"],
        "entities": [player, enemy, location],
        "facts": [
            {
                "id": "fact_hostile",
                "subject_id": "hostile_npc",
                "predicate": "disposition",
                "object": "hostile",
                "visibility": "known",
                "confidence": 1.0,
                "tags": ["disposition"]
            }
        ],
        "threads": [
            {
                "id": "thread_confrontation",
                "title": "Deal with the hostile",
                "status": "active",
                "stakes": {"success": "Safety", "failure": "Harm"},
                "related_entity_ids": ["hostile_npc"],
                "tags": ["combat"]
            }
        ],
        "clocks": [
            {"id": "heat", "name": "Heat", "value": 2, "max": 8, "triggers": {"4": "Cops incoming"}, "tags": []},
            {"id": "time", "name": "Time", "value": 6, "max": 12, "triggers": {}, "tags": []},
            {"id": "harm", "name": "Harm", "value": 0, "max": 4, "triggers": {"4": "Critical condition"}, "tags": []},
        ],
        "inventory": [
            {"owner_id": "player", "item_id": "knife", "qty": 1, "flags": {"equipped": True}}
        ],
        "summary": {"scene": "Confrontation in a dark alley", "threads": "Active: Deal with the hostile"},
        "recent_events": [],
        "calibration": {
            "tone": {"gritty_vs_cinematic": 0.7},
            "themes": {"primary": ["survival"]},
            "risk": {"lethality": "moderate", "failure_mode": "consequential"}
        },
        "genre_rules": {"setting": "Urban noir"}
    }


def investigation_context(
    player_name: str = "Test Player"
) -> dict:
    """
    Context with player, clues, and NPCs for investigation testing.
    """
    player = make_player(name=player_name)
    witness = make_npc(
        id="witness_npc",
        name="Nervous Witness",
        role="witness",
        description="Someone who saw something they shouldn't have",
        tags=["social", "information"]
    )
    location = make_location(
        id="crime_scene",
        name="Crime Scene",
        description="A room where something bad happened",
        features=["overturned furniture", "broken window", "bloodstain"],
        tags=["investigation"]
    )

    return {
        "scene": {
            "location_id": "crime_scene",
            "time": {"hour": 14, "period": "afternoon"},
            "constraints": {},
            "visibility_conditions": "normal",
            "noise_level": "quiet"
        },
        "present_entities": ["player", "witness_npc", "crime_scene"],
        "entities": [player, witness, location],
        "facts": [
            # Known facts
            {
                "id": "fact_crime_happened",
                "subject_id": "crime_scene",
                "predicate": "event",
                "object": {"type": "crime", "description": "Something violent occurred here"},
                "visibility": "known",
                "confidence": 1.0,
                "tags": ["event"]
            },
            # Hidden facts (clues to discover)
            {
                "id": "fact_witness_saw",
                "subject_id": "witness_npc",
                "predicate": "knows",
                "object": {"what": "who did it", "will_share": "if pressed"},
                "visibility": "world",
                "confidence": 1.0,
                "tags": ["clue", "hidden"]
            },
            {
                "id": "fact_hidden_evidence",
                "subject_id": "crime_scene",
                "predicate": "contains",
                "object": {"item": "dropped ID card", "location": "under furniture"},
                "visibility": "world",
                "confidence": 1.0,
                "tags": ["clue", "hidden"]
            }
        ],
        "threads": [
            {
                "id": "thread_investigate",
                "title": "Find out what happened",
                "status": "active",
                "stakes": {"success": "Truth revealed", "failure": "Trail goes cold"},
                "related_entity_ids": ["crime_scene", "witness_npc"],
                "tags": ["investigation", "main"]
            }
        ],
        "clocks": [
            {"id": "heat", "name": "Heat", "value": 1, "max": 8, "triggers": {}, "tags": []},
            {"id": "time", "name": "Time", "value": 8, "max": 12, "triggers": {"4": "Getting late"}, "tags": []},
            {"id": "harm", "name": "Harm", "value": 0, "max": 4, "triggers": {}, "tags": []},
        ],
        "inventory": [],
        "summary": {
            "scene": "Investigating a crime scene with a nervous witness nearby",
            "threads": "Active: Find out what happened"
        },
        "recent_events": [],
        "calibration": {
            "tone": {"slow_burn_vs_action": 0.7},
            "themes": {"primary": ["truth", "justice"]},
            "risk": {"lethality": "low", "failure_mode": "consequential"}
        },
        "genre_rules": {"setting": "Noir investigation"}
    }


def obscured_entity_context() -> dict:
    """
    Context with an obscured entity for perception testing.

    The hidden_npc is present but obscured (in shadows, etc.).
    """
    base = minimal_context()

    hidden_npc = make_npc(
        id="hidden_npc",
        name="Lurking Figure",
        role="unknown",
        description="Someone hiding in the shadows",
        tags=["hidden"]
    )

    base["entities"].append(hidden_npc)
    base["present_entities"].append("hidden_npc")
    base["scene"]["obscured_entities"] = ["hidden_npc"]
    base["scene"]["visibility_conditions"] = "dim"

    return base
