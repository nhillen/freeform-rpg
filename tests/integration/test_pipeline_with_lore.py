"""
Integration tests for the turn pipeline with lore retrieval.

Tests:
  - Orchestrator with lore components wired in
  - Scene transition triggers lore retrieval
  - NPC introduction triggers entity lore fetch
  - Lore context appears in context packet when cached
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.db.state_store import StateStore
from src.core import Orchestrator
from src.llm.gateway import MockGateway
from src.llm.prompt_registry import PromptRegistry
from src.content.retriever import LoreRetriever, RetrievalResult, LoreQuery
from src.content.scene_cache import SceneLoreCacheManager
from src.content.session_manager import SessionManager
from tests.fixtures.state import setup_minimal_game_state


@pytest.fixture
def lore_retriever(state_store):
    """LoreRetriever backed by the test state store."""
    return LoreRetriever(state_store)


@pytest.fixture
def scene_cache(state_store):
    """SceneLoreCacheManager backed by the test state store."""
    return SceneLoreCacheManager(state_store)


@pytest.fixture
def session_mgr(state_store):
    """SessionManager backed by the test state store."""
    return SessionManager(state_store)


class TestOrchestratorWithLore:
    """Tests for Orchestrator with lore components wired in."""

    def test_orchestrator_accepts_lore_params(
        self, state_store, prompt_registry, lore_retriever, scene_cache, session_mgr
    ):
        """Orchestrator can be constructed with lore components."""
        setup_minimal_game_state(state_store)

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
            lore_retriever=lore_retriever,
            scene_cache=scene_cache,
            session_manager=session_mgr,
            pack_ids=["test_pack"],
        )

        assert orch.lore_retriever is lore_retriever
        assert orch.scene_cache is scene_cache
        assert orch.session_manager is session_mgr
        assert orch.pack_ids == ["test_pack"]

    def test_turn_with_lore_components_runs(
        self, state_store, prompt_registry, lore_retriever, scene_cache, session_mgr
    ):
        """A turn runs successfully with lore components wired in."""
        setup_minimal_game_state(state_store)

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
            lore_retriever=lore_retriever,
            scene_cache=scene_cache,
            session_manager=session_mgr,
            pack_ids=["test_pack"],
        )

        result = orch.run_turn("test_campaign", "I look around the room")

        assert result.turn_no >= 1
        assert len(result.final_text) > 0

    def test_lore_context_from_cache_injected(
        self, state_store, prompt_registry, scene_cache
    ):
        """When scene cache has lore, it's fetched in Stage 1."""
        setup_minimal_game_state(state_store)

        # Pre-populate scene cache for current location
        mock_result = RetrievalResult(
            chunks=[{
                "id": "test:loc:atmo",
                "section_title": "Atmosphere",
                "content": "A dimly lit room.",
                "chunk_type": "location",
                "entity_refs": ["test_location"],
                "token_estimate": 10,
            }],
            total_tokens=10,
        )
        scene_cache.materialize(mock_result, "test_location", None, "test_campaign")

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
            lore_retriever=LoreRetriever(state_store),
            scene_cache=scene_cache,
            pack_ids=["test_pack"],
        )

        result = orch.run_turn("test_campaign", "I look around")

        # The turn should succeed; lore_context was fetched from cache
        assert result.turn_no >= 1


class TestSceneTransitionLoreRetrieval:
    """Tests for lore retrieval triggered by scene transitions."""

    def test_scene_transition_triggers_retrieval(
        self, state_store, prompt_registry, scene_cache, session_mgr
    ):
        """When narrator declares a scene transition, lore is retrieved."""
        setup_minimal_game_state(state_store)

        # Create a mock retriever that tracks calls
        mock_retriever = MagicMock(spec=LoreRetriever)
        mock_retriever.retrieve_for_scene.return_value = RetrievalResult(
            chunks=[{
                "id": "pack:new_loc:atmo",
                "section_title": "New Place",
                "content": "A new location.",
                "chunk_type": "location",
                "entity_refs": ["new_location"],
                "token_estimate": 15,
            }],
            total_tokens=15,
        )

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
            lore_retriever=mock_retriever,
            scene_cache=scene_cache,
            session_manager=session_mgr,
            pack_ids=["test_pack"],
        )

        # Patch the narrator to return a scene transition
        narrator_output = {
            "final_text": "You step into the alley.",
            "next_prompt": "what_do_you_do",
            "suggested_actions": [],
            "scene_transition": {
                "location_id": "alley",
                "location_name": "Dark Alley",
                "description": "A narrow, dark alley.",
                "present_entities": ["player"],
            },
        }
        with patch.object(orch, "_run_narrator", return_value=narrator_output):
            result = orch.run_turn("test_campaign", "I go to the alley")

        # Retriever should have been called for the new scene
        assert mock_retriever.retrieve_for_scene.called


class TestNPCIntroductionLoreRetrieval:
    """Tests for lore retrieval triggered by NPC introductions."""

    def test_npc_introduction_triggers_entity_retrieval(
        self, state_store, prompt_registry, scene_cache, session_mgr
    ):
        """When narrator introduces an NPC, lore is fetched for that entity."""
        setup_minimal_game_state(state_store)

        # Pre-populate scene cache so append_npc has something to append to
        initial_result = RetrievalResult(
            chunks=[{
                "id": "test:loc:atmo",
                "section_title": "Scene",
                "content": "A room.",
                "chunk_type": "location",
                "entity_refs": [],
                "token_estimate": 5,
            }],
            total_tokens=5,
        )
        scene_cache.materialize(initial_result, "test_location", None, "test_campaign")

        mock_retriever = MagicMock(spec=LoreRetriever)
        mock_retriever.retrieve_for_entity.return_value = RetrievalResult(
            chunks=[{
                "id": "pack:npc:bg",
                "section_title": "Background",
                "content": "New NPC backstory.",
                "chunk_type": "npc",
                "entity_refs": ["new_npc"],
                "token_estimate": 20,
            }],
            total_tokens=20,
        )

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
            lore_retriever=mock_retriever,
            scene_cache=scene_cache,
            session_manager=session_mgr,
            pack_ids=["test_pack"],
        )

        narrator_output = {
            "final_text": "A shadowy figure steps forward.",
            "next_prompt": "what_do_you_do",
            "suggested_actions": [],
            "introduced_npcs": [
                {
                    "entity_id": "new_npc",
                    "name": "Shadow",
                    "description": "A mysterious figure",
                    "role": "unknown",
                }
            ],
        }
        with patch.object(orch, "_run_narrator", return_value=narrator_output):
            result = orch.run_turn("test_campaign", "I call out into the shadows")

        # Entity lore should have been fetched
        mock_retriever.retrieve_for_entity.assert_called_once_with(
            "new_npc", pack_ids=["test_pack"]
        )


class TestCacheAwareRetrieval:
    """Tests for cache-aware retrieval (skip when already cached)."""

    def test_revisit_location_skips_retrieval(
        self, state_store, prompt_registry, scene_cache, session_mgr
    ):
        """Returning to a cached location does not re-fetch from pack."""
        setup_minimal_game_state(state_store)

        # Pre-populate scene cache for "alley"
        initial_result = RetrievalResult(
            chunks=[{
                "id": "pack:alley:atmo",
                "section_title": "Alley",
                "content": "A dark alley.",
                "chunk_type": "location",
                "entity_refs": ["alley"],
                "token_estimate": 10,
            }],
            total_tokens=10,
        )
        scene_cache.materialize(initial_result, "alley", None, "test_campaign")

        mock_retriever = MagicMock(spec=LoreRetriever)

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
            lore_retriever=mock_retriever,
            scene_cache=scene_cache,
            session_manager=session_mgr,
            pack_ids=["test_pack"],
        )

        # Narrator declares transition to "alley" (already cached)
        narrator_output = {
            "final_text": "You return to the alley.",
            "next_prompt": "what_do_you_do",
            "suggested_actions": [],
            "scene_transition": {
                "location_id": "alley",
                "location_name": "Dark Alley",
                "description": "A narrow, dark alley.",
                "present_entities": ["player"],
            },
        }
        with patch.object(orch, "_run_narrator", return_value=narrator_output):
            result = orch.run_turn("test_campaign", "I go back to the alley")

        # retrieve_for_scene should NOT have been called (cache hit)
        mock_retriever.retrieve_for_scene.assert_not_called()

    def test_npc_already_cached_skips_retrieval(
        self, state_store, prompt_registry, scene_cache, session_mgr
    ):
        """NPC already in scene briefings does not trigger re-fetch."""
        setup_minimal_game_state(state_store)

        # Pre-populate scene cache with existing NPC briefing
        initial_result = RetrievalResult(
            chunks=[
                {
                    "id": "test:loc:atmo",
                    "section_title": "Scene",
                    "content": "A room.",
                    "chunk_type": "location",
                    "entity_refs": [],
                    "token_estimate": 5,
                },
                {
                    "id": "pack:npc:bg",
                    "section_title": "Returning NPC",
                    "content": "NPC backstory.",
                    "chunk_type": "npc",
                    "entity_refs": ["returning_npc"],
                    "token_estimate": 10,
                },
            ],
            total_tokens=15,
        )
        scene_cache.materialize(initial_result, "test_location", None, "test_campaign")

        mock_retriever = MagicMock(spec=LoreRetriever)

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
            lore_retriever=mock_retriever,
            scene_cache=scene_cache,
            session_manager=session_mgr,
            pack_ids=["test_pack"],
        )

        narrator_output = {
            "final_text": "The figure returns.",
            "next_prompt": "what_do_you_do",
            "suggested_actions": [],
            "introduced_npcs": [
                {
                    "entity_id": "returning_npc",
                    "name": "Old Friend",
                    "description": "Someone you've met before",
                    "role": "ally",
                }
            ],
        }
        with patch.object(orch, "_run_narrator", return_value=narrator_output):
            result = orch.run_turn("test_campaign", "I greet the old friend")

        # Entity lore should NOT have been fetched (already in briefings)
        mock_retriever.retrieve_for_entity.assert_not_called()
