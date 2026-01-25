"""Test fixtures for freeform-rpg tests."""

from .entities import make_player, make_npc, make_location, make_item
from .facts import make_fact, make_known_fact, make_world_fact
from .contexts import minimal_context, combat_context, investigation_context
from .state import setup_minimal_game_state, setup_clocks

__all__ = [
    "make_player",
    "make_npc",
    "make_location",
    "make_item",
    "make_fact",
    "make_known_fact",
    "make_world_fact",
    "minimal_context",
    "combat_context",
    "investigation_context",
    "setup_minimal_game_state",
    "setup_clocks",
]
