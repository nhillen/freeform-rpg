"""
Shared pytest fixtures for all tests.
"""

import pytest
import tempfile
import os
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.state_store import StateStore
from src.llm.gateway import MockGateway
from src.llm.prompt_registry import PromptRegistry
from src.context.builder import ContextBuilder
from src.core.validator import Validator
from src.core.resolver import Resolver


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def db_path(tmp_path):
    """Temporary database path for testing."""
    return tmp_path / "test_game.db"


@pytest.fixture
def state_store(db_path):
    """Fresh state store with schema initialized."""
    store = StateStore(db_path)
    store.ensure_schema()
    return store


@pytest.fixture
def populated_store(state_store):
    """
    State store with minimal test data loaded.

    Contains:
    - 1 campaign
    - 1 player entity
    - 1 NPC entity
    - 1 location entity
    - 1 scene with player and NPC present
    - 5 clocks (heat, time, harm, cred, rep)
    - 2 facts (1 known, 1 world)
    - 1 active thread
    """
    from tests.fixtures.entities import make_player, make_npc, make_location
    from tests.fixtures.state import setup_minimal_game_state

    setup_minimal_game_state(state_store)
    return state_store


# =============================================================================
# LLM Fixtures
# =============================================================================

@pytest.fixture
def mock_gateway():
    """Mock LLM gateway for testing without API calls."""
    return MockGateway()


@pytest.fixture
def prompt_registry():
    """Prompt registry pointing to actual prompts."""
    prompts_dir = Path(__file__).parent.parent / "src" / "prompts"
    return PromptRegistry(prompts_dir)


# =============================================================================
# Component Fixtures
# =============================================================================

@pytest.fixture
def context_builder(state_store):
    """Context builder with state store."""
    return ContextBuilder(state_store)


@pytest.fixture
def validator(state_store):
    """Validator with state store."""
    return Validator(state_store)


@pytest.fixture
def resolver(state_store):
    """Resolver with state store."""
    return Resolver(state_store)


# =============================================================================
# Context Packet Fixtures
# =============================================================================

@pytest.fixture
def minimal_context():
    """Minimal valid context packet for testing."""
    from tests.fixtures.contexts import minimal_context
    return minimal_context()


@pytest.fixture
def combat_context():
    """Context with player and hostile NPC."""
    from tests.fixtures.contexts import combat_context
    return combat_context()


@pytest.fixture
def investigation_context():
    """Context with player, clues, and NPCs to question."""
    from tests.fixtures.contexts import investigation_context
    return investigation_context()


# =============================================================================
# Interpreter Output Fixtures
# =============================================================================

@pytest.fixture
def simple_action_interpreter_output():
    """Interpreter output for a simple valid action."""
    return {
        "intent": "examine the room",
        "referenced_entities": ["test_location"],
        "proposed_actions": [
            {"action": "examine", "target_id": "test_location", "details": "looking around carefully"}
        ],
        "assumptions": [],
        "risk_flags": [],
        "perception_flags": []
    }


@pytest.fixture
def combat_interpreter_output():
    """Interpreter output for a combat action."""
    return {
        "intent": "attack the hostile NPC",
        "referenced_entities": ["hostile_npc"],
        "proposed_actions": [
            {"action": "attack", "target_id": "hostile_npc", "details": "throwing a punch"}
        ],
        "assumptions": [],
        "risk_flags": ["violence"],
        "perception_flags": []
    }


@pytest.fixture
def invalid_target_interpreter_output():
    """Interpreter output referencing an entity not in scene."""
    return {
        "intent": "talk to someone not here",
        "referenced_entities": ["nonexistent_npc"],
        "proposed_actions": [
            {"action": "talk", "target_id": "nonexistent_npc", "details": "asking questions"}
        ],
        "assumptions": [],
        "risk_flags": [],
        "perception_flags": [
            {"entity_id": "nonexistent_npc", "issue": "not_present", "player_assumption": "thought they were here"}
        ]
    }
